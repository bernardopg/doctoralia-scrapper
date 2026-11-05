# Dashboard rendering audit (REL-04)

Base: `origin/main` 8921cfb, including #203. The existing escaping helpers
protect review text, textarea content, attributes and most inline event arguments.
This audit also found unescaped report counters and a job detail count, a favorite
link that accepted non-HTTP schemes, and favorite event arguments that did not
escape the surrounding single-quoted HTML attribute. Profile and task identifiers
are now URL encoded when inserted into request URLs.

## Reproduce

Install the project's Python dependencies in a virtual environment, then install
Playwright deliberately (it is not a production dependency):

```sh
python -m pip install playwright
python -m playwright install chromium
python scripts/test_dashboard_browser.py
python -m pytest -q tests/test_responses_rendering.py tests/test_dashboard.py tests/test_dashboard_additional.py
```

The browser runner starts the actual Flask dashboard on an ephemeral loopback
port with a temporary data directory, an exclusive test secret and authentication
disabled. It clears the inherited environment and overrides runtime configuration;
Python requests are blocked, browser API calls are fulfilled from synthetic
fixtures, and all other remote browser requests are aborted. It never submits
payloads to external services. Clipboard writes are explicitly mocked in the
browser; the operating system clipboard is not tested. No Redis or PostgreSQL is
used. The suite requires the application's Python dependencies and its NLTK
resources to be installed beforehand.

## Page and context matrix

| Page | Context and exercised flow |
| --- | --- |
| Base / overview | Shared Jinja rendering, dynamic favorite text and action summary; hostile markup remains text. |
| Responses | Dynamic review text, textarea, attribute and inline IDs; edit/save with hostile identifiers and legitimate text, mocked clipboard copy. |
| Profiles | Dynamic name and specialty, profile identifier in selection request; displayed hostile markup remains text. |
| History | Dynamic snapshot text and job detail, hostile identifier and count; detail opened in browser. |
| Reports | Dynamic summary counter, profile and inventory fixtures; hostile summary markup remains literal. |
| Minha Área | Dynamic favorite text, single-quoted event argument and URL; hostile identifier, hover and edit; `javascript:` and `data:` links omitted, HTTPS link retained. |
| Telegram schedule | Dynamic schedule name and inline ID; edit opened with hostile identifier. No notification is sent. |
| Settings and health | Pages loaded with simulated responses; no mutation or service health assertion. |

## Recorded run and limits

On 2026-11-05, headless Chromium **156.0.8078.4**, driven by Python
Playwright, passed the runner. Before the fix, the reports fixture created an
image element and its error handler incremented the execution sentinel. After
fixing it, the runner reports PASS with no dialog or sentinel execution; it also
checks literal text, generated links, and the saved response payload. Python
unit tests and formatting/type checks are separate from browser evidence.

The test uses a finite set of synthetic payloads, API responses and interactions;
it is not an exhaustive proof against XSS. It does not exercise a real backend,
production authentication, real clipboard permissions, mobile browsers, browser
extensions, external links, Telegram delivery, AI generation, or actual saved
snapshots. Settings and health receive smoke coverage only. The API schema may
normally restrict some malicious counter values, but rendering remains defensive
for historical or malformed data. Static third-party resources are blocked in
this run, and charts are stubbed rather than visually validated.
