"""
Testes end-to-end do fluxo completo: scrape -> analyze -> generate -> notify.

Mocka apenas as fronteiras de I/O (rede do Selenium e HTTP do Telegram),
deixando a orquestração real do scraper, gerador de respostas, analisador de
qualidade e notifier exercitarem o pipeline inteiro em conjunto.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from src.response_generator import ResponseGenerator
from src.response_quality_analyzer import ResponseQualityAnalyzer
from src.scraper import DoctoraliaScraper
from src.telegram_notifier import TelegramNotifier
from tests.fixtures import MockConfig


DOCTOR_URL = "https://www.doctoralia.com.br/medico/especialidade/cidade"


@pytest.fixture
def scraped_payload() -> Dict[str, Any]:
    """Payload que o scraper produziria após uma extração bem-sucedida."""
    return {
        "doctor_name": "Dra. Bruna Pinto Gomes",
        "url": DOCTOR_URL,
        "reviews": [
            {
                "id": 1,
                "author": "Maria Silva",
                "comment": "Excelente atendimento, muito atenciosa e cuidadosa!",
                "rating": "5",
                "date": "2026-06-01",
                "doctor_reply": None,
            },
            {
                "id": 2,
                "author": "Carlos Souza",
                "comment": "A consulta atrasou bastante e me senti pouco ouvido.",
                "rating": "2",
                "date": "2026-06-05",
                "doctor_reply": None,
            },
            {
                "id": 3,
                "author": "Ana Pereira",
                "comment": "Já respondida pelo médico.",
                "rating": "4",
                "date": "2026-06-08",
                # Já possui resposta -> deve ser ignorada na geração.
                "doctor_reply": "Obrigado pela visita!",
            },
        ],
    }


def _build_responses(
    data: Dict[str, Any], generator: ResponseGenerator
) -> List[Dict[str, Any]]:
    """Replica a etapa de geração do workflow apenas para reviews sem resposta."""
    pending = [r for r in data.get("reviews", []) if not r.get("doctor_reply")]
    responses: List[Dict[str, Any]] = []
    for i, review in enumerate(pending, 1):
        text = generator.generate_response(review)
        responses.append(
            {
                "author": review.get("author", "Anônimo"),
                "comment": review.get("comment", ""),
                "rating": review.get("rating", ""),
                "review_id": review.get("id", i),
                "response": text,
            }
        )
    return responses


def test_full_pipeline_scrape_generate_analyze_notify(
    scraped_payload: Dict[str, Any], tmp_path
) -> None:
    """Exercita scrape -> generate -> analyze -> notify de ponta a ponta."""
    config = MockConfig()
    # Isola qualquer escrita em disco no diretório temporário do teste.
    config.data_dir = tmp_path
    config.base_dir = tmp_path
    logger = Mock()

    # --- 1) SCRAPE -------------------------------------------------------
    # Mocka só a fronteira de rede (uma única tentativa retorna o payload).
    scraper = DoctoraliaScraper(config, logger)
    with patch.object(
        scraper, "_process_single_scrape_attempt", return_value=scraped_payload
    ) as scrape_attempt:
        data = scraper.scrape_reviews(DOCTOR_URL)

    scrape_attempt.assert_called()
    assert data is not None
    assert data["doctor_name"] == "Dra. Bruna Pinto Gomes"
    assert len(data["reviews"]) == 3

    # --- 2) GENERATE -----------------------------------------------------
    generator = ResponseGenerator(config, logger)
    responses = _build_responses(data, generator)

    # Só os 2 reviews sem doctor_reply devem gerar resposta.
    assert len(responses) == 2
    assert {r["author"] for r in responses} == {"Maria Silva", "Carlos Souza"}
    for item in responses:
        assert isinstance(item["response"], str)
        assert item["response"].strip()

    # --- 3) ANALYZE ------------------------------------------------------
    analyzer = ResponseQualityAnalyzer()
    for item in responses:
        analysis = analyzer.analyze_response(
            item["response"], original_review=item["comment"]
        )
        assert 0 <= analysis.score.overall_score <= 100
        assert analysis.sentiment in {"positive", "negative", "neutral"}

    # --- 4) NOTIFY -------------------------------------------------------
    # Mocka o HTTP do Telegram; valida que o notifier é exercitado.
    notifier = TelegramNotifier(config, logger)
    with patch.object(notifier, "send_message", return_value=True) as send_message:
        ok = notifier.send_responses_generated(responses)

    assert ok is True
    send_message.assert_called_once()
    sent_body = send_message.call_args.args[0]
    # A mensagem enviada deve referenciar os autores processados.
    assert "Maria Silva" in sent_body
    assert "Carlos Souza" in sent_body


def test_pipeline_aborts_when_scrape_returns_nothing(tmp_path) -> None:
    """Scrape sem resultado encerra o pipeline sem gerar respostas."""
    config = MockConfig()
    config.data_dir = tmp_path
    config.base_dir = tmp_path
    logger = Mock()

    scraper = DoctoraliaScraper(config, logger)
    with patch.object(
        scraper, "_process_single_scrape_attempt", return_value=None
    ):
        data = scraper.scrape_reviews(DOCTOR_URL)

    assert not data
