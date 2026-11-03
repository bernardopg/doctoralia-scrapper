from types import SimpleNamespace
from unittest.mock import MagicMock

from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException

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


def test_extract_current_portuguese_review_date():
    scraper = _build_scraper()
    block = BeautifulSoup(
        '<div><time class="small text-muted">19 de outubro de 2026</time></div>',
        "html.parser",
    ).div
    assert scraper.extract_date(block) == "2026-10-19"


def test_extract_date_handles_accent_and_invalid_dates():
    scraper = _build_scraper()
    for value, expected in [
        ("2 de março de 2024", "2024-03-02"),
        ("31 de fevereiro de 2024", None),
        ("ontem", None),
    ]:
        block = BeautifulSoup(f"<div><time>{value}</time></div>", "html.parser").div
        assert scraper.extract_date(block) == expected


def test_review_ids_follow_doctoralia_ids_when_order_changes():
    scraper = _build_scraper()
    first = HTML.replace(
        "data-test-id='opinion-block'", "data-test-id='opinion-block' data-id='123'"
    )
    second = HTML.replace(
        "data-test-id='opinion-block'", "data-test-id='opinion-block' data-id='456'"
    )
    driver = SimpleNamespace(
        page_source=first + second,
        current_url="https://www.doctoralia.com.br/test",
    )
    scraper.driver = driver  # type: ignore[assignment]
    assert [r["id"] for r in scraper._extract_all_reviews(force_refresh=True)] == [
        "doctoralia:123",
        "doctoralia:456",
    ]
    driver.page_source = second + first
    assert [r["id"] for r in scraper._extract_all_reviews(force_refresh=True)] == [
        "doctoralia:456",
        "doctoralia:123",
    ]


def _build_scraper():
    config = MockConfig()
    logger = MagicMock()
    return DoctoraliaScraper(config, logger)


def test_extract_doctor_name_from_current_header():
    scraper = _build_scraper()
    header = MagicMock()
    header.text = "Dra. Bruna Pinto Gomes"
    header.is_displayed.return_value = True
    driver = MagicMock()

    def find_element(by, selector):
        if selector == '[data-test-id="doctor-header-fullname"]':
            return header
        raise NoSuchElementException()

    driver.find_element.side_effect = find_element
    scraper.driver = driver
    assert scraper.extract_doctor_name() == "Dra. Bruna Pinto Gomes"


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


def test_extract_all_reviews_force_refresh_bypasses_cache():
    scraper = _build_scraper()
    driver = SimpleNamespace(
        page_source=f"<html><body>{HTML}</body></html>",
        current_url="https://www.doctoralia.com.br/test",
    )
    scraper.driver = driver  # type: ignore

    first = scraper._extract_all_reviews()
    assert len(first) == 1

    driver.page_source = "<html><body></body></html>"
    refreshed = scraper._extract_all_reviews(force_refresh=True)
    assert refreshed == []
