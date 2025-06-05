# Teste Configuration
"""Configuração para os testes"""

import sys
from pathlib import Path

import pytest

# Adicionar src ao path para imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_config():
    """Fixture com configuração de exemplo para testes"""
    from config.settings import AppConfig, ScrapingConfig, TelegramConfig

    telegram_config = TelegramConfig(
        token="test_token", chat_id="test_chat_id", enabled=False
    )

    scraping_config = ScrapingConfig(
        headless=True, timeout=30, delay_min=1.0, delay_max=2.0, max_retries=3
    )

    return AppConfig(
        telegram=telegram_config,
        scraping=scraping_config,
        base_dir=Path("/tmp/test"),
        data_dir=Path("/tmp/test/data"),
    )


@pytest.fixture
def mock_logger():
    """Fixture com logger mock para testes"""
    from unittest.mock import Mock

    return Mock()


@pytest.fixture
def sample_html():
    """Fixture com HTML de exemplo do Doctoralia"""
    return """
    <html>
        <body>
            <div class="review">
                <div class="review-content">Excelente atendimento!</div>
                <div class="rating">5</div>
                <div class="patient-name">João Silva</div>
            </div>
        </body>
    </html>
    """
