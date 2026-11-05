#!/usr/bin/env python3
"""Run isolated dashboard rendering checks with Playwright and synthetic API data."""

import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ATTACK = "</textarea><img src=x onerror=window.__xss++> ' \" &"
IDENT = "id' onmouseover='window.__xss++' data-x='"
REVIEW = dict(
    profile_id=IDENT,
    review_id=IDENT,
    doctor_name=ATTACK,
    author=ATTACK,
    comment=ATTACK,
    generated_response=ATTACK,
    rating=5,
    date="2026-01-01",
)
PROFILE = dict(
    profile_id=IDENT,
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


def main():
    # Never load the user's environment, config or data. API calls are intercepted below.
    browser_cache = os.environ.get(
        "PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache/ms-playwright")
    )
    os.environ.clear()
    os.environ.update(
        PATH="/usr/bin:/bin",
        HOME="/tmp",
        PLAYWRIGHT_BROWSERS_PATH=browser_cache,
        DASHBOARD_SESSION_SECRET="rel04-test-secret",
    )
    with tempfile.TemporaryDirectory(prefix="rel04-") as data:
        config = SimpleNamespace(
            data_dir=data,
            security=SimpleNamespace(
                dashboard_auth_enabled=False,
                dashboard_session_secret="rel04-test-secret",
            ),
        )
        network_guard = patch(
            "requests.sessions.Session.request",
            side_effect=RuntimeError("External HTTP blocked"),
        )
        network_guard.start()
        with patch("nltk.download", return_value=False):
            from src.dashboard.app import DashboardApp

        with (
            patch.object(DashboardApp, "_get_runtime_config", return_value=config),
            patch("src.dashboard.app.ResponseQualityAnalyzer"),
        ):
            dashboard = DashboardApp(config=config, logger=logging.getLogger("rel04"))
        dashboard.svc.get_user_profile_settings = lambda: {}
        dashboard.svc.get_api_docs_url = lambda: "http://example.test/docs"
        server = make_server("127.0.0.1", 0, dashboard.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        saved = []
        fixtures = {
            "/api/workspace/overview": {
                "summary": {"unanswered_reviews_current": ATTACK},
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
                "summary": {"profiles_tracked": ATTACK},
                "top_profiles": [PROFILE],
                "inventory": [dict(PROFILE, filename=ATTACK)],
            },
            "/api/user-profile": {
                "display_name": ATTACK,
                "username": ATTACK,
                "favorite_profiles": FAVORITES,
            },
            "/api/notifications/telegram/schedules": {
                "schedules": [
                    dict(
                        id=IDENT,
                        name=ATTACK,
                        profile_label=ATTACK,
                        recurrence_type="daily",
                        enabled=True,
                    )
                ]
            },
            "/api/notifications/telegram/history": {"history": []},
            "/api/ready": {"ready": True, "components": {}},
            "/api/health": {"dashboard": "ok", "api": {"status": "connected"}},
            "/api/tasks": [{"task_id": IDENT, "status": "completed", "progress": 100}],
            "/api/tasks/"
            + IDENT: {"doctor": {"name": ATTACK}, "metrics": {"scraped_count": ATTACK}},
            "/api/auth/session": {},
            "/api/settings": {},
            "/api/performance": {},
        }
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                print("Chromium:", browser.version)
                context = browser.new_context()
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
                    from urllib.parse import unquote, urlsplit

                    url = urlsplit(route.request.url)
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

                page.route("**/*", route_handler)

                def visit(path):
                    page.goto(origin + path, wait_until="networkidle")
                    assert page.evaluate("window.__xss") == 0, path

                visit("/")
                assert (
                    page.locator("#overview-next-actions").inner_text().find(ATTACK)
                    >= 0
                )
                assert page.locator("#overview-next-actions img").count() == 0
                visit("/responses")
                assert page.locator("#responses-list").inner_text().find(ATTACK) >= 0
                assert page.locator("#responses-list img").count() == 0
                page.locator("#responses-list textarea").fill(
                    "Resposta legítima & segura"
                )
                page.get_by_role("button", name="Salvar Edição").click()
                page.wait_for_function(
                    "document.querySelector('#responses-alert').textContent.includes('sucesso')"
                )
                assert (
                    saved[-1]["profile_id"] == IDENT
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
                visit("/history")
                assert ATTACK in page.locator("#history-table-body").inner_text()
                assert page.locator("#history-table-body img").count() == 0
                page.locator("#tasks-table-body button").click()
                page.wait_for_function(
                    "text => document.querySelector('#task-detail-body').textContent.includes(text)",
                    arg=ATTACK,
                )
                assert page.locator("#task-detail-body img").count() == 0
                visit("/reports")
                assert (
                    ATTACK in page.locator("#reports-operational-summary").inner_text()
                )
                assert page.locator("#reports-operational-summary img").count() == 0
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
                assert ATTACK in page.locator("#schedule-card-list").inner_text()
                assert page.locator("#schedule-card-list img").count() == 0
                page.locator("#schedule-card-list").get_by_role(
                    "button", name="Editar"
                ).click()
                assert page.locator("#edit-schedule-name").input_value() == ATTACK
                assert page.evaluate("window.__xss") == 0
                for path in ["/settings", "/health-check"]:
                    visit(path)
                assert not dialogs and page.evaluate("window.__xss") == 0
                browser.close()
                print(
                    "PASS: overview, responses save/copy, profiles, history, reports, favorites, schedule, settings, health"
                )
        finally:
            network_guard.stop()
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
