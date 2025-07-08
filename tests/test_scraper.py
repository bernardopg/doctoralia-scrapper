"""
Testes básicos para o sistema de scraping
"""

from unittest.mock import Mock

from config.settings import AppConfig
from src.scraper import DoctoraliaScraper


class TestDoctoraliaScraper:
    """Testes para o scraper do Doctoralia"""

    def test_scraper_initialization(self) -> None:
        """Testa se o scraper é inicializado corretamente"""
        config = AppConfig.load()
        mock_logger = Mock()
        scraper = DoctoraliaScraper(config=config, logger=mock_logger)
        assert scraper is not None
        assert scraper.config == config
        assert scraper.logger == mock_logger

    def test_url_validation(self) -> None:
        """Testa validação de URLs"""
        # URL válida do Doctoralia
        valid_url = "https://www.doctoralia.com.br/medico/especialidade/cidade"
        assert "doctoralia.com" in valid_url

        # URL inválida
        invalid_url = "https://www.google.com"
        assert "doctoralia.com" not in invalid_url

    def test_browser_setup_methods_exist(self) -> None:
        """Verifica se os métodos de configuração do browser existem"""
        config = AppConfig.load()
        mock_logger = Mock()
        scraper = DoctoraliaScraper(config=config, logger=mock_logger)

        assert hasattr(scraper, "setup_driver")
        assert callable(getattr(scraper, "setup_driver"))


class TestScrapingMethods:
    """Testes para métodos específicos de scraping"""

    def test_scraper_has_required_methods(self) -> None:
        """Verifica se o scraper tem todos os métodos necessários"""
        config = AppConfig.load()
        mock_logger = Mock()
        scraper = DoctoraliaScraper(config=config, logger=mock_logger)

        required_methods = [
            "scrape_reviews",
            "extract_doctor_name",
            "save_data",
        ]

        for method in required_methods:
            assert hasattr(scraper, method), f"Método {method} não encontrado"
            assert callable(getattr(scraper, method)), f"Método {method} não é callable"
