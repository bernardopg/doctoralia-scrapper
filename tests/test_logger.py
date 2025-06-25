"""
Testes básicos para o sistema de logger
"""

from src.logger import setup_logger


class TestLogger:
    """Testes para o sistema de logging"""

    def test_logger_setup(self) -> None:
        """Testa se o logger é configurado corretamente"""
        logger = setup_logger()
        assert logger is not None
        assert logger.name == "doctoralia-scraper"

    def test_logger_with_custom_name(self) -> None:
        """Testa logger com nome customizado"""
        custom_name = "test-logger"
        logger = setup_logger(name=custom_name)
        assert logger is not None
        assert logger.name == custom_name

    def test_logger_levels(self) -> None:
        """Testa se o logger responde aos diferentes níveis"""
        logger = setup_logger()

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
        logger = setup_logger()

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
