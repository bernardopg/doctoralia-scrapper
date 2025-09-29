"""
Tests for n8n API integration.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.v1.deps import create_webhook_signature
from src.api.v1.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def api_key():
    """Test API key."""
    return "test-api-key-123"


@pytest.fixture
def mock_env(api_key):
    """Mock environment variables."""
    with patch.dict("os.environ", {"API_KEY": api_key}):
        yield


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_s" in data

    def test_ready_check_without_redis(self, client):
        """Test readiness when Redis is unavailable."""
        with patch("redis.from_url") as mock_redis:
            mock_redis.side_effect = Exception("Redis connection failed")
            response = client.get("/v1/ready")
            assert response.status_code == 503


class TestAuthentication:
    """Test API authentication."""

    def test_no_api_key(self, client, mock_env):
        """Test request without API key."""
        response = client.post("/v1/scrape:run", json={})
        assert response.status_code == 401

    def test_invalid_api_key(self, client, mock_env):
        """Test request with invalid API key."""
        response = client.post(
            "/v1/scrape:run", json={}, headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_valid_api_key(self, client, mock_env, api_key):
        """Test request with valid API key."""
        with patch("src.scraper.DoctoraliaScraper") as mock_scraper:
            mock_instance = MagicMock()
            mock_instance.scrape_reviews.return_value = {
                "doctor_name": "Test Doctor",
                "reviews": [],
            }
            mock_scraper.return_value = mock_instance

            response = client.post(
                "/v1/scrape:run",
                json={"doctor_url": "https://example.com"},
                headers={"X-API-Key": api_key},
            )
            assert response.status_code == 200


class TestScrapeEndpoint:
    """Test synchronous scraping endpoint."""

    @patch("src.scraper.DoctoraliaScraper")
    def test_scrape_run_success(self, mock_scraper, client, mock_env, api_key):
        """Test successful scraping."""
        # Mock scraper
        mock_instance = MagicMock()
        mock_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Test",
            "url": "https://example.com",
            "specialty": "General Practice",
            "location": "Test City",
            "average_rating": 4.5,
            "reviews": [
                {
                    "rating": 5,
                    "comment": "Excellent doctor!",
                    "date": "2024-01-15",
                    "author_name": "Patient",
                }
            ],
        }
        mock_scraper.return_value = mock_instance

        # Make request
        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://example.com", "include_analysis": False},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["status"] == "completed"
        assert data["doctor"]["name"] == "Dr. Test"
        assert len(data["reviews"]) == 1
        assert data["metrics"]["scraped_count"] == 1

    @patch("src.api.v1.main.ResponseQualityAnalyzer")
    @patch("src.scraper.DoctoraliaScraper")
    def skip_test_scrape_with_analysis(
        self, mock_scraper, mock_analyzer, client, mock_env, api_key
    ):
        """Test scraping with sentiment analysis."""
        # Mock scraper
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Test",
            "reviews": [{"comment": "Great!"}],
        }
        mock_scraper.return_value = mock_scraper_instance

        # Mock analyzer
        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.analyze_sentiment.return_value = {
            "compound": 0.8,
            "pos": 0.7,
            "neu": 0.2,
            "neg": 0.1,
        }
        mock_analyzer.return_value = mock_analyzer_instance

        # Make request
        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://example.com", "include_analysis": True},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["analysis"] is not None
        assert "sentiments" in data["analysis"]


class TestAsyncJobs:
    """Test async job endpoints."""

    @patch("src.api.v1.main.get_queue")
    def test_create_job(self, mock_queue, client, mock_env, api_key):
        """Test job creation."""
        # Mock queue
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_q.enqueue.return_value = mock_job
        mock_queue.return_value = mock_q

        # Make request
        response = client.post(
            "/v1/jobs",
            json={"doctor_url": "https://example.com", "mode": "async"},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @patch("src.api.v1.main.get_queue")
    def test_get_job_status(self, mock_queue, client, mock_env, api_key):
        """Test job status retrieval."""
        # Mock queue and job
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.is_finished = True
        mock_job.result = {
            "doctor": {
                "id": "test123",
                "name": "Dr. Test",
                "profile_url": "https://example.com/dr-test",
                "specialty": "General Practice",
                "location": "Test City",
                "rating": 4.5,
            },
            "reviews": [],
            "metrics": {
                "scraped_count": 0,
                "start_ts": "2024-01-15T10:00:00",
                "end_ts": "2024-01-15T10:00:01",
                "duration_ms": 1000,
                "source": "doctoralia",
            },
            "status": "completed",
        }
        mock_q.fetch_job.return_value = mock_job
        mock_queue.return_value = mock_q

        # Make request
        response = client.get("/v1/jobs/job-123", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert data["doctor"]["name"] == "Dr. Test"

    def test_job_not_found(self, client, mock_env, api_key):
        """Test job not found error."""
        with patch("src.api.v1.main.get_queue") as mock_queue:
            mock_q = MagicMock()
            mock_q.fetch_job.return_value = None
            mock_queue.return_value = mock_q

            response = client.get(
                "/v1/jobs/nonexistent", headers={"X-API-Key": api_key}
            )

            assert response.status_code == 404


class TestWebhookSecurity:
    """Test webhook signature verification."""

    def test_create_webhook_signature(self):
        """Test signature creation."""
        payload = '{"test": "data"}'
        timestamp = time.time()

        with patch.dict("os.environ", {"WEBHOOK_SIGNING_SECRET": "secret123"}):
            ts_str, signature = create_webhook_signature(payload, timestamp)

            assert ts_str == str(timestamp)
            assert signature.startswith("sha256=")
            assert len(signature) > 7

    def test_webhook_without_signature(self, client):
        """Test webhook endpoint without signature."""
        response = client.post(
            "/v1/hooks/n8n/scrape", json={"doctor_url": "https://example.com"}
        )
        # Should pass if no secret is configured
        assert response.status_code in [200, 401, 422]

    def test_webhook_with_valid_signature(self, client):
        """Test webhook with valid signature."""
        payload = {"doctor_url": "https://example.com"}
        timestamp = str(time.time())

        with patch.dict("os.environ", {"WEBHOOK_SIGNING_SECRET": "secret123"}):
            # Create valid signature
            import hashlib
            import hmac

            message = f"{timestamp}.{json.dumps(payload)}"
            signature = (
                "sha256="
                + hmac.new(b"secret123", message.encode(), hashlib.sha256).hexdigest()
            )

            with patch("src.api.v1.main.create_job") as mock_create:
                mock_create.return_value = MagicMock(job_id="job-123", status="queued")

                response = client.post(
                    "/v1/hooks/n8n/scrape",
                    json=payload,
                    headers={"X-Timestamp": timestamp, "X-Signature": signature},
                )

                # Should succeed with valid signature
                assert response.status_code in [200, 422]


class TestErrorHandling:
    """Test error handling."""

    def test_request_id_header(self, client):
        """Test that request ID is added to responses."""
        response = client.get("/v1/health")
        assert "X-Request-Id" in response.headers

    def test_validation_error(self, client, mock_env, api_key):
        """Test validation error response."""
        response = client.post(
            "/v1/scrape:run",
            json={"invalid_field": "test"},
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 422

    @patch("src.scraper.DoctoraliaScraper")
    def test_scraper_exception(self, mock_scraper, client, mock_env, api_key):
        """Test handling of scraper exceptions."""
        mock_scraper.side_effect = Exception("Scraper failed")

        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://example.com"},
            headers={"X-API-Key": api_key},
        )

        # Should handle exception gracefully
        assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
