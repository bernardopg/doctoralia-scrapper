#!/usr/bin/env python3
"""Browser checks for dashboard states, accessibility and responsiveness.

The dashboard runs against synthetic snapshots in a temporary directory with
the real workspace service. Requests leaving the local server are aborted, and
calls to the scraping API fail, so nothing external is contacted.

Usage (needs Playwright and its Chromium build)::

    python scripts/test_dashboard_ux.py [--screenshots DIR]
"""

import argparse
import json
import logging
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VIEWPORTS = {"mobile": (375, 812), "tablet": (768, 1024), "desktop": (1280, 800)}
PAGES = ["/", "/responses", "/profiles", "/history", "/reports", "/settings"]


def _write_snapshots(data_dir: Path) -> None:
    complete = {
        "doctor_name": "Dra Sintética Completa",
        "url": "https://example.test/completa",
        "extraction_timestamp": "2026-03-01T09:00:00",
        "collection": {"status": "complete", "expected_count": 30},
        "reviews": [
            {
                "id": f"doctoralia:{index}",
                "author": f"Paciente {index}",
                "comment": f"Comentário sintético número {index}. " * 3,
                "rating": 5 - index % 3,
                "date": (f"2026-01-{index:02d}" if index <= 28 else None),
            }
            for index in range(1, 31)
        ],
    }
    partial = {
        "doctor_name": "Dr Sintético Parcial",
        "url": "https://example.test/parcial",
        "extraction_timestamp": "2026-03-02T09:00:00",
        "collection": {
            "status": "partial",
            "expected_count": 9,
            "extracted_count": 2,
            "stop_reason": "time_limit",
        },
        "reviews": [
            {
                "id": f"doctoralia:{100 + index}",
                "author": "Paciente parcial",
                "comment": "Avaliação de coleta parcial",
                "rating": 4,
                "date": "2026-02-10",
            }
            for index in range(2)
        ],
    }
    for name, payload in (("completa.json", complete), ("parcial.json", partial)):
        (data_dir / name).write_text(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    failures: list[str] = []
    page_errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        print(("ok   " if condition else "FAIL ") + message)
        if not condition:
            failures.append(message)

    with tempfile.TemporaryDirectory(prefix="ux-") as tmp, ExitStack() as stack:
        data_dir = Path(tmp)
        _write_snapshots(data_dir)
        config = SimpleNamespace(
            data_dir=data_dir,
            logs_dir=data_dir / "logs",
            security=SimpleNamespace(
                dashboard_auth_enabled=False, dashboard_session_secret="ux-secret"
            ),
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
        dashboard = DashboardApp(config=config, logger=logging.getLogger("ux"))
        stack.enter_context(
            patch.object(dashboard.svc, "get_user_profile_settings", return_value={})
        )
        server = make_server("127.0.0.1", 0, dashboard.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stack.callback(server.server_close)
        stack.callback(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            print("Chromium:", browser.version)

            def new_page(width: int, height: int, clipboard: bool = True):
                context = browser.new_context(
                    viewport={"width": width, "height": height}
                )
                script = (
                    "window.Chart = class { destroy(){} update(){} };"
                    "Chart.defaults = {}; Chart.instances = {};"
                )
                if not clipboard:
                    script += (
                        "Object.defineProperty(navigator, 'clipboard', {value: undefined});"
                        "window.__copied = null;"
                        "document.execCommand = (cmd) => {"
                        " if (cmd === 'copy') { window.__copied = document.activeElement.value; }"
                        " return cmd === 'copy'; };"
                    )
                context.add_init_script(script)
                context.route(
                    "**/*",
                    lambda route: (
                        route.continue_()
                        if route.request.url.startswith(origin)
                        else route.abort()
                    ),
                )
                page = context.new_page()
                page.set_default_timeout(5000)
                page.on(
                    "pageerror",
                    lambda error: page_errors.append(f"{page.url}: {error}"),
                )
                return page

            # Responsive layout: no horizontal scrolling on any main page.
            for label, (width, height) in VIEWPORTS.items():
                page = new_page(width, height)
                for path in PAGES:
                    page.goto(origin + path, wait_until="networkidle")
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - window.innerWidth"
                    )
                    check(
                        overflow <= 1,
                        f"{label} {path}: no horizontal overflow ({overflow}px)",
                    )
                    if args.screenshots:
                        args.screenshots.mkdir(parents=True, exist_ok=True)
                        name = path.strip("/") or "overview"
                        page.screenshot(
                            path=str(args.screenshots / f"{label}-{name}.png"),
                            full_page=True,
                        )
                page.context.close()

            page = new_page(1280, 800)
            page.goto(origin + "/responses", wait_until="networkidle")

            # Keyboard: the first Tab reaches the skip link, which moves focus.
            page.keyboard.press("Tab")
            check(
                page.evaluate("document.activeElement.classList.contains('skip-link')"),
                "first Tab focuses the skip link",
            )
            page.keyboard.press("Enter")
            check(
                page.evaluate("location.hash") == "#main-content",
                "skip link targets the main content",
            )
            check(
                page.locator('.nav-item[aria-current="page"]').count() == 1
                and "/responses"
                in (
                    page.locator('.nav-item[aria-current="page"]').get_attribute("href")
                    or ""
                ),
                "active navigation item exposes aria-current",
            )
            unnamed = page.evaluate("""() => [...document.querySelectorAll(
                    'main input, main select, main textarea, main button')]
                  .filter(el => el.offsetParent !== null)
                  .filter(el => !(el.labels && el.labels.length)
                    && !el.getAttribute('aria-label')
                    && !el.getAttribute('aria-labelledby')
                    && !(el.tagName === 'BUTTON' && el.textContent.trim()))
                  .map(el => el.id || el.outerHTML.slice(0, 80))""")
            check(unnamed == [], f"form controls have accessible names {unnamed}")

            # Responses page content and states.
            body = page.locator("main").inner_text()
            check(
                "publicad" in body and "Doctoralia" in body,
                "manual publication notice is shown",
            )
            check(
                "Dr Sintético Parcial"
                in page.locator("#responses-collection-warning").inner_text(),
                "partial collection warning names the profile",
            )
            check(
                page.locator("#responses-list .response-card").count() == 25,
                "first page shows 25 items",
            )
            check(
                "Página 1 de 2" in page.locator("#responses-page-label").inner_text(),
                "page label",
            )
            page.click("#responses-next-page")
            page.wait_for_function(
                "document.querySelector('#responses-page-label').textContent.includes('Página 2')"
            )
            check(
                page.locator("#responses-list .response-card").count() == 7,
                "second page shows the rest",
            )

            page.fill("#responses-review-date-from", "2026-01-01")
            page.fill("#responses-review-date-to", "2026-01-10")
            page.click("text=Aplicar filtros")
            page.wait_for_function(
                "document.querySelectorAll('#responses-list .response-card').length === 10"
            )
            check(True, "review date filter narrows the queue to 10 items")
            check(
                "sem data publicada"
                in page.locator("#responses-filter-note").inner_text(),
                "undated reviews excluded by the filter are reported",
            )

            # Error state with retry.
            page.route(
                "**/api/workspace/responses?*",
                lambda route: route.fulfill(
                    status=500, body='{"error": "Falha simulada"}'
                ),
            )
            page.click("text=Aplicar filtros")
            page.wait_for_selector("#responses-list .state-error")
            check(True, "load failure renders a persistent error state")
            page.unroute("**/api/workspace/responses?*")
            page.click("#responses-list .state-error button")
            page.wait_for_selector("#responses-list .response-card")
            check(True, "retry recovers from the error state")
            page.context.close()

            # Copy works without the async clipboard API (plain HTTP on a LAN).
            page = new_page(375, 812, clipboard=False)
            page.goto(origin + "/responses", wait_until="networkidle")
            first = page.locator("#responses-list .response-card").first
            first.locator("textarea").fill("Resposta sintética para copiar")
            first.locator("button", has_text="Copiar").click()
            check(
                page.evaluate("window.__copied") == "Resposta sintética para copiar",
                "copy falls back when navigator.clipboard is unavailable",
            )
            check(
                "copiad" in page.locator("#responses-alert").inner_text().lower(),
                "copy feedback",
            )
            page.context.close()
            browser.close()
        check(page_errors == [], f"no uncaught page errors {page_errors[:5]}")

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
