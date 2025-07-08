"""
Testes básicos para o sistema de logger
"""

from unittest.mock import Mock
from pathlib import Path

from src.logger import setup_logger


class TestLogger:
    """Testes para o sistema de logging"""

    def _create_mock_config(self):
        """Cria um objeto mock para config com logs_dir"""
        mock_config = Mock()
        mock_config.logs_dir = Path("data/logs")
        return mock_config

    def test_logger_setup(self) -> None:
        """Testa se o logger é configurado corretamente"""
        mock_config = self._create_mock_config()
        logger = setup_logger(name="doctoralia-scraper", config=mock_config)
        assert logger is not None
        assert logger.name == "doctoralia-scraper"

    def test_logger_with_custom_name(self) -> None:
        """Testa logger com nome customizado"""
        custom_name = "test-logger"
        mock_config = self._create_mock_config()
        logger = setup_logger(name=custom_name, config=mock_config)
        assert logger is not None
        assert logger.name == custom_name

    def test_logger_levels(self) -> None:
        """Testa se o logger responde aos diferentes níveis"""
        mock_config = self._create_mock_config()
        logger = setup_logger(name="doctoralia-scraper", config=mock_config)

        # Testa se os métodos de logging existem
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")

        # Testa se são callable
        assert callable(logger.info)
        assert callable(logger.error)
        assert callable(logger.warning)
        assert callable(logger.debug)

    def test_logger_message_formatting(self) -> None:
        """Testa se o logger aceita diferentes tipos de mensagens"""
        mock_config = self._create_mock_config()
        logger = setup_logger(name="doctoralia-scraper", config=mock_config)

        # Testa com string simples
        try:
            logger.info("Teste de mensagem simples")
            logger.error("Teste de erro")
            logger.warning("Teste de warning")
        except Exception as e:
            assert False, f"Logger falhou com mensagem simples: {e}"

        # Testa com formatação
        try:
            logger.info("Teste com parâmetro: %s", "valor")
            logger.info(f"Teste com f-string: {'valor'}")
        except Exception as e:
            assert False, f"Logger falhou com formatação: {e}"
