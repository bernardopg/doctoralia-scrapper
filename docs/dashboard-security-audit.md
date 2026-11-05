# Dashboard rendering audit (REL-04)

This audit covers dashboard rendering with synthetic fixtures. It corrected report
counters, job detail counts, favorite links and event arguments, and URL encoding
of profile, task and schedule identifiers. The browser checks exercise only the
flows listed below; they are not an exhaustive XSS audit.

## Reproduce

Linux must permit unprivileged user and network namespaces and provide `unshare`
and `/usr/bin/ip`. Install application dependencies and Playwright in a **separate**
test environment; do not install Playwright into the production environment. For
example, with an existing application virtualenv and Chromium cache:

```sh
python -m venv /tmp/rel04-browser-venv
/tmp/rel04-browser-venv/bin/python -m pip install -r requirements.txt playwright
PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright" /tmp/rel04-browser-venv/bin/python scripts/test_dashboard_browser.py
python -m pytest -q tests/test_responses_rendering.py tests/test_dashboard.py tests/test_dashboard_additional.py
```

The test environment must also provide the application's dependencies and NLTK
resources. Playwright needs a compatible cached Chromium or a browser installed
into a dedicated test cache. The runner re-executes itself with `unshare --user
--map-root-user --net`, activates only loopback, and refuses to run if the
namespace or interface checks fail. Flask binds an ephemeral port inside that
namespace. It checks Python socket failures for another loopback port and a
non-loopback destination, a successful connection to Flask, a blocked requests
proxy, browser fetch and WebSocket failure, and an unsuccessful popup. The
browser context blocks service workers and intercepts requests as an additional
layer; mocked API responses and the requests guard prevent real API operations.
The network namespace isolates the test from host network interfaces and host
loopback, but is not a filesystem sandbox.

The runner uses a temporary HOME and data directory, a test-only session secret,
and synthetic authentication configuration for both dashboard components from
startup through server shutdown. Before project imports, a Python audit hook
rejects opens of `.env`, `config.json` and common credentials paths; temporary
canaries verify rejection. `AppConfig.load` is patched to fail even if a caller
catches ordinary exceptions. This audit applies to Python file opens and is not
a general operating-system filesystem access control mechanism. No actual
credentials or persistent configuration are intentionally opened by this test.

## Page and context matrix

| Page | Exercised flow |
| --- | --- |
| Overview | Hostile counter as text, favorite text, and the positive numeric next-action branch. |
| Responses | Hostile review fields and distinct IDs; edit/save payload and simulated clipboard copy. |
| Profiles | Hostile names and reviews; profile selection and encoded query identifier. |
| History | Snapshot text and task detail with hostile count and encoded task path. |
| Reports | Four hostile operational counters and distinct top-profile and inventory text. |
| Minha Área | Favorite text and edit, unsafe URL schemes rejected and HTTPS retained. |
| Telegram schedule | Hostile schedule and history text and counters; edit/save with encoded schedule path, mocked API. |
| Settings and health | Smoke loading with simulated responses. |

The browser runs headless with a stubbed chart and a mocked clipboard. It does not
validate real authentication, API persistence, Telegram delivery, external
services, OS clipboard permissions, mobile browsers or chart appearance. Static
third-party resources are blocked. The runner never intentionally sends a
notification or payload outside the isolated namespace.
