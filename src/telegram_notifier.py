from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

# Importar templates
try:
    from config.telegram_templates import TelegramTemplates
except ImportError:
    # Fallback para importação relativa
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.telegram_templates import TelegramTemplates


class TelegramNotifier:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def send_message(self, message: str) -> bool:
        """Envia mensagem via Telegram"""
        if not self.config.telegram.enabled:
            self.logger.debug("Telegram não configurado")
            return False

        url = f"https://api.telegram.org/bot{self.config.telegram.token}/sendMessage"
        data = {
            "chat_id": self.config.telegram.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            if response.status_code == 200:
                self.logger.info("Notificação enviada via Telegram")
                return True
            else:
                self.logger.error(f"Erro ao enviar notificação: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Erro ao conectar com Telegram: {e}")
            return False

    def send_document(self, file_path: Path, caption: str = "") -> bool:
        """Envia documento via Telegram"""
        if not self.config.telegram.enabled:
            self.logger.debug("Telegram não configurado")
            return False

        url = f"https://api.telegram.org/bot{self.config.telegram.token}/sendDocument"

        try:
            with open(file_path, 'rb') as file:
                files = {'document': file}
                data = {
                    "chat_id": self.config.telegram.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }

                response = requests.post(url, files=files, data=data, timeout=60)
                if response.status_code == 200:
                    self.logger.info(f"Documento enviado via Telegram: {file_path.name}")
                    return True
                else:
                    self.logger.error(f"Erro ao enviar documento: {response.status_code}")
                    return False
        except Exception as e:
            self.logger.error(f"Erro ao enviar documento via Telegram: {e}")
            return False

    def send_scraping_complete(self, data: Dict[str, Any], save_path: Path):
        """Envia notificação de scraping concluído"""
        message = TelegramTemplates.scraping_complete(data, save_path)
        return self.send_message(message)

    def send_responses_generated(self, responses: List[Dict[str, Any]]):
        """Envia notificação de respostas geradas"""
        message = TelegramTemplates.responses_generated(responses)
        return self.send_message(message)

    def send_responses_with_file(self, responses: List[Dict[str, Any]], file_path: Path):
        """Envia notificação de respostas geradas com arquivo anexado"""
        caption = TelegramTemplates.responses_generated_with_file(responses, file_path)
        return self.send_document(file_path, caption)

    def send_error(self, error_message: str, context: str = ""):
        """Envia notificação de erro"""
        message = TelegramTemplates.generic_error(error_message, context)
        return self.send_message(message)

    def send_daemon_started(self, interval_minutes: int):
        """Envia notificação de daemon iniciado"""
        message = TelegramTemplates.daemon_started(interval_minutes)
        return self.send_message(message)

    def send_daemon_stopped(self):
        """Envia notificação de daemon parado"""
        message = TelegramTemplates.daemon_stopped()
        return self.send_message(message)

    def send_generation_cycle_success(self, responses: List[Dict[str, Any]]):
        """Envia notificação de ciclo de geração bem-sucedido"""
        message = TelegramTemplates.generation_cycle_success(responses)
        return self.send_message(message)

    def send_generation_cycle_no_responses(self):
        """Envia notificação de ciclo sem novas respostas"""
        message = TelegramTemplates.generation_cycle_no_responses()
        return self.send_message(message)

    def send_daemon_error(self, error_message: str, context: str = "Daemon de geração automática"):
        """Envia notificação de erro do daemon"""
        message = TelegramTemplates.daemon_error(error_message, context)
        return self.send_message(message)

    def send_custom_message(self, title: str, content: str, emoji: str = "📢"):
        """Envia mensagem customizada"""
        message = TelegramTemplates.custom_message(title, content, emoji)
        return self.send_message(message)