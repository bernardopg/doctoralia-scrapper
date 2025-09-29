from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.response_generator import ResponseGenerator


@pytest.fixture
def rg(tmp_path: Path):
    mock_config = MagicMock()
    mock_config.data_dir = tmp_path
    return ResponseGenerator(mock_config, logger=MagicMock())


@pytest.mark.parametrize(
    "author,expected",
    [
        ("João da Silva", "João"),
        ("AB", None),  # Too short
        ("", None),
        ("MARIA", None),  # Uppercase only
    ],
)
def test_extract_first_name(rg, author, expected):
    assert rg.extract_first_name(author) == expected


def test_identify_mentioned_qualities(rg):
    comment = (
        "Atendimento muito atenciosa e profissional, "
        "explicou todos os detalhes com eficiência."
    )
    qualities = rg.identify_mentioned_qualities(comment)
    # Should include mapped categories
    assert any(
        q in qualities
        for q in ["atenciosa", "profissional", "explicar_detalhes", "eficiente"]
    )


def test_load_and_save_processed_reviews(rg):
    ids = {1, 2, 3}
    rg.save_processed_reviews(ids)
    loaded = rg.load_processed_reviews()
    assert ids == loaded
