import json
import sys
from pathlib import Path
from typing import List

import pytest

import main as cli_main  # noqa: E402
from config.settings import (
    APIConfig,
    AppConfig,
    DelayConfig,
    ScrapingConfig,
    TelegramConfig,
)

EXAMPLE_URL = (
    "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"
)


@pytest.fixture()
def mock_config(tmp_path: Path, monkeypatch):
    """Provide an isolated AppConfig so CLI writes only into a temp directory."""
    cfg = AppConfig(
        telegram=TelegramConfig(token=None, chat_id=None, enabled=False),
        scraping=ScrapingConfig(
            headless=True,
            timeout=5,
            delay_min=0.1,
            delay_max=0.2,
            max_retries=1,
            page_load_timeout=5,
            implicit_wait=1,
            explicit_wait=1,
        ),
        delays=DelayConfig(
            human_like_min=0.0,
            human_like_max=0.0,
            retry_base=0.0,
            error_recovery=0.0,
            rate_limit_retry=0.0,
            page_load_retry=0.0,
        ),
        api=APIConfig(
            host="127.0.0.1",
            port=8000,
            debug=False,
            workers=1,
        ),
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
    )
    monkeypatch.setattr(
        cli_main, "AppConfig", type("_Wrapper", (), {"load": staticmethod(lambda: cfg)})
    )
    return cfg


def _sample_scrape_result(url: str):
    return {
        "url": url,
        "doctor_name": "Bruna Pinto Gomes",
        "extraction_timestamp": "2025-09-12T12:00:00",
        "reviews": [
            {
                "id": 1,
                "author": "Maria",
                "comment": "Excelente atendimento",
                "rating": 5,
                "date": "2025-09-10",
            },
            {
                "id": 2,
                "author": "Joao",
                "comment": "Muito bom",
                "rating": 4,
                "doctor_reply": "Obrigado!",
                "date": "2025-09-11",
            },
        ],
        "total_reviews": 2,
    }


@pytest.fixture()
def patch_scraper(monkeypatch):
    calls: List[str] = []

    class DummyScraper:
        def __init__(self, *a, **kw):
            pass

        def scrape_reviews(self, url: str):
            calls.append(url)
            return _sample_scrape_result(url)

        def save_data(self, data):  # mimic saving
            p = Path(
                data.get("doctor_name", "doctor").lower().replace(" ", "_") + ".json"
            )
            p.write_text(json.dumps(data), encoding="utf-8")
            return p

    monkeypatch.setattr(cli_main, "DoctoraliaScraper", DummyScraper)
    return calls


@pytest.fixture()
def patch_response_generator(monkeypatch):
    class DummyGenerator:
        def __init__(self, *a, **kw):
            pass

        def generate_response(self, review):
            return f"Resposta automática para {review.get('author', 'paciente')}"

    monkeypatch.setattr(cli_main, "ResponseGenerator", DummyGenerator)


def test_cli_scrape_success(mock_config, patch_scraper, monkeypatch, caplog):
    caplog.set_level("INFO")
    cli = cli_main.DoctoraliaCLI()
    cli.scrape(EXAMPLE_URL)
    # Verify scraper was called with provided URL
    assert patch_scraper == [EXAMPLE_URL]
    saved = list(Path.cwd().glob("bruna_pinto_gomes.json"))
    assert saved, "Expected saved data file in current directory"
    joined_logs = "\n".join(caplog.messages)
    assert "Scraping concluído" in joined_logs or "Scraping concluído" in joined_logs


def test_cli_run_generates_responses(
    mock_config, patch_scraper, patch_response_generator
):
    cli = cli_main.DoctoraliaCLI()
    cli.run(EXAMPLE_URL)
    # Ensure generated responses added only to review without doctor_reply
    saved_files = list(Path.cwd().glob("bruna_pinto_gomes.json"))
    assert saved_files
    data = json.loads(saved_files[-1].read_text(encoding="utf-8"))
    gen_reviews = [r for r in data["reviews"] if r.get("generated_response")]
    assert len(gen_reviews) == 1
    assert gen_reviews[0]["id"] == 1


def test_cli_scrape_failure_exit(mock_config, monkeypatch):
    class FailingScraper:
        def __init__(self, *a, **kw):
            pass

        def scrape_reviews(self, url: str):
            return None

    monkeypatch.setattr(cli_main, "DoctoraliaScraper", FailingScraper)
    cli = cli_main.DoctoraliaCLI()
    with pytest.raises(SystemExit) as exc:
        cli.scrape(EXAMPLE_URL)
    assert exc.value.code == 1


def test_main_entrypoint_dispatch(monkeypatch, mock_config):
    invoked = {}

    def fake_scrape(self, url):  # noqa: D401
        invoked["called"] = url
        # mimic success path minimal data
        return _sample_scrape_result(url)

    # Patch CLI method
    monkeypatch.setattr(cli_main.DoctoraliaCLI, "scrape", fake_scrape)
    # Build argv and invoke main
    argv_backup = sys.argv
    sys.argv = ["main.py", "scrape", "--url", EXAMPLE_URL]
    try:
        cli_main.main()
    finally:
        sys.argv = argv_backup

    assert invoked.get("called") == EXAMPLE_URL
