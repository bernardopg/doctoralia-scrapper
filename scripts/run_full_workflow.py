#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.config.settings import AppConfig
from src.logger import setup_logger
from src.response_generator import ResponseGenerator
from src.scraper import DoctoraliaScraper
from src.telegram_notifier import TelegramNotifier


def build_responses_from_data(
    data: Dict[str, Any], generator: ResponseGenerator
) -> List[Dict[str, Any]]:
    reviews = data.get("reviews", []) or []
    # Processar apenas sem resposta do médico
    reviews_to_process = [r for r in reviews if not r.get("doctor_reply")]
    responses: List[Dict[str, Any]] = []

    for i, review in enumerate(reviews_to_process, 1):
        response_text = generator.generate_response(review)
        responses.append(
            {
                "author": review.get("author", "Anônimo"),
                "comment": review.get("comment", ""),
                "date": review.get("date", ""),
                "rating": review.get("rating", ""),
                "review_id": review.get("id", i),
                "response": response_text,
            }
        )
    return responses


def main():
    parser = argparse.ArgumentParser(
        description="Run full workflow: scrape -> generate -> notify (with attachment)."
    )
    parser.add_argument("--url", required=True, help="Doctoralia profile URL to scrape")
    parser.add_argument(
        "--no-telegram", action="store_true", help="Skip Telegram notification"
    )
    args = parser.parse_args()

    config = AppConfig.load()
    logger = setup_logger("fullworkflow", config)

    logger.info("🚀 Full workflow iniciado para URL: %s", args.url)

    # 1) Scraping
    scraper = DoctoraliaScraper(config, logger)
    data = scraper.scrape_reviews(args.url)
    if not data:
        logger.error("❌ Falha no scraping. Abortando workflow.")
        raise SystemExit(1)

    # 2) Salvar dados crus
    saved_file = scraper.save_data(data)
    if saved_file:
        logger.info("💾 Dados salvos: %s", saved_file)

    # 3) Geração de respostas
    generator = ResponseGenerator(config, logger)
    responses = build_responses_from_data(data, generator)
    logger.info("🤖 Respostas geradas: %d", len(responses))

    # 4) Notificação no Telegram com anexo (se habilitado)
    if not args.no_telegram:
        notifier = TelegramNotifier(config, logger)
        ok = notifier.send_responses_generated(responses)
        logger.info("📨 Envio Telegram: %s", "sucesso" if ok else "falha")
    else:
        logger.info("📵 Telegram desabilitado por --no-telegram")

    # 5) Salvar arquivo combinado com respostas no mesmo JSON (opcional)
    try:
        if saved_file and responses:
            # Atualizar arquivo salvo com as respostas geradas por ID lógico
            # Observação: para simplicidade, vamos anexar um campo 'generated_responses'
            enriched = dict(data)
            enriched["generated_responses"] = responses
            enriched_file = Path(saved_file).with_name(
                Path(saved_file).stem + "_with_responses.json"
            )
            with open(enriched_file, "w", encoding="utf-8") as f:
                json.dump(enriched, f, ensure_ascii=False, indent=2)
            logger.info("💾 Arquivo enriquecido salvo: %s", enriched_file)
    except Exception as e:
        logger.warning("⚠️ Não foi possível salvar arquivo enriquecido: %s", e)

    logger.info("✅ Workflow concluído.")


if __name__ == "__main__":
    main()
