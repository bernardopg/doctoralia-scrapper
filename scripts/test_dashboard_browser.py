#!/usr/bin/env python3
"""Run isolated dashboard rendering checks with Playwright and synthetic API data."""

import json
import logging
import os
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ATTACK = "</textarea><img src=x onerror=window.__xss++> ' \" &"


def hostile(label):
    return f"{label}: {ATTACK}"


PROFILE_ID = "profile&?#/'\""
REVIEW_ID = "review&?#/'\""
TASK_ID = "task&?#/'\""
SCHEDULE_ID = "schedule&?#/'\""
REVIEW = dict(
    profile_id=PROFILE_ID,
    review_id=REVIEW_ID,
    doctor_name=ATTACK,
    author=ATTACK,
    comment=ATTACK,
    generated_response=ATTACK,
    rating=5,
    date="2026-01-01",
)
PROFILE = dict(
    profile_id=PROFILE_ID,
    doctor_name=ATTACK,
    specialty=ATTACK,
    profile_url="https://example.test/doctor",
    total_scrapes=1,
    current_unanswered=1,
    average_rating=5,
)
FAVORITES = [
    dict(name=ATTACK, specialty=ATTACK, notes=ATTACK, profile_url=url)
    for url in [
        "javascript:window.__xss++",
        "data:text/html,hello",
        "https://example.test/doctor' onmouseover='window.__xss++' data-x='",
    ]
]


blocked_opens: list[str] = []


class ConfigLoadForbidden(BaseException):
    pass


def deny_sensitive_open(event, args):
    """Reject persisted settings before any project module can open them."""
    if (
        event != "open"
        or not args
        or not isinstance(args[0], (str, bytes, os.PathLike))
    ):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if (
        path.name == ".env"
        or path.name.startswith(".env.")
        or path.name == "config.json"
        or any(
            part.lower()
            in {
                "credentials",
                "credentials.json",
                "credentials.toml",
                "credentials.yaml",
                "credentials.yml",
            }
            for part in path.parts
        )
    ):
        blocked_opens.append(str(path))
        raise PermissionError("Persistent configuration is forbidden in this test")


