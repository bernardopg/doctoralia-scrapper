"""
Fixtures para testes do projeto
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class MockTelegramConfig:
    """Mock Telegram config para testes"""

    token: str = "test_token"
    chat_id: str = "test_chat_id"
    enabled: bool = False


@dataclass
class MockScrapingConfig:
    """Mock scraping config para testes"""

    headless: bool = True
    page_load_timeout: int = 60
    implicit_wait: int = 10
    explicit_wait: int = 20
    delay_min: float = 1.5
    delay_max: float = 3.5
    max_retries: int = 3
    timeout: int = 60

    def get_wait_times(self) -> Dict[str, int]:
        """Return a dictionary of wait time configurations."""
        return {
            "page_load": self.page_load_timeout,
            "implicit": self.implicit_wait,
            "explicit": self.explicit_wait,
        }


@dataclass
class MockDelayConfig:
    """Mock delay config para testes"""

    human_like_min: float = 0.1
    human_like_max: float = 0.3
    retry_base: float = 0.5
    error_recovery: float = 1.0
    rate_limit_retry: float = 5.0
    page_load_retry: float = 1.0


class MockConfig:
    """
    Mock configuration class para testes.
    Contains scraping and data directory settings.
    """

    def __init__(self) -> None:
        self.telegram = MockTelegramConfig()
        self.scraping = MockScrapingConfig()
        self.delays = MockDelayConfig()
        # Adjust this path to your desired data directory
        self.base_dir = Path("./test_data")
        self.data_dir = Path("./test_data")
        self.logs_dir = Path("./test_data/logs")

    def get_data_path(self) -> Path:
        """Return the configured data directory path."""
        return self.data_dir
