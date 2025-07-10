from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.response_generator import ResponseGenerator


@pytest.fixture
def response_generator():
    mock_config = MagicMock()
    mock_config.data_dir = Path("/tmp")
    return ResponseGenerator(config=mock_config, logger=None)


def test_generate_response(response_generator):
    # Adicione testes para verificar a geração de respostas
    review = {"author": "John Doe", "comment": "Great service!"}
    response = response_generator.generate_response(review)
    assert "John" in response
    assert "satisfeita" in response
    assert "atendimento" in response
