"""Synthetic regression coverage for explicitly selected snapshots."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

from src.dashboard.workspace import create_blueprint
from src.services.workspace_service import WorkspaceService


@pytest.fixture
def workspace(tmp_path):
    url = "https://www.doctoralia.com.br/synthetic"
    service = WorkspaceService(tmp_path)
    profile = service.make_profile_id(url, "Synthetic")
    common = {"url": url, "doctor_name": "Synthetic"}
    complete = {
        **common,
        "extraction_timestamp": "2026-01-01",
        "collection": {"status": "complete"},
        "reviews": [{"id": "old", "generated_response": "old draft"}],
    }
    partial = {
        **common,
        "extraction_timestamp": "2026-01-02",
        "collection": {
            "status": "partial",
            "expected_count": 50,
            "extracted_count": 35,
        },
        "reviews": [
            {
                "id": str(i),
                "comment": "review",
                "generated_response": "draft" if i == 34 else None,
            }
            for i in range(35)
        ],
    }
    for name, payload in [("complete.json", complete), ("partial.json", partial)]:
        (tmp_path / name).write_text(json.dumps(payload))
    return service, profile, complete


def test_selected_snapshot_reviews_and_edits_are_isolated(workspace):
    service, profile, complete = workspace
    assert (
        service.get_profile_detail(profile)["latest_reviews"][0]["review_id"] == "old"
    )
    detail = service.get_profile_detail(profile, snapshot="partial.json")
    assert len(detail["latest_reviews"]) == 35
    assert detail["selected_snapshot"]["collection"]["status"] == "partial"
    assert (
        len(service.list_pending_responses(profile, snapshot="partial.json")["items"])
        == 35
    )
    service.save_generated_response(profile, "34", "edited", snapshot="partial.json")
    assert (
        service.list_pending_responses(profile, snapshot="partial.json")["items"][-1][
            "generated_response"
        ]
        == "edited"
    )
    assert json.loads((service.data_dir / "complete.json").read_text()) == complete


def test_routes_validate_snapshot_and_render_links(workspace, tmp_path):
    service, profile, complete = workspace
    outside = tmp_path.parent / "outside-snapshot.json"
    outside.write_text(json.dumps(complete))
    (tmp_path / "link.json").symlink_to(outside)
    svc = SimpleNamespace(
        workspace_service=service,
        get_user_profile_settings=lambda: {},
        error_response=MagicMock(),
    )
    app = Flask(__name__)
    app.register_blueprint(create_blueprint(svc))
    client = app.test_client()
    args = {"profile_id": profile, "snapshot": "partial.json"}
    assert (
        len(
            client.get("/api/workspace/profile", query_string=args).json[
                "latest_reviews"
            ]
        )
        == 35
    )
    assert (
        client.post(
            "/api/workspace/responses/save",
            json={**args, "review_id": "34", "generated_response": "saved"},
        ).status_code
        == 200
    )
    assert any(
        i["generated_response"] == "saved"
        for i in client.get("/api/workspace/responses", query_string=args).json["items"]
    )
    for bad_profile, filename in [
        (profile, "missing.json"),
        ("other", "partial.json"),
        (profile, "../partial.json"),
        (profile, "link.json"),
    ]:
        query = {"profile_id": bad_profile, "snapshot": filename}
        assert (
            client.get("/api/workspace/profile", query_string=query).status_code == 404
        )
        assert (
            client.get("/api/workspace/responses", query_string=query).status_code
            == 404
        )
        assert (
            client.post(
                "/api/workspace/responses/save",
                json={**query, "review_id": "34", "generated_response": "bad"},
            ).status_code
            == 404
        )
    assert json.loads((tmp_path / "complete.json").read_text()) == complete
    history = open("templates/history.html", encoding="utf-8").read()
    assert "/profiles?profile_id=${encodeURIComponent(entry.profile_id)}" in history
    assert "/responses?profile_id=${encodeURIComponent(entry.profile_id)}" in history


def test_selected_responses_require_profile(workspace):
    service, _, _ = workspace
    with pytest.raises(ValueError, match="Snapshot não encontrado"):
        service.list_pending_responses(snapshot="partial.json")
