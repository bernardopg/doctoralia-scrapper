from types import SimpleNamespace
from unittest.mock import MagicMock

from bs4 import BeautifulSoup

from src.scraper import DoctoraliaScraper
from tests.fixtures import MockConfig

HTML = """
<div data-test-id='opinion-block'>
  <div data-score='5'></div>
  <time itemprop='datePublished' datetime='2025-09-12'></time>
  <h4><span>Maria Silva</span></h4>
  <p data-test-id='opinion-comment'> Atendimento excelente e muito atenciosa. </p>
  <div data-id='doctor-answer-content'><p>Resposta:</p><p>Obrigada pelo retorno!</p></div>
</div>
"""


def _build_scraper():
    config = MockConfig()
    logger = MagicMock()
    return DoctoraliaScraper(config, logger)


def test_individual_extractors_with_tag():
    scraper = _build_scraper()
    soup = BeautifulSoup(HTML, "html.parser")
    block = soup.find("div", {"data-test-id": "opinion-block"})
    assert scraper.extract_rating(block) == 5
    assert scraper.extract_date(block) == "2025-09-12"
    assert scraper.extract_author_name(block) == "Maria Silva"
    comment = scraper.extract_comment(block)
    assert comment and "Atendimento excelente" in comment
    assert scraper.extract_reply(block) == "Obrigada pelo retorno!"


def test_clean_text_and_missing_fields():
    scraper = _build_scraper()
    assert scraper.clean_text("  Olá   Mundo  \n") == "Olá Mundo"
    empty_soup = BeautifulSoup("<div></div>", "html.parser")
    assert scraper.extract_rating(empty_soup) is None
    assert scraper.extract_comment(empty_soup) is None


def test_extract_all_reviews_cache():
    scraper = _build_scraper()
    # Mock driver with page_source and current_url
    driver = SimpleNamespace(
        page_source=f"<html><body>{HTML}</body></html>",
        current_url="https://www.doctoralia.com.br/test",
    )
    scraper.driver = driver  # type: ignore
    first = scraper._extract_all_reviews()
    assert len(first) == 1
    # Change underlying HTML but keep URL - cache should return old result
    driver.page_source = "<html><body></body></html>"
    second = scraper._extract_all_reviews()
    assert second == first
