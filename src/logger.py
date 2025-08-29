import json
import logging
import sys
from datetime import datetime
from typing import Any


class ColoredFormatter(logging.Formatter):
    """Formatter com cores para diferentes níveis de log"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Aplicar cor baseada no nível
        if record.levelname in self.COLORS:
            levelname_color = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
            record.levelname = levelname_color

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Formatter para logs estruturados em JSON"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Adicionar contexto extra se disponível
        if hasattr(record, "context") and record.context:  # type: ignore
            log_entry["context"] = record.context  # type: ignore

        # Adicionar informações de exceção se disponível
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(
    name: str, config: Any, verbose: bool = False, structured: bool = False
) -> logging.Logger:
    """Configura logger com saída colorida e arquivo"""

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Limpar handlers existentes
    logger.handlers.clear()

    # Handler para arquivo (log completo)
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.logs_dir / f"{name}_{datetime.now().strftime('%Y%m')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")

    if structured:
        # Log estruturado em JSON para produção
        file_handler.setFormatter(JSONFormatter())
    else:
        # Log tradicional para desenvolvimento
        file_format = "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s"
        file_handler.setFormatter(logging.Formatter(file_format))

    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # Handler para console (saída colorida e limpa)
    console_handler = logging.StreamHandler(sys.stdout)
    if verbose:
        console_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    else:
        console_format = "%(levelname)s | %(message)s"

    console_handler.setFormatter(ColoredFormatter(console_format))
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(console_handler)

    # Handler para arquivo (log completo)
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.logs_dir / f"{name}_{datetime.now().strftime('%Y%m')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_format = (
        "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s"
    )
    file_handler.setFormatter(logging.Formatter(file_format))
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger
