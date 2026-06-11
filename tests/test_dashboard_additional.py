import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.dashboard import DashboardApp
from src.dashboard.auth import _validate_redirect_target
from src.dashboard.services import _clean_optional


class DummyHTTPResponse:
    def __init__(self, status_code=200, payload=None, text="OK"):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def build_dashboard(tmp_path):
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    config = SimpleNamespace(
        data_dir=str(data_dir),
        logs_dir=str(logs_dir),
        api=SimpleNamespace(port=8000),
        integrations=SimpleNamespace(api_url=None, api_public_url=None),
        security=SimpleNamespace(api_key=None),
        user_profile=None,
    )
    dashboard = DashboardApp(config=config, logger=MagicMock())
    dashboard.app.config.update({"TESTING": True})
    return dashboard


def build_authenticated_dashboard(tmp_path, bootstrap_password="bootstrap-secret"):
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    config = SimpleNamespace(
        data_dir=str(data_dir),
        logs_dir=str(logs_dir),
        api=SimpleNamespace(port=8000),
        integrations=SimpleNamespace(api_url=None, api_public_url=None),
        security=SimpleNamespace(
            api_key=bootstrap_password,
            webhook_signing_secret="webhook-secret",
            dashboard_auth_enabled=True,
            dashboard_password_hash=None,
            dashboard_session_secret="dashboard-session-secret",
            dashboard_session_ttl_minutes=90,
        ),
        user_profile=SimpleNamespace(
            display_name="Administrador",
            username="admin",
            favorite_profiles=[],
        ),
    )
    dashboard = DashboardApp(config=config, logger=MagicMock())
    dashboard.app.config.update({"TESTING": True, "AUTH_FORCE_ENABLED": True})
    dashboard.svc._get_runtime_config = MagicMock(return_value=config)
    dashboard.svc.call_api = MagicMock(
        return_value={
            "success": True,
            "auth_enabled": True,
            "password_configured": True,
            "bootstrap_password_enabled": True,
            "session_ttl_minutes": 90,
            "user": {"username": "admin"},
        }
    )
    return dashboard


def test_clean_optional_and_runtime_url_helpers(tmp_path, monkeypatch):
    dashboard = build_dashboard(tmp_path)
    dashboard.svc._get_runtime_config = MagicMock(
        return_value=SimpleNamespace(
            api=SimpleNamespace(port=8100),
            integrations=SimpleNamespace(
                api_url="  http://api.internal:8100  ",
                api_public_url=" https://public.example.com/base ",
            ),
            security=SimpleNamespace(api_key=" secret-api-key "),
        )
    )

    assert _clean_optional("  valor  ") == "valor"
    assert _clean_optional("   ") is None
    assert _clean_optional(None) is None
    assert dashboard.svc.get_api_base_url() == "http://api.internal:8100"
    assert dashboard.svc.get_api_docs_url() == "https://public.example.com/base/docs"
    assert dashboard.svc.get_api_key() == "secret-api-key"

    dashboard.svc._get_runtime_config = MagicMock(
        return_value=SimpleNamespace(
            api=SimpleNamespace(port=8200),
            integrations=SimpleNamespace(api_url=None, api_public_url=None),
            security=SimpleNamespace(api_key=None),
        )
    )
    monkeypatch.setenv("API_URL", " http://env-api:9000 ")
    monkeypatch.setenv("API_PUBLIC_URL", " https://env-public.example.com/api ")
    monkeypatch.setenv("API_KEY", " env-api-key ")

    assert dashboard.svc.get_api_base_url() == "http://env-api:9000"
    assert dashboard.svc.get_api_docs_url() == "https://env-public.example.com/api/docs"
    assert dashboard.svc.get_api_key() == "env-api-key"


def test_remote_settings_and_user_profile_fallbacks(tmp_path):
    dashboard = build_dashboard(tmp_path)

    dashboard.svc.call_api = MagicMock(
        return_value={
            "success": True,
            "settings": {"user_profile": {"username": "remote"}},
        }
    )
    assert dashboard.svc.get_user_profile_settings() == {"username": "remote"}

    dashboard.svc.call_api = MagicMock(return_value={"success": False})
    dashboard.svc._get_runtime_config = MagicMock(
        return_value=SimpleNamespace(
            user_profile=SimpleNamespace(
                display_name="Dra. Ana",
                username="dra-ana",
                favorite_profiles=[
                    SimpleNamespace(
                        name="Principal",
                        profile_url="https://example.com/profile",
                        specialty="Ginecologia",
                        notes="VIP",
                    )
                ],
            )
        )
    )
    local_profile = dashboard.svc.get_user_profile_settings()
    assert local_profile["display_name"] == "Dra. Ana"
    assert local_profile["favorite_profiles"][0]["name"] == "Principal"

    dashboard.svc._get_runtime_config = MagicMock(
        return_value=SimpleNamespace(user_profile=None)
    )
    assert dashboard.svc.get_user_profile_settings()["username"] == "admin"


def test_update_remote_settings_merges_existing_payload(tmp_path):
    dashboard = build_dashboard(tmp_path)
    dashboard.svc.call_api = MagicMock(
        side_effect=[
            {
                "success": True,
                "settings": {
                    "api": {"timeout": 5},
                    "user_profile": {"username": "old"},
                },
            },
            {"success": True, "settings": {"user_profile": {"username": "new"}}},
        ]
    )

    updated = dashboard.svc.update_remote_settings(
        {"user_profile": {"username": "new"}}
    )

    assert updated == {"user_profile": {"username": "new"}}
    dashboard.svc.call_api.assert_called_with(
        "/v1/settings",
        method="PUT",
        json={"api": {"timeout": 5}, "user_profile": {"username": "new"}},
    )

    dashboard.svc.call_api = MagicMock(return_value={"success": False})
    assert dashboard.svc.update_remote_settings({"user_profile": {}}) is None


@pytest.mark.parametrize(
    ("response", "side_effect"),
    [
        (DummyHTTPResponse(500, text="boom"), None),
        (None, requests.exceptions.ConnectionError()),
        (None, requests.exceptions.Timeout()),
        (None, RuntimeError("unexpected")),
    ],
)
def test_call_api_handles_http_errors_and_exceptions(tmp_path, response, side_effect):
    dashboard = build_dashboard(tmp_path)
    dashboard.svc._get_runtime_config = MagicMock(
        return_value=SimpleNamespace(
            api=SimpleNamespace(port=8000),
            integrations=SimpleNamespace(
                api_url="http://api.internal:8000", api_public_url=None
            ),
            security=SimpleNamespace(api_key="api-key"),
        )
    )

    with patch("src.dashboard.services.requests.request") as mock_request:
        if side_effect is not None:
            mock_request.side_effect = side_effect
        else:
            mock_request.return_value = response

        assert dashboard.svc.call_api("/v1/health") is None


def test_request_api_with_status_preserves_payload_and_status(tmp_path):
    dashboard = build_dashboard(tmp_path)
    dashboard.svc._get_runtime_config = MagicMock(
        return_value=SimpleNamespace(
            api=SimpleNamespace(port=8000),
            integrations=SimpleNamespace(
                api_url="http://api.internal:8000", api_public_url=None
            ),
            security=SimpleNamespace(api_key="api-key"),
        )
    )

    with patch("src.dashboard.services.requests.request") as mock_request:
        mock_request.return_value = DummyHTTPResponse(
            status_code=422,
            payload={"error": {"message": "payload inválido"}},
            text="unprocessable",
        )

        payload, status_code = dashboard.svc.request_api_with_status(
            "/v1/notifications/telegram/schedules",
            method="POST",
            json={"name": "teste"},
        )

    assert status_code == 422
    assert payload == {"error": {"message": "payload inválido"}}
    mock_request.assert_called_once()


def test_get_api_health_disconnected_uses_base_url(tmp_path):
    dashboard = build_dashboard(tmp_path)
    dashboard.svc.call_api = MagicMock(return_value=None)
    dashboard.svc.get_api_base_url = MagicMock(return_value="http://api.internal:8000")

    data = dashboard.svc.get_api_health()

    assert data["status"] == "disconnected"
    assert data["api_url"] == "http://api.internal:8000"