def main():
    if len(sys.argv) == 1:
        parent_net = os.readlink("/proc/self/ns/net")
        os.execvp(
            "unshare",
            [
                "unshare",
                "--user",
                "--map-root-user",
                "--net",
                sys.executable,
                __file__,
                "--isolated",
                parent_net,
            ],
        )
    if (
        len(sys.argv) != 3
        or sys.argv[1] != "--isolated"
        or os.readlink("/proc/self/ns/net") == sys.argv[2]
    ):
        raise RuntimeError("A distinct network namespace is required")
    subprocess.run(["/usr/bin/ip", "link", "set", "lo", "up"], check=True)
    links = subprocess.check_output(["/usr/bin/ip", "-o", "link", "show"], text=True)
    routes = subprocess.check_output(["/usr/bin/ip", "route", "show"], text=True)
    if len(links.splitlines()) != 1 or "lo:" not in links or routes.strip():
        raise RuntimeError("Unexpected namespace network configuration")
    browser_cache = os.environ.get(
        "PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache/ms-playwright")
    )
    with tempfile.TemporaryDirectory(prefix="rel04-") as data, ExitStack() as stack:
        canaries = (
            Path(data) / ".env",
            Path(data) / "config.json",
            Path(data) / "credentials" / "secret",
        )
        canaries[-1].parent.mkdir()
        for canary in canaries:
            canary.write_text("synthetic-test-secret")
        sys.addaudithook(deny_sensitive_open)

        def remove_canaries():
            for canary in canaries:
                canary.unlink()
            canaries[-1].parent.rmdir()

        stack.callback(remove_canaries)
        os.environ.clear()
        os.environ.update(
            PATH="/usr/bin:/bin",
            HOME=data,
            PLAYWRIGHT_BROWSERS_PATH=browser_cache,
            DASHBOARD_SESSION_SECRET="rel04-test-secret",
            NO_PROXY="*",
        )
        # Verify that the guard rejects an access, without creating a project canary.
        for forbidden in canaries:
            try:
                open(forbidden).close()
            except PermissionError:
                pass
            else:
                raise AssertionError("sensitive-file guard failed")
        assert len(blocked_opens) == len(canaries)
        blocked_opens.clear()
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        from src.config.settings import AppConfig

        config = SimpleNamespace(
            data_dir=data,
            security=SimpleNamespace(
                dashboard_auth_enabled=False,
                dashboard_session_secret="rel04-test-secret",
            ),
        )
        stack.enter_context(
            patch.object(
                AppConfig,
                "load",
                side_effect=ConfigLoadForbidden("AppConfig.load forbidden"),
            )
        )
        stack.enter_context(
            patch(
                "requests.sessions.Session.request",
                side_effect=RuntimeError("External HTTP blocked"),
            )
        )
        stack.enter_context(patch("nltk.download", return_value=False))
        from src.dashboard.app import DashboardApp
        from src.dashboard.services import DashboardServices

        stack.enter_context(
            patch.object(DashboardApp, "_get_runtime_config", return_value=config)
        )
        stack.enter_context(
            patch.object(DashboardServices, "_get_runtime_config", return_value=config)
        )
        stack.enter_context(patch("src.dashboard.app.ResponseQualityAnalyzer"))
        dashboard = DashboardApp(config=config, logger=logging.getLogger("rel04"))
        stack.enter_context(
            patch.object(dashboard.svc, "get_user_profile_settings", return_value={})
        )
        stack.enter_context(
            patch.object(
                dashboard.svc,
                "get_api_docs_url",
                return_value="http://example.test/docs",
            )
        )
        server = make_server("127.0.0.1", 0, dashboard.app)
        stack.callback(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop_server():
            server.shutdown()
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Server failed to stop")

        stack.callback(stop_server)
        origin = f"http://127.0.0.1:{server.server_port}"
        saved = []
        requested = []
        violations = []
        # Only the Flask port is open on the namespace loopback.
        for address in (("127.0.0.1", 8000), ("192.0.2.1", 80)):
            try:
                with socket.create_connection(address, timeout=1):
                    raise AssertionError(f"unexpected connection: {address}")
            except OSError:
                pass
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=1):
            pass
        import requests

        try:
            requests.get(origin, proxies={"http": "http://127.0.0.1:8000"})
        except RuntimeError as exc:
            assert "blocked" in str(exc)
        else:
            raise AssertionError("requests proxy bypassed guard")
        try:
            AppConfig.load()
        except ConfigLoadForbidden:
            pass
        else:
            raise AssertionError("AppConfig.load was not blocked")
        fixtures = {
            "/api/workspace/overview": {
                "summary": {"unanswered_reviews_current": hostile("overview-counter")},
                "favorite_profiles": [PROFILE],
            },
            "/api/workspace/responses": {"items": [REVIEW], "filters": [PROFILE]},
            "/api/workspace/profiles": {"profiles": [PROFILE]},
            "/api/workspace/profile": {"profile": PROFILE, "latest_reviews": [REVIEW]},
            "/api/workspace/history": {
                "entries": [dict(PROFILE, filename=ATTACK, reviews_count=1)],
                "filters": [PROFILE],
            },
            "/api/workspace/reports": {
                "summary": {
                    key: hostile(key)
                    for key in (
                        "profiles_tracked",
                        "total_reviews_current",
                        "generated_current",
                        "outdated_snapshots",
                    )
                },
                "top_profiles": [dict(PROFILE, doctor_name=hostile("top-profile"))],
                "inventory": [
                    dict(
                        PROFILE,
                        doctor_name=hostile("inventory-name"),
                        filename=hostile("inventory-file"),
                    )
                ],
            },
            "/api/user-profile": {
                "display_name": ATTACK,
                "username": ATTACK,
                "favorite_profiles": FAVORITES,
            },
            "/api/notifications/telegram/schedules": {
                "schedules": [
                    dict(
                        id=SCHEDULE_ID,
                        name=ATTACK,
                        profile_label=ATTACK,
                        recurrence_type="daily",
                        enabled=True,
                    )
                ]
            },
            "/api/notifications/telegram/history": {
                "history": [
                    dict(
                        schedule_name=hostile("history-name"),
                        summary=hostile("history-summary"),
                        error=hostile("history-error"),
                        status="success",
                        metrics={
                            "total_reviews": hostile("history-reviews"),
                            "generated_responses": hostile("history-generated"),
                        },
                    )
                ]
            },
            "/api/ready": {"ready": True, "components": {}},
            "/api/health": {"dashboard": "ok", "api": {"status": "connected"}},
            "/api/tasks": [
                {"task_id": TASK_ID, "status": "completed", "progress": 100}
            ],
            "/api/tasks/"
            + TASK_ID: {
                "doctor": {"name": ATTACK},
                "metrics": {"scraped_count": ATTACK},
            },
            "/api/auth/session": {},
            "/api/settings": {},
            "/api/performance": {},
        }
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            print("Chromium:", browser.version)
            context = browser.new_context(service_workers="block")
            context.add_init_script("""window.__xss=0; window.__clipboard='';
              Object.defineProperty(navigator, 'clipboard', {value:{writeText: async t => {window.__clipboard=t}}});
              window.Chart=class {destroy(){} update(){}};""")
            page = context.new_page()
            page.set_default_timeout(5000)
            dialogs = []

            def dismiss_dialog(dialog):
                dialogs.append(dialog.message)
                dialog.dismiss()

            page.on("dialog", dismiss_dialog)

            def route_handler(route):
                from urllib.parse import parse_qs, unquote, urlsplit

                url = urlsplit(route.request.url)
                requested.append((url.path, url.query))
                if url.path == "/api/workspace/profile":
                    parsed = parse_qs(url.query, keep_blank_values=True)
                    if parsed.get("profile_id") != [PROFILE_ID] or any(
                        x not in url.query.upper() for x in ("%26", "%3F", "%23", "%2F")
                    ):
                        violations.append((url.path, url.query))
                if url.path.startswith("/api/notifications/telegram/schedules/"):
                    encoded = url.path[len("/api/notifications/telegram/schedules/") :]
                    if unquote(encoded) != SCHEDULE_ID or any(
                        x not in encoded.upper() for x in ("%26", "%3F", "%23", "%2F")
                    ):
                        violations.append((url.path, url.query))
                if url.path.startswith("/api/tasks/"):
                    encoded = url.path[len("/api/tasks/") :]
                    if unquote(encoded) != TASK_ID or any(
                        x not in encoded.upper() for x in ("%26", "%3F", "%23", "%2F")
                    ):
                        violations.append((url.path, url.query))
                if route.request.url.startswith(origin + "/api/"):
                    if url.path == "/api/workspace/responses/save":
                        saved.append(route.request.post_data_json)
                        payload: object = {"success": True}
                    else:
                        payload = fixtures.get(unquote(url.path), {})
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(payload),
                    )
                elif route.request.url.startswith(origin + "/"):
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", route_handler)

            def visit(path):
                page.goto(origin + path, wait_until="networkidle")
                assert page.evaluate("window.__xss") == 0, path

            visit("/")
            assert page.evaluate("""async () => {
              try { await fetch('http://127.0.0.1:8000/private'); return false; }
              catch (_) { return true; }
            }""")
            assert page.evaluate("""() => new Promise(resolve => {
              const ws = new WebSocket('ws://127.0.0.1:8000/private');
              ws.onopen = () => resolve(false); ws.onerror = () => resolve(true);
              setTimeout(() => resolve(false), 3000);
            })""")
            with page.expect_popup() as popup_info:
                page.evaluate("window.open('http://127.0.0.1:8000/popup')")
            popup = popup_info.value
            popup.wait_for_load_state("load")
            assert popup.url != "http://127.0.0.1:8000/popup"
            popup.close()
            assert (
                hostile("overview-counter")
                in page.locator("#overview-unanswered").inner_text()
            )
            assert page.locator("#overview-unanswered img").count() == 0
            assert page.locator("#overview-next-actions").inner_text().find(ATTACK) >= 0
            assert page.locator("#overview-next-actions img").count() == 0
            page.evaluate(
                "renderNextActions({unanswered_reviews_current: 7, favorite_profiles_count: 1}, [])"
            )
            assert (
                "7 comentários" in page.locator("#overview-next-actions").inner_text()
            )
            visit("/responses")
            assert page.locator("#responses-list").inner_text().find(ATTACK) >= 0
            assert page.locator("#responses-list img").count() == 0
            page.locator("#responses-list textarea").fill("Resposta legítima & segura")
            page.get_by_role("button", name="Salvar Edição").click()
            page.wait_for_function(
                "document.querySelector('#responses-alert').textContent.includes('sucesso')"
            )
            assert (
                saved[-1]["review_id"] == REVIEW_ID
                and saved[-1]["profile_id"] == PROFILE_ID
                and saved[-1]["generated_response"] == "Resposta legítima & segura"
            )
            page.get_by_role("button", name="Copiar", exact=True).click()
            page.wait_for_function(
                "window.__clipboard === 'Resposta legítima & segura'"
            )
            visit("/profiles")
            assert ATTACK in page.locator("#profiles-list").inner_text()
            assert page.locator("#profiles-list img").count() == 0
            assert ATTACK in page.locator("#profile-latest-reviews").inner_text()
            assert page.locator("#profile-latest-reviews img").count() == 0
            assert any(path == "/api/workspace/profile" for path, query in requested)
            visit("/history")
            assert ATTACK in page.locator("#history-table-body").inner_text()
            assert page.locator("#history-table-body img").count() == 0
            page.locator("#tasks-table-body button").click()
            page.wait_for_function(
                "text => document.querySelector('#task-detail-body').textContent.includes(text)",
                arg=ATTACK,
            )
            assert page.locator("#task-detail-body img").count() == 0
            assert any(path.startswith("/api/tasks/") for path, query in requested)
            visit("/reports")
            assert ATTACK in page.locator("#reports-operational-summary").inner_text()
            assert page.locator("#reports-operational-summary img").count() == 0
            lines = page.locator(
                "#reports-operational-summary .report-line-item strong"
            )
            for index, key in (
                (0, "profiles_tracked"),
                (1, "total_reviews_current"),
                (2, "generated_current"),
                (4, "outdated_snapshots"),
            ):
                assert lines.nth(index).inner_text() == hostile(key)
            assert (
                hostile("top-profile")
                in page.locator("#reports-top-profiles").inner_text()
            )
            assert (
                hostile("inventory-name")
                in page.locator("#reports-inventory-table").inner_text()
            )
            assert (
                hostile("inventory-file")
                in page.locator("#reports-inventory-table").inner_text()
            )
            assert (
                page.locator(
                    "#reports-top-profiles img, #reports-inventory-table img"
                ).count()
                == 0
            )
            visit("/me")
            cards = page.locator(".favorite-entry-card")
            assert cards.count() == 3 and ATTACK in cards.first.inner_text()
            assert cards.locator("img").count() == 0
            assert cards.nth(0).locator("a.favorite-entry-link").count() == 0
            assert cards.nth(1).locator("a.favorite-entry-link").count() == 0
            assert (
                cards.nth(2)
                .locator("a.favorite-entry-link")
                .get_attribute("href")
                .startswith("https://example.test/doctor")
            )
            cards.nth(2).hover()
            cards.nth(2).get_by_role("button", name="Editar").click()
            assert (
                page.locator("#favorite-url").input_value()
                == FAVORITES[2]["profile_url"]
            )
            assert page.evaluate("window.__xss") == 0
            visit("/notifications/telegram/schedule")
            history = page.locator("#history-table-body")
            for field in (
                "history-name",
                "history-summary",
                "history-error",
                "history-reviews",
                "history-generated",
            ):
                assert hostile(field) in history.inner_text()
            assert history.locator("img").count() == 0
            assert ATTACK in page.locator("#schedule-card-list").inner_text()
            assert page.locator("#schedule-card-list img").count() == 0
            page.locator("#schedule-card-list").get_by_role(
                "button", name="Editar"
            ).click()
            assert page.locator("#edit-schedule-name").input_value() == ATTACK
            page.locator("#edit-schedule-name").fill("Agendamento legítimo")
            page.locator("#edit-schedule-submit").click()
            page.wait_for_function("!notificationState.editingId")
            assert any(
                path.startswith("/api/notifications/telegram/schedules/")
                for path, query in requested
            )
            assert page.evaluate("window.__xss") == 0
            for path in ["/settings", "/health-check"]:
                visit(path)
            assert not dialogs and page.evaluate("window.__xss") == 0
            assert not violations, violations
            assert not blocked_opens, blocked_opens
            browser.close()
            print(
                "PASS: overview, responses save/copy, profiles, history, reports, favorites, schedule, settings, health"
            )


if __name__ == "__main__":
    main()
