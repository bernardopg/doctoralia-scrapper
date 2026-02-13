import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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

        # Escapar caracteres especiais do Markdown (pensado p/ parse_mode "Markdown")
        text = re.sub(r"([_*\[\]()~`>#+\\=|{}.!-])", r"\\\1", text)

        # Manter formatações desejadas (negrito/itálico/código inline)
        text = re.sub(r"\\\*\\\*([^*]+)\\\*\\\*", r"**\1**", text)  # Negrito
        text = re.sub(r"\\\*([^*]+)\\\*", r"*\1*", text)  # Itálico
        text = re.sub(r"\\`([^`]+)\\`", r"`\1`", text)  # Código inline

        return text

    def _get_parse_mode(self) -> str:
        """Obtém parse_mode da configuração, com fallback seguro."""
        try:
            pm = (self.config.telegram.parse_mode or "").strip()
            # Telegram aceita: "Markdown", "MarkdownV2", "HTML" ou vazio
            if pm in {"Markdown", "MarkdownV2", "HTML"}:
                return pm
            return ""
        except Exception:
            return ""

    def send_message(self, message: str, retry_count: int = 3) -> bool:
        """Envia mensagem via Telegram com retry automático"""
        if not self.config.telegram.enabled:
            self.logger.debug("Telegram não configurado")
            return False

        parse_mode = self._get_parse_mode()

        # Sanitizar mensagem para evitar problemas com Markdown
        # Obs.: se parse_mode != "Markdown", ainda assim sanitizar ajuda a evitar 400
        message = self._sanitize_markdown(message)

        url = f"https://api.telegram.org/bot{self.config.telegram.token}/sendMessage"
        data = {
            "chat_id": self.config.telegram.chat_id,
            "text": message,
            "parse_mode": parse_mode,
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
                ):  # Bad request (provável erro de formatação)
                    self.logger.warning(
                        "⚠️ Erro de formatação/parse_mode, tentando sem parse_mode"
                    )
                    # Tentar sem parse_mode
                    data.pop("parse_mode", None)
                    response = requests.post(url, data=data, timeout=30)
                    if response.status_code == 200:
                        self.logger.info(
                            "✅ Notificação enviada (fallback sem parse_mode)"
                        )
                        return True

                self.logger.error(
                    f"❌ Erro ao enviar notificação: {response.status_code} - {response.text}"
                )
                return False

            except requests.Timeout:
                if attempt < retry_count - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    self.logger.warning(
                        f"⏳ Timeout, tentando novamente em {wait_time}s "
                        f"(tentativa {attempt + 2}/{retry_count})"
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

        parse_mode = self._get_parse_mode()

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
                        "parse_mode": parse_mode,
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
                    elif response.status_code == 400:
                        self.logger.warning(
                            "⚠️ Erro de formatação/parse_mode no caption, "
                            "tentando sem parse_mode"
                        )
                        data.pop("parse_mode", None)
                        response = requests.post(
                            url, files=files, data=data, timeout=60
                        )
                        if response.status_code == 200:
                            self.logger.info(
                                "✅ Documento enviado (fallback sem parse_mode)"
                            )
                            return True

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
                        f"⏳ Erro de conexão no upload, tentando "
                        f"novamente em {wait_time}s: {e}"
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

    # -------------------- Anexo automático de respostas --------------------

    def _create_attachment_file(
        self, responses: List[Dict[str, Any]]
    ) -> Optional[Path]:
        """Cria arquivo (txt/json/csv) com as respostas para anexar junto da mensagem."""
        try:
            if not responses:
                return None

            responses_dir = self.config.data_dir / "responses"
            responses_dir.mkdir(parents=True, exist_ok=True)

            fmt = (self.config.telegram.attachment_format or "txt").lower()
            if fmt not in {"txt", "json", "csv"}:
                fmt = "txt"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = responses_dir / f"respostas_consolidadas_{timestamp}.{fmt}"

            # Normalizar conteúdo esperado
            # responses deve conter dicts com: author, comment, response, review_id (opcional: date, rating)
            if fmt == "json":
                payload = {
                    "generated_at": datetime.now().isoformat(),
                    "total": len(responses),
                    "items": responses,
                }
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

            elif fmt == "csv":
                cols = ["author", "date", "rating", "review_id", "comment", "response"]
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=cols)
                    writer.writeheader()
                    for r in responses:
                        writer.writerow(
                            {
                                "author": r.get("author", ""),
                                "date": r.get("date", ""),
                                "rating": r.get("rating", ""),
                                "review_id": r.get("review_id", ""),
                                "comment": r.get("comment", ""),
                                "response": r.get("response", ""),
                            }
                        )
            else:
                # txt - formato limpo e fácil de copiar
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("╔" + "═" * 58 + "╗\n")
                    f.write("║" + " " * 12 + "RESPOSTAS DOCTORALIA" + " " * 26 + "║\n")
                    f.write(
                        "║" + " " * 12 + "Dra. Bruna Pinto Gomes" + " " * 24 + "║\n"
                    )
                    f.write("╚" + "═" * 58 + "╝\n\n")
                    f.write(
                        f"📅 Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}\n"
                    )
                    f.write(f"📊 Total: {len(responses)} respostas\n")
                    f.write("\n" + "─" * 60 + "\n")

                    for i, r in enumerate(responses, 1):
                        author = r.get("author", "Paciente")
                        comment = r.get("comment", "")
                        date_str = r.get("date", "")
                        rating = r.get("rating", "")
                        response_text = r.get("response", "")

                        # Formatar data se disponível
                        if date_str and "T" in str(date_str):
                            try:
                                from datetime import datetime as dt

                                dt_obj = dt.fromisoformat(
                                    date_str.replace("-03:00", "")
                                )
                                date_formatted = dt_obj.strftime("%d/%m/%Y")
                            except Exception:
                                date_formatted = str(date_str)[:10]
                        else:
                            date_formatted = str(date_str)[:10] if date_str else ""

                        f.write(
                            f"\n┌─ RESPOSTA {i:02d} ─────────────────────────────────────────┐\n"
                        )
                        f.write(f"│ 👤 {author}\n")
                        if date_formatted:
                            f.write(f"│ 📆 {date_formatted}")
                            if rating:
                                f.write(f"  ⭐ {rating}/5")
                            f.write("\n")
                        f.write("│\n")
                        f.write("│ 💬 Comentário:\n")
                        f.write(f'│ "{comment}"\n')
                        f.write("│\n")
                        f.write("│ ✏️ Resposta para copiar:\n")
                        f.write("└" + "─" * 55 + "┘\n\n")
                        f.write(response_text)
                        f.write("\n\n" + "─" * 60 + "\n")

                    f.write("\n📋 INSTRUÇÕES:\n")
                    f.write(
                        '   1. Copie a resposta (texto após "Resposta para copiar")\n'
                    )
                    f.write("   2. Cole no Doctoralia no comentário correspondente\n")
                    f.write("   3. Personalize se necessário antes de publicar\n")
                    f.write("\n" + "═" * 60 + "\n")

            self.logger.info(f"📁 Arquivo de anexo criado: {file_path.name}")
            return file_path
        except Exception as e:
            self.logger.error(f"❌ Falha ao criar arquivo de anexo: {e}")
            return None

    # -------------------- Templates de alto nível --------------------

    def send_scraping_complete(self, data: Dict[str, Any], save_path: Path) -> bool:
        """Envia notificação de scraping concluído"""
        message = TelegramTemplates.scraping_complete(data, save_path)
        return self.send_message(message)

    def send_responses_generated(self, responses: List[Dict[str, Any]]) -> bool:
        """Envia notificação de respostas geradas.

        Se attach_responses_auto estiver habilitado, envia também o arquivo em
        formato configurado (txt/json/csv) junto à mensagem.
        """
        if self.config.telegram.attach_responses_auto and responses:
            attachment = self._create_attachment_file(responses)
            if attachment:
                caption = TelegramTemplates.responses_generated_with_file(
                    responses, attachment
                )
                return self.send_document(attachment, caption)

        # Fallback: somente mensagem
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
        # Se habilitado, tenta anexar arquivo com as respostas no envio
        if getattr(self.config.telegram, "attach_responses_auto", False) and responses:
            attachment = self._create_attachment_file(responses)
            if attachment:
                caption = TelegramTemplates.responses_generated_with_file(
                    responses, attachment
                )
                return self.send_document(attachment, caption)
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
        elif len(self.config.telegram.token) < 45:
            # Tokens do Telegram têm >= 45 chars
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
                "parse_mode": self._get_parse_mode(),
                "attach_responses_auto": getattr(
                    self.config.telegram, "attach_responses_auto", False
                ),
                "attachment_format": getattr(
                    self.config.telegram, "attachment_format", "txt"
                ),
            },
        }
