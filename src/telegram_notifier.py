import re
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

# Importar templates
try:
    from config.telegram_templates import TelegramTemplates
except ImportError:
    # Fallback para importação relativa
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.telegram_templates import TelegramTemplates


class TelegramNotifier:
    def __init__(self, config: Any, logger: Any) -> None:
        self.config = config
        self.logger = logger

    def _sanitize_markdown(self, text: str) -> str:
        """Sanitiza texto para evitar problemas com Markdown do Telegram"""
        if not text:
            return text

        # Escapar caracteres especiais do Markdown
        text = re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

        # Mas não escapar os caracteres de formatação que queremos usar
        text = re.sub(r"\\\*\\\*([^*]+)\\\*\\\*", r"**\1**", text)  # Negrito
        text = re.sub(r"\\\*([^*]+)\\\*", r"*\1*", text)  # Itálico
        text = re.sub(r"\\`([^`]+)\\`", r"`\1`", text)  # Código inline

        return text

    def send_message(self, message: str, retry_count: int = 3) -> bool:
        """Envia mensagem via Telegram com retry automático"""
        if not self.config.telegram.enabled:
            self.logger.debug("Telegram não configurado")
            return False

        # Sanitizar mensagem para evitar problemas com Markdown
        message = self._sanitize_markdown(message)

        url = f"https://api.telegram.org/bot{self.config.telegram.token}/sendMessage"
        data = {
            "chat_id": self.config.telegram.chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,  # Evita preview de links
        }

        for attempt in range(retry_count):
            try:
                response = requests.post(url, data=data, timeout=30)

                if response.status_code == 200:
                    self.logger.info("✅ Notificação enviada via Telegram")
                    return True
                elif response.status_code == 429:  # Rate limit
                    retry_after = response.headers.get("Retry-After", "30")
                    self.logger.warning(
                        f"⚠️ Rate limit atingido, aguardando {retry_after}s"
                    )
                    time.sleep(int(retry_after))
                    continue
                elif (
                    response.status_code == 400
                ):  # Bad request (provavelmente erro de formatação)
                    self.logger.warning(
                        "⚠️ Erro de formatação Markdown, tentando sem parse_mode"
                    )
                    data["parse_mode"] = ""  # Tentar sem Markdown
                    response = requests.post(url, data=data, timeout=30)
                    if response.status_code == 200:
                        return True

                self.logger.error(
                    f"❌ Erro ao enviar notificação: {response.status_code} - {response.text}"
                )
                return False

            except requests.Timeout:
                if attempt < retry_count - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    self.logger.warning(
                        f"⏳ Timeout, tentando novamente em {wait_time}s (tentativa {attempt + 2}/{retry_count})"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error("❌ Timeout final ao conectar com Telegram")
                    return False
            except requests.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = 2**attempt
                    self.logger.warning(
                        f"⏳ Erro de conexão, tentando novamente em {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"❌ Erro final ao conectar com Telegram: {e}")
                    return False

        return False

    def send_document(
        self, file_path: Path, caption: str = "", retry_count: int = 3
    ) -> bool:
        """Envia documento via Telegram com retry automático"""
        if not self.config.telegram.enabled:
            self.logger.debug("Telegram não configurado")
            return False

        # Sanitizar caption
        caption = self._sanitize_markdown(caption)

        url = f"https://api.telegram.org/bot{self.config.telegram.token}/sendDocument"

        for attempt in range(retry_count):
            try:
                with open(file_path, "rb") as file:
                    files = {"document": file}
                    data = {
                        "chat_id": self.config.telegram.chat_id,
                        "caption": caption,
                        "parse_mode": "Markdown",
                    }

                    response = requests.post(url, files=files, data=data, timeout=60)
                    if response.status_code == 200:
                        self.logger.info(
                            f"✅ Documento enviado via Telegram: {file_path.name}"
                        )
                        return True
                    elif response.status_code == 429:  # Rate limit
                        retry_after = response.headers.get("Retry-After", "30")
                        self.logger.warning(
                            f"⚠️ Rate limit atingido, aguardando {retry_after}s"
                        )
                        time.sleep(int(retry_after))
                        continue

                    self.logger.error(
                        f"❌ Erro ao enviar documento: {response.status_code} - {response.text}"
                    )
                    return False

            except requests.Timeout:
                if attempt < retry_count - 1:
                    wait_time = 2**attempt
                    self.logger.warning(
                        f"⏳ Timeout no upload, tentando novamente em {wait_time}s"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error("❌ Timeout final no upload do documento")
                    return False
            except requests.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = 2**attempt
                    self.logger.warning(
                        f"⏳ Erro de conexão no upload, tentando novamente em {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"❌ Erro final no upload do documento: {e}")
                    return False
            except FileNotFoundError:
                self.logger.error(f"❌ Arquivo não encontrado: {file_path}")
                return False
            except Exception as e:
                self.logger.error(f"❌ Erro inesperado no upload: {e}")
                return False

        return False

    def send_scraping_complete(self, data: Dict[str, Any], save_path: Path) -> bool:
        """Envia notificação de scraping concluído"""
        message = TelegramTemplates.scraping_complete(data, save_path)
        return self.send_message(message)

    def send_responses_generated(self, responses: List[Dict[str, Any]]) -> bool:
        """Envia notificação de respostas geradas"""
        message = TelegramTemplates.responses_generated(responses)
        return self.send_message(message)

    def send_responses_with_file(
        self, responses: List[Dict[str, Any]], file_path: Path
    ) -> bool:
        """Envia notificação de respostas geradas com arquivo anexado"""
        caption = TelegramTemplates.responses_generated_with_file(responses, file_path)
        return self.send_document(file_path, caption)

    def send_error(self, error_message: str, context: str = "") -> bool:
        """Envia notificação de erro"""
        message = TelegramTemplates.generic_error(error_message, context)
        return self.send_message(message)

    def send_daemon_started(self, interval_minutes: int) -> bool:
        """Envia notificação de daemon iniciado"""
        message = TelegramTemplates.daemon_started(interval_minutes)
        return self.send_message(message)

    def send_daemon_stopped(self) -> bool:
        """Envia notificação de daemon parado"""
        message = TelegramTemplates.daemon_stopped()
        return self.send_message(message)

    def send_generation_cycle_success(self, responses: List[Dict[str, Any]]) -> bool:
        """Envia notificação de ciclo de geração bem-sucedido"""
        message = TelegramTemplates.generation_cycle_success(responses)
        return self.send_message(message)

    def send_generation_cycle_no_responses(self) -> bool:
        """Envia notificação de ciclo sem novas respostas"""
        message = TelegramTemplates.generation_cycle_no_responses()
        return self.send_message(message)

    def send_daemon_error(
        self, error_message: str, context: str = "Daemon de geração automática"
    ) -> bool:
        """Envia notificação de erro do daemon"""
        message = TelegramTemplates.daemon_error(error_message, context)
        return self.send_message(message)

    def send_custom_message(self, title: str, content: str, emoji: str = "📢") -> bool:
        """Envia mensagem customizada"""
        message = TelegramTemplates.custom_message(title, content, emoji)
        return self.send_message(message)

    def test_connection(self) -> bool:
        """Testa a conectividade com o Telegram"""
        if not self.config.telegram.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.config.telegram.token}/getMe"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get("ok"):
                    bot_name = bot_info["result"].get("first_name", "Bot")
                    self.logger.info(f"✅ Conexão com Telegram OK - Bot: {bot_name}")
                    return True

            self.logger.error(
                f"❌ Erro na conexão com Telegram: {response.status_code}"
            )
            return False

        except requests.RequestException as e:
            self.logger.error(f"❌ Erro de rede ao testar Telegram: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Erro inesperado ao testar Telegram: {e}")
            return False

    def validate_config(self) -> Dict[str, Any]:
        """Valida a configuração do Telegram"""
        issues = []

        if not self.config.telegram.token:
            issues.append("Token do bot não configurado")
        elif (
            len(self.config.telegram.token) < 45
        ):  # Tokens do Telegram têm pelo menos 45 caracteres
            issues.append("Token do bot parece inválido (muito curto)")

        if not self.config.telegram.chat_id:
            issues.append("Chat ID não configurado")
        elif not str(self.config.telegram.chat_id).lstrip("-").isdigit():
            issues.append("Formato do Chat ID inválido")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "config": {
                "token_configured": bool(self.config.telegram.token),
                "chat_id_configured": bool(self.config.telegram.chat_id),
                "enabled": self.config.telegram.enabled,
            },
        }
