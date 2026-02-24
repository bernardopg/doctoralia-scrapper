import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.dashboard import DashboardApp


@pytest.fixture
def app():
    dashboard = DashboardApp()
    dashboard.app.config.update(
        {
            "TESTING": True,
        }
    )
    yield dashboard.app


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200


def test_settings_route(client):
    response = client.get("/settings")
    assert response.status_code == 200


def test_history_route(client):
    response = client.get("/history")
    assert response.status_code == 200


def test_reports_route(client):
    response = client.get("/reports")
    assert response.status_code == 200


def test_health_check_page_route(client):
    response = client.get("/health-check")
    assert response.status_code == 200


@patch("src.dashboard.DashboardApp._get_api_health")
def test_api_health_route(mock_get_api_health, client):
    mock_get_api_health.return_value = {"status": "ok"}
    response = client.get("/api/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "dashboard" in data
    assert data["api"] == {"status": "ok"}


@patch("src.dashboard.DashboardApp._get_api_statistics")
def test_api_stats_route_api_success(mock_get_api_stats, client):
    mock_get_api_stats.return_value = {"total": 10}
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["source"] == "api"
    assert data["data"] == {"total": 10}


@patch("src.dashboard.DashboardApp._get_api_statistics")
@patch("src.dashboard.DashboardApp._get_scraper_stats")
def test_api_stats_route_fallback(mock_get_scraper_stats, mock_get_api_stats, client):
    mock_get_api_stats.return_value = None
    mock_get_scraper_stats.return_value = {"total": 5}
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["source"] == "local"
    assert data["data"] == {"total": 5}


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_scrape_route(mock_call_api, client):
    mock_call_api.return_value = {"task_id": "123"}
    response = client.post("/api/scrape", json={"url": "http://test.com"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"task_id": "123"}
    mock_call_api.assert_called_once_with(
        "/v1/scrape:run", method="POST", json={"url": "http://test.com"}
    )


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_scrape_route_api_unavailable(mock_call_api, client):
    mock_call_api.return_value = None
    response = client.post("/api/scrape", json={"url": "http://test.com"})
    assert response.status_code == 503


@patch("src.dashboard.DashboardApp._get_api_metrics")
def test_api_performance_route_api_success(mock_get_api_metrics, client):
    mock_get_api_metrics.return_value = {"latency": 100}
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["source"] == "api"
    assert data["data"] == {"latency": 100}


@patch("src.dashboard.DashboardApp._get_recent_activities")
def test_api_recent_activity_route(mock_get_recent_activities, client):
    mock_get_recent_activities.return_value = [{"id": 1}]
    response = client.get("/api/recent-activity")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == [{"id": 1}]


@patch("src.dashboard.DashboardApp._get_trend_data")
def test_api_trends_route(mock_get_trend_data, client):
    mock_get_trend_data.return_value = {
        "dates": ["2025-10-01", "2025-10-02"],
        "reviews": [10, 14],
        "scrapes": [1, 1],
    }
    response = client.get("/api/trends")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["source"] == "local"
    assert data["data"] == {
        "dates": ["2025-10-01", "2025-10-02"],
        "reviews": [10, 14],
        "scrapes": [1, 1],
    }


def test_get_trend_data_aggregates_reviews_per_day(tmp_path):
    file_day_one_a = tmp_path / "20251001_doctor_a.json"
    file_day_one_a.write_text(
        json.dumps(
            {
                "extraction_timestamp": "2025-10-01T10:30:00",
                "reviews": [{"id": 1}, {"id": 2}],
            }
        ),
        encoding="utf-8",
    )

    file_day_one_b = tmp_path / "20251001_doctor_b.json"
    file_day_one_b.write_text(
        json.dumps(
            {
                "extraction_timestamp": "2025-10-01T16:45:00",
                "total_reviews": 5,
                "reviews": [{"id": 1}],
            }
        ),
        encoding="utf-8",
    )

    file_day_two = tmp_path / "20251002_doctor_a.json"
    file_day_two.write_text(
        json.dumps(
            {
                "scraped_at": "2025-10-02T08:00:00",
                "reviews": [{"id": 1}, {"id": 2}, {"id": 3}],
            }
        ),
        encoding="utf-8",
    )

    config = SimpleNamespace(data_dir=str(tmp_path))
    dashboard = DashboardApp(config=config, logger=MagicMock())

    trends = dashboard._get_trend_data()

    assert trends["dates"] == ["2025-10-01", "2025-10-02"]
    assert trends["reviews"] == [7, 3]
    assert trends["scrapes"] == [2, 1]


@patch("src.dashboard.DashboardApp._handle_quality_analysis")
def test_api_quality_analysis_route(mock_handle_quality_analysis, client):
    mock_handle_quality_analysis.return_value = {"score": 90}
    response = client.post("/api/quality-analysis", json={"text": "test"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"score": 90}


@patch("src.dashboard.ScraperFactory.get_supported_platforms")
def test_api_platforms_route(mock_get_supported_platforms, client):
    mock_get_supported_platforms.return_value = ["doctoralia", "test"]
    response = client.get("/api/platforms")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"platforms": ["doctoralia", "test"]}


@patch("src.dashboard.DashboardApp._get_recent_logs")
def test_api_logs_route(mock_get_recent_logs, client):
    mock_get_recent_logs.return_value = ["log1", "log2"]
    response = client.get("/api/logs?lines=10")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"logs": ["log1", "log2"]}
    mock_get_recent_logs.assert_called_once_with(10)


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_task_status_route(mock_call_api, client):
    mock_call_api.return_value = {"status": "running"}
    response = client.get("/api/tasks/123")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"status": "running"}
    mock_call_api.assert_called_once_with("/v1/jobs/123")


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_list_tasks_route(mock_call_api, client):
    mock_call_api.return_value = [{"id": "123"}]
    response = client.get("/api/tasks?status=running")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == [{"id": "123"}]
    mock_call_api.assert_called_once_with("/v1/jobs?status=running")


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_get_settings_route(mock_call_api, client):
    mock_call_api.return_value = {"setting": "value"}
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"setting": "value"}
    mock_call_api.assert_called_once_with("/v1/settings")


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_update_settings_route(mock_call_api, client):
    mock_call_api.return_value = {"status": "updated"}
    response = client.put("/api/settings", json={"setting": "new_value"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"status": "updated"}
    mock_call_api.assert_called_once_with(
        "/v1/settings", method="PUT", json={"setting": "new_value"}
    )


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_validate_settings_route(mock_call_api, client):
    mock_call_api.return_value = {"valid": True}
    response = client.post("/api/settings/validate", json={"setting": "value"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"valid": True}
    mock_call_api.assert_called_once_with(
        "/v1/settings/validate", method="POST", json={"setting": "value"}
    )


# -------------------------------------------------------------------
# Reports endpoints
# -------------------------------------------------------------------


@patch("src.dashboard.DashboardApp._get_data_files")
def test_api_reports_files_route(mock_get_data_files, client):
    mock_get_data_files.return_value = [
        {"name": "20251001_doctor_a.json", "size": 1234}
    ]
    response = client.get("/api/reports/files")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {"files": [{"name": "20251001_doctor_a.json", "size": 1234}]}


@patch("src.dashboard.DashboardApp._get_report_summary")
def test_api_reports_summary_route(mock_get_report_summary, client):
    mock_get_report_summary.return_value = {
        "total_files": 5,
        "today_files": 1,
        "total_reviews": 100,
        "unique_doctors": 3,
    }
    response = client.get("/api/reports/summary")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["total_files"] == 5
    assert data["unique_doctors"] == 3


@patch("src.dashboard.DashboardApp._get_export_data")
def test_api_reports_export_json(mock_get_export_data, client):
    mock_get_export_data.return_value = [{"doctor_name": "Dr. Test"}]
    response = client.get("/api/reports/export/json")
    assert response.status_code == 200
    assert response.content_type.startswith("application/json")
    assert "attachment" in response.headers.get("Content-Disposition", "")
    data = json.loads(response.data)
    assert data == [{"doctor_name": "Dr. Test"}]


@patch("src.dashboard.DashboardApp._get_export_data")
def test_api_reports_export_csv(mock_get_export_data, client):
    mock_get_export_data.return_value = [
        {
            "doctor_name": "Dr. Test",
            "extraction_timestamp": "2025-10-01T10:00:00",
            "reviews": [
                {
                    "id": "1",
                    "author": "Ana",
                    "rating": 5,
                    "date": "2025-09-30",
                    "comment": "Great",
                }
            ],
        }
    ]
    response = client.get("/api/reports/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.content_type
    csv_text = response.data.decode("utf-8")
    assert "doctor_name" in csv_text
    assert "Dr. Test" in csv_text


def test_api_reports_export_invalid_format(client):
    response = client.get("/api/reports/export/xml")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


# -------------------------------------------------------------------
# Reports integration tests with real data files
# -------------------------------------------------------------------


def test_get_report_summary_with_real_data(tmp_path):
    today = __import__("datetime").datetime.now().strftime("%Y%m%d")
    file_today = tmp_path / f"{today}_doctor_a.json"
    file_today.write_text(
        json.dumps(
            {
                "doctor_name": "Dr. Ana",
                "reviews": [{"id": 1}, {"id": 2}],
            }
        ),
        encoding="utf-8",
    )

    file_old = tmp_path / "20240101_doctor_b.json"
    file_old.write_text(
        json.dumps(
            {
                "doctor_name": "Dr. Bruno",
                "reviews": [{"id": 1}],
            }
        ),
        encoding="utf-8",
    )

    config = SimpleNamespace(data_dir=str(tmp_path))
    dashboard = DashboardApp(config=config, logger=MagicMock())

    summary = dashboard._get_report_summary()

    assert summary["total_files"] == 2
    assert summary["today_files"] == 1
    assert summary["total_reviews"] == 3
    assert summary["unique_doctors"] == 2


def test_get_data_files_with_real_data(tmp_path):
    file_a = tmp_path / "20251001_12_doctor_test.json"
    file_a.write_text("{}", encoding="utf-8")

    config = SimpleNamespace(data_dir=str(tmp_path))
    dashboard = DashboardApp(config=config, logger=MagicMock())

    files = dashboard._get_data_files()

    assert len(files) == 1
    assert files[0]["name"] == "20251001_12_doctor_test.json"
    assert "size" in files[0]
    assert "modified" in files[0]


def test_get_scraper_stats_via_stats_service(tmp_path):
    file_a = tmp_path / "doctor_a.json"
    file_a.write_text(
        json.dumps(
            {
                "platform": "doctoralia",
                "total_reviews": 10,
                "reviews": [],
                "summary": {"average_rating": 4.5},
                "scraped_at": "2025-10-01T10:00:00",
            }
        ),
        encoding="utf-8",
    )

    config = SimpleNamespace(data_dir=str(tmp_path))
    dashboard = DashboardApp(config=config, logger=MagicMock())

    stats = dashboard._get_scraper_stats()

    assert stats["total_scraped_doctors"] == 1
    assert stats["total_reviews"] == 10
    assert stats["average_rating"] == 4.5
    assert stats["platform_stats"]["doctoralia"]["doctors"] == 1


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_get_settings_api_unavailable(mock_call_api, client):
    mock_call_api.return_value = None
    response = client.get("/api/settings")
    assert response.status_code == 503


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_update_settings_api_unavailable(mock_call_api, client):
    mock_call_api.return_value = None
    response = client.put("/api/settings", json={"setting": "val"})
    assert response.status_code == 503


@patch("src.dashboard.DashboardApp._call_api")
def test_proxy_validate_settings_api_unavailable(mock_call_api, client):
    mock_call_api.return_value = None
    response = client.post("/api/settings/validate", json={"setting": "val"})
    assert response.status_code == 503
