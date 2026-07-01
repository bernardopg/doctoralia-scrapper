#!/usr/bin/env python3
"""Smoke checks for the production Docker Compose stack.

The checks are intentionally read-only by default. Pass --send-telegram to run
Doctoralia's real Telegram notification endpoint as an explicit side effect.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ["docker-compose.yml", "docker-compose.prod.yml"]
REQUIRED_READY_CHECKS = {"redis", "queue", "templates", "nltk_vader", "selenium", "database"}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _compose_cmd(*args: str) -> list[str]:
    cmd = ["docker", "compose"]
    for compose_file in COMPOSE_FILES:
        cmd.extend(["-f", compose_file])
    cmd.extend(args)
    return cmd


def _run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _compose_cmd(*args),
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _request_json(
    method: str,
    url: str,
    *,
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(url, data=body, method=method, headers=headers)
    context = ssl._create_unverified_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{method} {url} returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _check_compose_services() -> None:
    result = _run("ps", "--all", "--format", "json")
    _require(result.returncode == 0, f"docker compose ps failed:\n{result.stdout}")

    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))

    services = {row["Service"]: row for row in rows}
    required = {"api", "worker", "dashboard", "redis", "db", "selenium", "n8n", "caddy"}
    missing = sorted(required - services.keys())
    _require(not missing, f"missing compose services: {missing}")

    unhealthy = []
    for service in sorted(required):
        row = services[service]
        state = row.get("State", "")
        health = row.get("Health", "")
        if state != "running":
            unhealthy.append(f"{service}: state={state!r}, health={health!r}")
        elif health and health != "healthy":
            unhealthy.append(f"{service}: state={state!r}, health={health!r}")
    _require(not unhealthy, "unhealthy services:\n" + "\n".join(unhealthy))


def _check_caddy_config() -> None:
    validate = _run("exec", "-T", "caddy", "caddy", "validate", "--config", "/etc/caddy/Caddyfile")
    _require(validate.returncode == 0, f"caddy validate failed:\n{validate.stdout}")

    adapted = _run("exec", "-T", "caddy", "caddy", "adapt", "--config", "/etc/caddy/Caddyfile")
    _require(adapted.returncode == 0, f"caddy adapt failed:\n{adapted.stdout}")
    config = json.loads(adapted.stdout)
    writer = (
        config.get("logging", {})
        .get("logs", {})
        .get("log0", {})
        .get("writer", {})
        .get("output")
    )
    _require(writer == "discard", f"Caddy app access log must discard sensitive headers; got {writer!r}")


def _check_ready(base_url: str, api_key: str) -> None:
    payload = _request_json("GET", f"{base_url}/v1/ready", api_key=api_key)
    _require(payload.get("ready") is True, f"/v1/ready is not ready: {payload}")
    checks = payload.get("checks") or {}
    missing = sorted(REQUIRED_READY_CHECKS - checks.keys())
    failing = sorted(name for name in REQUIRED_READY_CHECKS if checks.get(name) is not True)
    _require(not missing, f"/v1/ready missing checks: {missing}")
    _require(not failing, f"/v1/ready failing checks: {failing}")

    queue_details = ((payload.get("components") or {}).get("queue") or {}).get("details") or {}
    _require(queue_details.get("failed", 0) == 0, f"queue has failed jobs: {queue_details}")


def _check_telegram(base_url: str, api_key: str) -> None:
    payload = _request_json(
        "POST",
        f"{base_url}/v1/notifications/telegram/test",
        api_key=api_key,
        payload={"message": "Doctoralia Docker prod smoke test", "parse_mode": ""},
        timeout=45,
    )
    _require(payload.get("success") is True, f"telegram smoke failed: {payload}")
    result = payload.get("result") or {}
    _require(result.get("sent") is True, f"telegram smoke did not report sent=true: {payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("DOCTORALIA_BASE_URL", "https://localhost:8443"))
    parser.add_argument("--send-telegram", action="store_true", help="send a real Telegram test notification")
    args = parser.parse_args()

    _load_dotenv(ROOT / ".env")
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY is required in environment or .env")

    checks: list[tuple[str, Any]] = [
        ("compose services", _check_compose_services),
        ("caddy config", _check_caddy_config),
        ("readiness", lambda: _check_ready(args.base_url.rstrip("/"), api_key)),
    ]
    if args.send_telegram:
        checks.append(("telegram", lambda: _check_telegram(args.base_url.rstrip("/"), api_key)))

    for name, fn in checks:
        fn()
        print(f"ok: {name}")

    print("Docker production smoke checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI boundary with concise failure output.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
