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
    # New customization options
    parse_mode: str = "Markdown"  # Options: "Markdown", "MarkdownV2", "HTML", ""
    attach_responses_auto: bool = True  # Auto-anexar arquivo de respostas quando houver
    attachment_format: str = "txt"  # "txt" | "json" | "csv"


@dataclass
class DelayConfig:
    """Configurações de delays para evitar detecção"""

    human_like_min: float = 1.0
    human_like_max: float = 3.0
    retry_base: float = 2.0
    error_recovery: float = 10.0
    rate_limit_retry: float = 60.0
    page_load_retry: float = 5.0


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
    delays: DelayConfig
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
        delays = DelayConfig()

        # Carregar configurações se existir
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                tg_data = data.get("telegram", {})
                telegram = TelegramConfig(
                    token=tg_data.get("token"),
                    chat_id=tg_data.get("chat_id"),
                    enabled=bool(tg_data.get("token")),
                    parse_mode=tg_data.get("parse_mode", "Markdown"),
                    attach_responses_auto=tg_data.get("attach_responses_auto", True),
                    attachment_format=tg_data.get("attachment_format", "txt"),
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
            delays=delays,
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
                "parse_mode": self.telegram.parse_mode,
                "attach_responses_auto": self.telegram.attach_responses_auto,
                "attachment_format": self.telegram.attachment_format,
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

    # --- Added method used by CLI (main.py) ---
    def validate(self) -> bool:
        """Basic validation used by CLI.

        Returns True if mandatory directories can be created and basic numeric
        constraints look sane. This keeps behaviour simple while avoiding
        AttributeErrors where the CLI previously expected a validate() method.
        """
        ok = True

        # Ensure data/log dirs exist
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            ok = False

        # Scraping delay sanity
        if self.scraping.delay_min < 0 or self.scraping.delay_max < 0:
            ok = False
        if self.scraping.delay_min > self.scraping.delay_max:
            ok = False

        return ok
