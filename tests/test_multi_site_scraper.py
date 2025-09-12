from pathlib import Path
from unittest.mock import MagicMock

from src.multi_site_scraper import (
    DoctoraliaScraper,
    DoctorData,
    ReviewData,
    ScraperFactory,
)
from tests.fixtures import MockConfig


def test_factory_returns_doctoralia_scraper():
    scraper = ScraperFactory.create_scraper(
        "https://www.doctoralia.com.br/medico/test", MockConfig(), MagicMock()
    )
    assert isinstance(scraper, DoctoraliaScraper)


def test_factory_unknown_returns_none():
    scraper = ScraperFactory.create_scraper(
        "https://www.example.com/profile", MockConfig(), MagicMock()
    )
    assert scraper is None


def test_supported_platforms():
    assert "doctoralia" in ScraperFactory.get_supported_platforms()


def test_save_data(tmp_path: Path):
    config = MockConfig()
    config.data_dir = tmp_path
    scraper = DoctoraliaScraper(config, MagicMock())
    doctor = DoctorData(
        name="Dra Teste",
        specialty="Ginecologia",
        location="BH",
        rating=4.5,
        total_reviews=1,
        platform="doctoralia",
        profile_url="https://www.doctoralia.com.br/test",
    )
    reviews = [
        ReviewData(
            author="Paciente",
            rating=5.0,
            comment="Excelente atendimento",
            date="2025-09-12",
            platform="doctoralia",
        )
    ]
    output_file = scraper.save_data(doctor, reviews)
    assert output_file is not None
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert """\"doctor\": {""" in content
    assert "Excelente atendimento" in content
