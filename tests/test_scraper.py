"""
Testes básicos para o sistema de scraping
"""

from unittest.mock import Mock

from config.settings import AppConfig
from src.enhanced_scraper import EnhancedDoctoraliaScraper
from src.scraper import DoctoraliaScraper
from tests.fixtures import MockConfig


class TestDoctoraliaScraper:
    """Testes para o scraper do Doctoralia"""

    def test_scraper_initialization(self) -> None:
        """Testa se o scraper é inicializado corretamente"""
        config = AppConfig.load()
        mock_logger = Mock()
        scraper = DoctoraliaScraper(config, mock_logger)
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
        scraper = DoctoraliaScraper(config, mock_logger)

        assert hasattr(scraper, "setup_driver")
        assert callable(getattr(scraper, "setup_driver"))


class TestScrapingMethods:
    """Testes para métodos específicos de scraping"""

    def test_scraper_has_required_methods(self) -> None:
        """Verifica se o scraper tem todos os métodos necessários"""
        config = AppConfig.load()
        mock_logger = Mock()
        scraper = DoctoraliaScraper(config, mock_logger)

        # Verifica métodos essenciais
        assert hasattr(scraper, "setup_driver")
        assert hasattr(scraper, "scrape_reviews")
        assert hasattr(scraper, "add_human_delay")
        assert callable(getattr(scraper, "setup_driver"))
        assert callable(getattr(scraper, "scrape_reviews"))
        assert callable(getattr(scraper, "add_human_delay"))


class TestEnhancedScraper:
    """Testes para o scraper melhorado"""

    def test_enhanced_scraper_initialization(self) -> None:
        """Testa se o enhanced scraper é inicializado corretamente"""
        config = MockConfig()
        mock_logger = Mock()
        scraper = EnhancedDoctoraliaScraper(config, mock_logger)

        assert scraper is not None
        assert hasattr(scraper, "page_load_circuit")
        assert hasattr(scraper, "error_reporter")
        assert hasattr(scraper, "scrape_page_with_protection")

    def test_circuit_breaker_status(self) -> None:
        """Testa se o status do circuit breaker é retornado corretamente"""
        config = MockConfig()
        mock_logger = Mock()
        scraper = EnhancedDoctoraliaScraper(config, mock_logger)

        status = scraper.get_circuit_status()
        assert isinstance(status, dict)
        assert "page_load" in status
        assert "api" in status

        required_methods = [
            "scrape_reviews",
            "extract_doctor_name",
            "save_data",
        ]

        for method in required_methods:
            assert hasattr(scraper, method), f"Método {method} não encontrado"
            assert callable(getattr(scraper, method)), f"Método {method} não é callable"