def test_api_performance_route_local_and_none_sources(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()
    dashboard.svc.get_api_metrics = MagicMock(return_value=None)
    dashboard.svc.performance_monitor = MagicMock()
    dashboard.svc.performance_monitor.get_summary.return_value = {"requests": 10}

    response = client.get("/api/performance")
    assert response.status_code == 200
    assert response.get_json() == {"source": "local", "data": {"requests": 10}}

    dashboard.svc.performance_monitor = None
    response = client.get("/api/performance")
    assert response.status_code == 200
    assert response.get_json()["source"] == "none"


def test_proxy_scrape_validation_errors(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()

    empty = client.post("/api/scrape", data="", content_type="application/json")
    assert empty.status_code == 400

    missing_url = client.post("/api/scrape", json={"include_analysis": True})
    assert missing_url.status_code == 400


def test_task_routes_and_user_profile_availability_errors(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()
    dashboard.svc.call_api = MagicMock(return_value=None)
    dashboard.svc.update_remote_settings = MagicMock(return_value=None)

    assert client.get("/api/tasks/123").status_code == 503
    assert client.get("/api/tasks").status_code == 503
    assert client.put("/api/user-profile", json={"username": "ana"}).status_code == 503


def test_toggle_favorite_profile_remove_and_validation(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()

    missing = client.post("/api/user-profile/favorites/toggle", json={})
    assert missing.status_code == 400

    dashboard.svc.get_user_profile_settings = MagicMock(
        return_value={
            "display_name": "Dra. Ana",
            "username": "dra-ana",
            "favorite_profiles": [
                {
                    "name": "Principal",
                    "profile_url": "https://example.com/profile",
                    "specialty": "Clinica",
                    "notes": None,
                }
            ],
        }
    )
    dashboard.svc.update_remote_settings = MagicMock(
        return_value={
            "user_profile": {
                "display_name": "Dra. Ana",
                "username": "dra-ana",
                "favorite_profiles": [],
            }
        }
    )

    response = client.post(
        "/api/user-profile/favorites/toggle",
        json={"profile_url": "https://example.com/profile"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["favorite"] is False

    dashboard.svc.update_remote_settings = MagicMock(return_value=None)
    unavailable = client.post(
        "/api/user-profile/favorites/toggle",
        json={"profile_url": "https://example.com/new-profile"},
    )
    assert unavailable.status_code == 503


def test_workspace_routes_cover_filters_and_error_shapes(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()
    dashboard.svc.get_user_profile_settings = MagicMock(
        return_value={
            "display_name": "Dra. Ana",
            "username": "dra-ana",
            "favorite_profiles": [{"profile_url": "https://example.com/profile"}],
        }
    )
    dashboard.svc.workspace_service = MagicMock()
    dashboard.svc.workspace_service.list_profiles.return_value = [{"profile_id": "p1"}]
    dashboard.svc.workspace_service.get_profile_detail.return_value = {
        "profile_id": "p1"
    }
    dashboard.svc.workspace_service.list_pending_responses.return_value = {"items": []}

    profiles = client.get("/api/workspace/profiles?date_from=2026-03-01")
    assert profiles.status_code == 200
    assert profiles.get_json() == {"profiles": [{"profile_id": "p1"}]}

    detail_missing = client.get("/api/workspace/profile")
    assert detail_missing.status_code == 400

    detail = client.get("/api/workspace/profile?profile_id=p1")
    assert detail.status_code == 200
    assert detail.get_json() == {"profile_id": "p1"}

    dashboard.svc.workspace_service.get_profile_detail.return_value = None
    not_found = client.get("/api/workspace/profile?profile_id=unknown")
    assert not_found.status_code == 404

    pending = client.get(
        "/api/workspace/responses?profile_id=p1&favorites_only=1&q=excelente"
    )
    assert pending.status_code == 200
    assert pending.get_json() == {"items": []}


def test_dashboard_auth_redirects_and_keeps_public_health_route(tmp_path):
    dashboard = build_authenticated_dashboard(tmp_path)
    client = dashboard.app.test_client()

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    protected_api = client.get("/api/stats")
    assert protected_api.status_code == 401
    assert protected_api.get_json() == {"error": "Authentication required"}

    public_health = client.get("/api/health")
    assert public_health.status_code == 200


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("/reports", "/reports"),
        ("/reports?period=week", "/reports"),
        ("https://evil.example/reports", None),
        ("//evil.example/reports", None),
        ("/\\evil.example", None),
        ("/reports\r\nLocation: https://evil.example", None),
        ("/missing", None),
        ("/api/stats", None),
    ],
)
def test_dashboard_redirect_targets_are_canonical_and_allowlisted(
    tmp_path, candidate, expected
):
    dashboard = build_authenticated_dashboard(tmp_path)

    with dashboard.app.test_request_context("/login"):
        assert _validate_redirect_target(candidate) == expected


def test_dashboard_login_redirects_to_allowlisted_page(tmp_path):
    dashboard = build_authenticated_dashboard(tmp_path)
    client = dashboard.app.test_client()

    with client.session_transaction() as session_state:
        session_state["csrf_token"] = "test-csrf-token"

    response = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "bootstrap-secret",
            "csrf_token": "test-csrf-token",
            "next": "/reports?period=week",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/reports")


def test_dashboard_login_session_and_logout_flow(tmp_path):
    dashboard = build_authenticated_dashboard(tmp_path)
    client = dashboard.app.test_client()

    with client.session_transaction() as session_state:
        session_state["csrf_token"] = "test-csrf-token"
        csrf_token = session_state["csrf_token"]

    invalid = client.post(
        "/login",
        data={"username": "admin", "password": "wrong", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert invalid.status_code == 200
    assert "Credenciais inválidas." in invalid.get_data(as_text=True)

    login = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "bootstrap-secret",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert login.status_code == 302
    assert login.headers["Location"].endswith("/")

    with client.session_transaction() as session_state:
        assert session_state["dashboard_authenticated"] is True
        assert session_state["dashboard_username"] == "admin"
        csrf_token = session_state["csrf_token"]

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.get_json()["authenticated"] is True

    index = client.get("/")
    assert index.status_code == 200

    logout = client.post(
        "/logout", data={"csrf_token": csrf_token}, follow_redirects=False
    )
    assert logout.status_code == 302
    assert logout.headers["Location"].endswith("/")

    after_logout = client.get("/", follow_redirects=False)
    assert after_logout.status_code == 302
    assert "/login" in after_logout.headers["Location"]


def test_dashboard_json_login_and_logout_endpoints(tmp_path):
    dashboard = build_authenticated_dashboard(tmp_path)
    dashboard.svc.request_api_with_status = MagicMock(
        return_value=(
            {
                "success": True,
                "message": "Dashboard login successful",
                "user": {"username": "admin"},
            },
            200,
        )
    )
    client = dashboard.app.test_client()
    client.get("/login")
    with client.session_transaction() as session_state:
        csrf_token = session_state["csrf_token"]

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "bootstrap-secret"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["authenticated"] is True
    assert payload["username"] == "admin"

    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 200
    assert logout.get_json()["success"] is True


def test_workspace_history_and_save_routes_validation_and_success(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()
    dashboard.svc.workspace_service = MagicMock()
    dashboard.svc.workspace_service.delete_snapshot.return_value = None
    dashboard.svc.workspace_service.save_generated_response.return_value = {
        "filename": "latest.json",
        "review_id": "r1",
    }

    missing_filename = client.post("/api/workspace/history/delete", json={})
    assert missing_filename.status_code == 400

    not_found = client.post(
        "/api/workspace/history/delete", json={"filename": "missing.json"}
    )
    assert not_found.status_code == 404

    invalid_save = client.post("/api/workspace/responses/save", json={})
    assert invalid_save.status_code == 400

    saved = client.post(
        "/api/workspace/responses/save",
        json={
            "profile_id": "p1",
            "review_id": "r1",
            "generated_response": "Obrigada pelo retorno!",
        },
    )
    assert saved.status_code == 200
    assert saved.get_json()["success"] is True

    dashboard.svc.workspace_service.save_generated_response.return_value = None
    not_saved = client.post(
        "/api/workspace/responses/save",
        json={
            "profile_id": "p1",
            "review_id": "r1",
            "generated_response": "Obrigada pelo retorno!",
        },
    )
    assert not_saved.status_code == 404


def test_proxy_ready_handles_http_statuses_and_errors(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()
    dashboard.svc.get_api_base_url = MagicMock(return_value="http://api.internal:8000")
    dashboard.svc.get_api_key = MagicMock(return_value="secret-key")

    with patch("src.dashboard.services.requests.get") as mock_get:
        mock_get.return_value = DummyHTTPResponse(200, payload={"status": "ok"})
        assert client.get("/api/ready").status_code == 200

        mock_get.return_value = DummyHTTPResponse(503, payload={"status": "degraded"})
        assert client.get("/api/ready").status_code == 503

        mock_get.return_value = DummyHTTPResponse(500, payload={"status": "boom"})
        assert client.get("/api/ready").status_code == 503

        mock_get.side_effect = requests.exceptions.ConnectionError()
        assert client.get("/api/ready").status_code == 503

        mock_get.side_effect = RuntimeError("unexpected")
        assert client.get("/api/ready").status_code == 503


def test_handle_quality_analysis_variants(tmp_path):
    dashboard = build_dashboard(tmp_path)
    client = dashboard.app.test_client()

    invalid_json = client.post(
        "/api/quality-analysis", data="not-json", content_type="application/json"
    )
    assert invalid_json.status_code == 400

    missing_response = client.post(
        "/api/quality-analysis", json={"original_review": "bom"}
    )
    assert missing_response.status_code == 400

    dashboard.svc.quality_analyzer = None
    unavailable = client.post("/api/quality-analysis", json={"response": "obrigada"})
    assert unavailable.status_code == 503

    score = MagicMock()
    score.to_dict.return_value = {"overall": 91}
    dashboard.svc.quality_analyzer = MagicMock()
    dashboard.svc.quality_analyzer.analyze_response.return_value = SimpleNamespace(
        score=score,
        strengths=["Clareza"],
        weaknesses=["Sem CTA"],
        suggestions=["Adicionar fechamento"],
        keywords=["empatia"],
        sentiment="positive",
        readability_score=88,
    )
    success = client.post(
        "/api/quality-analysis",
        json={"response": "Obrigada pela confianca", "original_review": "Excelente"},
    )
    assert success.status_code == 200
    assert success.get_json()["score"] == {"overall": 91}


def test_recent_activity_and_logs_helpers_cover_success_and_failures(tmp_path):
    dashboard = build_dashboard(tmp_path)

    good_file = tmp_path / "data" / "activity.json"
    good_file.write_text(
        json.dumps(
            {
                "doctor": {"name": "Dra. Ana"},
                "reviews": [{"rating": 5}, {"rating": 4}],
                "extraction_timestamp": "2026-03-25T10:00:00",
            }
        ),
        encoding="utf-8",
    )
    bad_file = tmp_path / "data" / "broken.json"
    bad_file.write_text("{not-json", encoding="utf-8")

    activities = dashboard.svc.get_recent_activities()
    assert len(activities) == 1
    assert activities[0]["doctor_name"] == "Dra. Ana"

    latest_log = tmp_path / "logs" / "latest.log"
    latest_log.write_text("linha 1\nlinha 2\nlinha 3\n", encoding="utf-8")
    assert dashboard.svc.get_recent_logs(2) == ["linha 2", "linha 3"]

    broken_dashboard = build_dashboard(tmp_path / "other")
    broken_dashboard.svc.config.logs_dir = str(tmp_path / "missing-logs")
    assert broken_dashboard.svc.get_recent_logs(2) == ["Não foi possível ler os logs"]


def test_export_helpers_and_run_cover_remaining_dashboard_helpers(tmp_path):
    dashboard = build_dashboard(tmp_path)
    valid_file = tmp_path / "data" / "20260325_01_dra_ana.json"
    valid_file.write_text(
        json.dumps(
            {
                "doctor_name": "Dra. Ana",
                "extraction_timestamp": "2026-03-25T10:00:00",
                "reviews": [
                    {
                        "id": "r1",
                        "author": "Ana",
                        "rating": 5,
                        "date": "2026-03-25",
                        "comment": "Excelente",
                        "generated_response": "Obrigada!",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    invalid_file = tmp_path / "data" / "broken.json"
    invalid_file.write_text("{not-json", encoding="utf-8")

    from src.dashboard.reports import _convert_to_csv
    from src.dashboard.services import _format_file_size

    exported = dashboard.svc.get_export_data()
    assert len(exported) == 1
    csv_text = _convert_to_csv(exported)
    assert "doctor_name" in csv_text
    assert "Dra. Ana" in csv_text

    files = dashboard.svc.get_data_files()
    valid_entry = next(
        item for item in files if item["name"] == "20260325_01_dra_ana.json"
    )
    assert valid_entry["doctor"] == "Dra Ana"
    assert valid_entry["date_str"] == "2026-03-25"

    assert _format_file_size(512) == "512 B"
    assert _format_file_size(2048) == "2.0 KB"
    assert _format_file_size(2 * 1024 * 1024) == "2.0 MB"

    summary = dashboard.svc.get_report_summary()
    assert summary["total_files"] == 2
    assert summary["total_reviews"] == 1
    assert summary["unique_doctors"] == 1

    with patch.object(dashboard.app, "run") as app_run:
        dashboard.run(host="0.0.0.0", port=5050, debug=True)
    app_run.assert_called_once_with(host="0.0.0.0", port=5050, debug=True)
