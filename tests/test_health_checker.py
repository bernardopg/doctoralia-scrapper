"""
Testes para o health checker
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.health_checker import HealthChecker, HealthStatus
from tests.fixtures import MockConfig


class TestHealthChecker:
    """Testes para verificações de saúde do sistema"""

    def test_health_checker_initialization(self) -> None:
        """Testa se o health checker é inicializado corretamente"""
        config = MockConfig()
        checker = HealthChecker(config)

        assert checker is not None
        assert checker.config == config

    @pytest.mark.asyncio
    async def test_check_memory(self) -> None:
        """Testa verificação de memória"""
        config = MockConfig()
        checker = HealthChecker(config)

        result = await checker.check_memory()

        assert isinstance(result, HealthStatus)
        assert result.name == "memory"
        assert result.status in ["healthy", "degraded", "unhealthy"]
        assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_check_disk_space(self) -> None:
        """Testa verificação de espaço em disco"""
        config = MockConfig()
        checker = HealthChecker(config)

        result = await checker.check_disk_space()

        assert isinstance(result, HealthStatus)
        assert result.name == "disk_space"
        assert result.status in ["healthy", "degraded", "unhealthy"]
        assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_check_webdriver_mock(self) -> None:
        """Testa verificação do webdriver com mock"""
        config = MockConfig()
        checker = HealthChecker(config)

        with patch("selenium.webdriver.Chrome") as mock_driver:
            mock_instance = Mock()
            mock_driver.return_value = mock_instance

            result = await checker.check_webdriver()

            assert isinstance(result, HealthStatus)
            assert result.name == "webdriver"
            # Em caso de sucesso no mock, deve ser healthy
            assert result.status == "healthy"
            assert result.response_time_ms >= 0

            # Verifica se o driver foi fechado
            mock_instance.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_all(self) -> None:
        """Testa verificação completa de todos os componentes"""
        config = MockConfig()
        checker = HealthChecker(config)

        with patch.object(
            checker, "check_webdriver", new_callable=AsyncMock
        ) as mock_webdriver:
            mock_webdriver.return_value = HealthStatus(
                name="webdriver", status="healthy", response_time_ms=100.0
            )

            result = await checker.check_all()

            assert isinstance(result, dict)
            assert len(result) >= 2  # Pelo menos memory e disk_space

            for name, status in result.items():
                assert isinstance(status, HealthStatus)
                assert status.status in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_check_network_failure(self) -> None:
        """Testa comportamento em caso de falha de rede"""
        config = MockConfig()
        checker = HealthChecker(config)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = await checker.check_network()

            assert isinstance(result, HealthStatus)
            assert result.name == "network"
            assert result.status == "unhealthy"
            assert "Network error" in str(result.details)
