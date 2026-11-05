"""Exercise rendering of untrusted review data in the responses view."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_responses_render_untrusted_data_as_text():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the JavaScript rendering regression")

    template = (
        Path(__file__).resolve().parents[1] / "templates/responses.html"
    ).read_text()
    script = template.split("<script>", 1)[1].split("</script>", 1)[0]
    harness = r"""
const vm = require('vm');
const fs = require('fs');
const source = fs.readFileSync(0, 'utf8');
const output = {innerHTML: ''};
const document = {
  getElementById: () => output,
  addEventListener: () => {},
};
const context = {document, console, dashboardReviewDate: () => '-'};
vm.createContext(context);
vm.runInContext(source, context);
context.renderResponses([{
  profile_id: 'profile', review_id: '1', doctor_name: '<img src=x onerror=alert(1)>',
  author: '<svg onload=alert(2)>', comment: '<img src=x onerror=alert(3)>',
  generated_response: '</textarea><img src=x onerror=alert(4)>',
  date: null, rating: 5, is_favorite: false,
}]);
const html = output.innerHTML;
if (html.includes('<img') || html.includes('<svg') ||
    !html.includes('&lt;img') || !html.includes('&lt;/textarea&gt;')) {
  throw new Error('Untrusted content was not escaped: ' + html);
}
"""
    subprocess.run([node, "-e", harness], input=script, text=True, check=True)


@pytest.mark.parametrize(
    ("filename", "start", "end", "invocation"),
    [
        (
            "profiles.html",
            "renderLatestReviews",
            "selectProfile",
            "renderLatestReviews([{author: attack, comment: attack, generated_response: attack}]);",
        ),
        (
            "history.html",
            "renderHistoryTable",
            "loadSnapshotHistory",
            "renderHistoryTable([{doctor_name: attack, specialty: attack, filename: attack, profile_url: attack}]);",
        ),
        (
            "reports.html",
            "renderTopProfiles",
            "renderCleanupCandidates",
            "renderTopProfiles([{doctor_name: attack, profile_url: attack}]);",
        ),
    ],
)
def test_dashboard_views_escape_untrusted_content(filename, start, end, invocation):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the JavaScript rendering regression")
    root = Path(__file__).resolve().parents[1] / "templates"
    base = (root / "base.html").read_text()
    helpers = base.split("    function dashboardEscape", 1)[1].split(
        "    const dashboardCsrfToken", 1
    )[0]
    template = (root / filename).read_text()
    function = (
        "function "
        + start
        + template.split("function " + start, 1)[1].split(
            (
                "  async function " + end
                if end in ("selectProfile", "loadSnapshotHistory")
                else "  function " + end
            ),
            1,
        )[0]
    )
    source = "function dashboardEscape" + helpers + function
    harness = r"""
const vm = require('vm');
const fs = require('fs');
const output = {innerHTML: ''};
const document = {getElementById: () => output};
const context = {document, attack: '<img src=x onerror=alert(1)>', historyLabel: () => '', formatDateTime: () => ''};
vm.createContext(context);
vm.runInContext(fs.readFileSync(0, 'utf8'), context);
vm.runInContext(process.argv[1], context);
if (output.innerHTML.includes('<img') || !output.innerHTML.includes('&lt;img')) {
  throw new Error('Untrusted content was not escaped: ' + output.innerHTML);
}
"""
    subprocess.run(
        [node, "-e", harness, invocation], input=source, text=True, check=True
    )


def test_review_date_does_not_shift_in_sao_paulo():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the JavaScript rendering regression")
    template = (Path(__file__).resolve().parents[1] / "templates/base.html").read_text()
    helper = (
        "function dashboardReviewDate"
        + template.split("function dashboardReviewDate", 1)[1].split(
            "    const dashboardCsrfToken", 1
        )[0]
    )
    script = (
        helper
        + "\nif (dashboardReviewDate('2026-10-19') !== '19/10/2026') process.exit(1);"
    )
    import os

    subprocess.run(
        [node, "-e", script], env={**os.environ, "TZ": "America/Sao_Paulo"}, check=True
    )


def test_responses_alert_renders_error_messages_as_text():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the JavaScript rendering regression")

    template = (
        Path(__file__).resolve().parents[1] / "templates/responses.html"
    ).read_text()
    script = template.split("<script>", 1)[1].split("</script>", 1)[0]
    harness = r"""
const vm = require('vm');
const fs = require('fs');
const source = fs.readFileSync(0, 'utf8');
const output = {innerHTML: ''};
const document = {
  getElementById: () => output,
  addEventListener: () => {},
};
const context = {document, console, setTimeout: () => {}};
vm.createContext(context);
vm.runInContext(source, context);
context.showResponsesAlert('Erro: <img src=x onerror=alert(1)>', 'error');
const html = output.innerHTML;
if (html.includes('<img') || !html.includes('&lt;img')) {
  throw new Error('Alert message was not escaped: ' + html);
}
"""
    subprocess.run([node, "-e", harness], input=script, text=True, check=True)
