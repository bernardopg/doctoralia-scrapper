from unittest.mock import MagicMock, patch

from src.jobs.tasks import scrape_and_process


def test_scrape_and_process_persists_snapshot_with_generated_responses(tmp_path):
    config = MagicMock()
    config.data_dir = tmp_path

    saved_path = tmp_path / "snapshot.json"

    scraper_result = {
        "doctor_name": "Dra. Ana",
        "url": "https://example.com/dra-ana",
        "extraction_timestamp": "2026-03-14T20:00:00",
        "reviews": [
            {
                "id": 1,
                "author": "Maria",
                "comment": "Excelente atendimento",
                "rating": 5,
                "date": "2026-03-13",
            }
        ],
        "total_reviews": 1,
    }

    generation_data = {
        "responses": [
            {
                "review_id": "1",
                "text": "Obrigada pelo carinho e pela confiança.",
                "provider": "local",
                "model": "template",
                "status": "generated",
            }
        ],
        "model": {"provider": "local"},
    }

    with patch("config.settings.AppConfig.load", return_value=config):
        with patch("src.scraper.DoctoraliaScraper") as mock_scraper_cls:
            with patch(
                "src.jobs.tasks._run_response_generation", return_value=generation_data
            ):
                mock_scraper = MagicMock()
                mock_scraper.scrape_reviews.return_value = scraper_result
                mock_scraper.save_data.return_value = saved_path
                mock_scraper_cls.return_value = mock_scraper

                result = scrape_and_process(
                    {
                        "doctor_url": "https://example.com/dra-ana",
                        "include_generation": True,
                        "include_analysis": False,
                        "generation_mode": "local",
                        "language": "pt-BR",
                    },
                    job_id="job-123",
                )

    assert result["status"] == "completed"
    assert result["reviews"][0]["id"] == "1"
    mock_scraper.save_data.assert_called_once()

    snapshot_payload = mock_scraper.save_data.call_args.args[0]
    assert snapshot_payload["doctor_name"] == "Dra. Ana"
    assert snapshot_payload["total_reviews"] == 1
    assert snapshot_payload["reviews"][0]["id"] == "1"
    assert (
        snapshot_payload["reviews"][0]["generated_response"]
        == "Obrigada pelo carinho e pela confiança."
    )
    assert snapshot_payload["url"] == "https://example.com/dra-ana"
