#!/usr/bin/env python3
"""
Teste do enhanced scraper para debugging
"""

import asyncio

from config.settings import AppConfig
from src.enhanced_scraper import EnhancedDoctoraliaScraper
from src.health_checker import HealthChecker
from src.logger import setup_logger


async def test_enhanced_scraping():
    """Testa o enhanced scraper com debugging"""

    print("🔧 Carregando configuração...")
    config = AppConfig.load()
    logger = setup_logger("enhanced_test", config, verbose=True)

    print("🏥 Verificando saúde do sistema...")
    health_checker = HealthChecker(config)
    health_status = await health_checker.check_all()

    print("\n📊 Status de Saúde:")
    for name, status in health_status.items():
        print(f"  {name}: {status.status} ({status.response_time_ms:.1f}ms)")
        if status.details:
            print(f"    → {status.details}")

    print("\n🚀 Iniciando enhanced scraper...")
    scraper = EnhancedDoctoraliaScraper(config, logger)

    url = "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"

    try:
        print(f"🌐 Fazendo scraping de: {url}")
        data = scraper.scrape_page_with_protection(url)

        if data:
            print("✅ Sucesso! Dados extraídos:")
            print(f"  - Médico: {data.get('doctor_name', 'N/A')}")
            print(f"  - Total de reviews: {data.get('total_reviews', 0)}")
            print(f"  - Reviews extraídas: {len(data.get('reviews', []))}")

            if data.get("reviews"):
                print("📝 Amostras de reviews:")
                for i, review in enumerate(data.get("reviews", [])[:3]):
                    print(
                        f"  {i + 1}. {review.get('author', 'Anônimo')}: {review.get('comment', '')[:100]}..."
                    )
        else:
            print("❌ Nenhum dado retornado")

        # Status dos circuit breakers
        print("\n🔄 Status dos Circuit Breakers:")
        circuit_status = scraper.get_circuit_status()
        for name, status in circuit_status.items():
            print(f"  {name}: {status['state']} (falhas: {status['failure_count']})")

    except Exception as e:
        print(f"❌ Erro durante scraping: {e}")
        logger.error(f"Erro durante scraping: {e}", exc_info=True)

    print("\n✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(test_enhanced_scraping())
