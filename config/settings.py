import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TelegramConfig:
    token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = False


@dataclass
class ScrapingConfig:
    headless: bool = True
    timeout: int = 60
    delay_min: float = 2.0
    delay_max: float = 4.0
    max_retries: int = 5
    page_load_timeout: int = 45
    implicit_wait: int = 20
    explicit_wait: int = 30


@dataclass
class AppConfig:
    telegram: TelegramConfig
    scraping: ScrapingConfig
    base_dir: Path
    data_dir: Path
    logs_dir: Path

    @classmethod
    def load(cls) -> "AppConfig":
        base_dir = Path(__file__).parent.parent
        config_file = base_dir / "config" / "config.json"

        # Valores padrão
        telegram = TelegramConfig()
        scraping = ScrapingConfig()

        # Carregar configurações se existir
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                telegram = TelegramConfig(
                    token=data.get("telegram", {}).get("token"),
                    chat_id=data.get("telegram", {}).get("chat_id"),
                    enabled=bool(data.get("telegram", {}).get("token")),
                )

                scraping_data = data.get("scraping", {})
                scraping = ScrapingConfig(
                    headless=scraping_data.get("headless", True),
                    timeout=scraping_data.get("timeout", 60),
                    delay_min=scraping_data.get("delay_min", 2.0),
                    delay_max=scraping_data.get("delay_max", 4.0),
                    max_retries=scraping_data.get("max_retries", 5),
                    page_load_timeout=scraping_data.get("page_load_timeout", 45),
                    implicit_wait=scraping_data.get("implicit_wait", 20),
                    explicit_wait=scraping_data.get("explicit_wait", 30),
                )
            except Exception:
                pass

        return cls(
            telegram=telegram,
            scraping=scraping,
            base_dir=base_dir,
            data_dir=base_dir / "data",
            logs_dir=base_dir / "data" / "logs",
        )

    def save(self) -> None:
        config_file = self.base_dir / "config" / "config.json"
        config_file.parent.mkdir(exist_ok=True)

        data = {
            "telegram": {
                "token": self.telegram.token,
                "chat_id": self.telegram.chat_id,
            },
            "scraping": {
                "headless": self.scraping.headless,
                "timeout": self.scraping.timeout,
                "delay_min": self.scraping.delay_min,
                "delay_max": self.scraping.delay_max,
                "max_retries": self.scraping.max_retries,
                "page_load_timeout": self.scraping.page_load_timeout,
                "implicit_wait": self.scraping.implicit_wait,
                "explicit_wait": self.scraping.explicit_wait,
            },
            "updated_at": str(datetime.now()),
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
