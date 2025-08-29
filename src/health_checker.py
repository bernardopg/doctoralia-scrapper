"""
Health checker para monitorar a saúde do sistema
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


@dataclass
class HealthStatus:
    """Status de saúde de um componente"""

    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    response_time_ms: float
    details: Optional[str] = None


class HealthChecker:
    """Verifica a saúde de todos os componentes do sistema"""

    def __init__(self, config):
        self.config = config

    async def check_all(self) -> Dict[str, HealthStatus]:
        """Executa todos os health checks"""
        checks = [
            self.check_webdriver(),
            self.check_network(),
            self.check_disk_space(),
            self.check_memory(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        health_status = {}
        check_names = ["webdriver", "network", "disk_space", "memory"]

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                health_status[check_names[i]] = HealthStatus(
                    name=check_names[i],
                    status="unhealthy",
                    response_time_ms=0,
                    details=str(result),
                )
            elif isinstance(result, HealthStatus):
                health_status[result.name] = result

        return health_status

    async def check_webdriver(self) -> HealthStatus:
        """Verifica se o WebDriver está funcionando"""
        start = time.time()
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=options)
            driver.quit()

            response_time = (time.time() - start) * 1000
            return HealthStatus(
                name="webdriver", status="healthy", response_time_ms=response_time
            )
        except Exception as e:
            return HealthStatus(
                name="webdriver",
                status="unhealthy",
                response_time_ms=(time.time() - start) * 1000,
                details=str(e),
            )

    async def check_network(self) -> HealthStatus:
        """Verifica conectividade de rede"""
        import requests

        start = time.time()
        try:
            response = requests.get("https://www.doctoralia.com.br", timeout=10)
            if response.status_code == 200:
                response_time = (time.time() - start) * 1000
                return HealthStatus(
                    name="network", status="healthy", response_time_ms=response_time
                )
            else:
                return HealthStatus(
                    name="network",
                    status="degraded",
                    response_time_ms=(time.time() - start) * 1000,
                    details=f"HTTP {response.status_code}",
                )
        except Exception as e:
            return HealthStatus(
                name="network",
                status="unhealthy",
                response_time_ms=(time.time() - start) * 1000,
                details=str(e),
            )

    async def check_disk_space(self) -> HealthStatus:
        """Verifica espaço em disco"""
        import shutil

        start = time.time()
        try:
            total, used, free = shutil.disk_usage(self.config.data_dir)
            free_percent = (free / total) * 100

            if free_percent > 20:
                status = "healthy"
            elif free_percent > 10:
                status = "degraded"
            else:
                status = "unhealthy"

            return HealthStatus(
                name="disk_space",
                status=status,
                response_time_ms=(time.time() - start) * 1000,
                details=f"{free_percent:.1f}% free",
            )
        except Exception as e:
            return HealthStatus(
                name="disk_space",
                status="unhealthy",
                response_time_ms=(time.time() - start) * 1000,
                details=str(e),
            )

    async def check_memory(self) -> HealthStatus:
        """Verifica uso de memória"""
        import psutil

        start = time.time()
        try:
            memory = psutil.virtual_memory()

            if memory.percent < 80:
                status = "healthy"
            elif memory.percent < 90:
                status = "degraded"
            else:
                status = "unhealthy"

            return HealthStatus(
                name="memory",
                status=status,
                response_time_ms=(time.time() - start) * 1000,
                details=f"{memory.percent:.1f}% used",
            )
        except Exception as e:
            return HealthStatus(
                name="memory",
                status="unhealthy",
                response_time_ms=(time.time() - start) * 1000,
                details=str(e),
            )
