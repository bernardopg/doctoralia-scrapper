#!/usr/bin/env python3
"""
Templates para mensagens do Telegram
Permite personalização fácil das notificações
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _clean_md(text: str) -> str:
    """Remove caracteres problemáticos básicos do Markdown simples do Telegram."""
    if not text:
        return text
    return (
        text.replace("*", "")
        .replace("_", "")
        .replace("`", "")
        .replace("[", "")
        .replace("]", "")
    )


class TelegramTemplates:
    """Templates personalizáveis para mensagens do Telegram"""

    @staticmethod
    def daemon_started(interval_minutes: int) -> str:
        """Template para notificação de daemon iniciado"""
        return f"""🔄 *Daemon Automático Iniciado*

⏱️ *Intervalo:* {interval_minutes} min
🧠 *Função:* Geração automática de respostas
📅 *Iniciado em:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

✅ Sistema rodando em segundo plano
📌 Dica: Você pode interromper a qualquer momento pelo servidor."""

    @staticmethod
    def daemon_stopped() -> str:
        """Template para notificação de daemon parado"""
        return f"""🛑 *Daemon Automático Finalizado*

📅 *Finalizado em:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

ℹ️ Execuções agendadas foram interrompidas
📌 Para retomar, inicie o daemon novamente."""

    @staticmethod
    def generation_cycle_success(responses: List[Dict[str, Any]]) -> str:
        """Template para ciclo de geração bem-sucedido"""
        total = len(responses)
        preview_limit = 3

        message = f"""🤖 *Doctoralia — Respostas Geradas com Sucesso*

📊 *Resumo do Ciclo*
• Total de respostas: *{total}*
• Arquivos em `data/responses/`
• Processo concluído sem erros

📝 *Últimos comentários processados*:"""

        for i, response in enumerate(responses[:preview_limit], 1):
            author = _clean_md(response.get("author", "Anônimo"))
            comment = _clean_md(response.get("comment", "") or "")
            comment_preview = (
                comment[:80] + "..."
                if len(comment) > 80
                else (comment or "Comentário vazio")
            )
            message += f"\n{i}. *{author}*: {comment_preview}"

        if total > preview_limit:
            message += f"\n… e mais {total - preview_limit} resposta(s)"

        message += f"""

🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔔 As respostas já estão prontas para copiar/colar no Doctoralia."""
        return message

    @staticmethod
    def generation_cycle_no_responses() -> str:
        """Template para ciclo sem novas respostas"""
        return f"""ℹ️ *Doctoralia — Ciclo Automático*

📊 *Status:* Nenhuma nova resposta necessária
✅ Todos os comentários recentes já possuem resposta

🗓️ *Verificação:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
🔄 Próxima checagem ocorrerá automaticamente."""

    @staticmethod
    def daemon_error(
        error_message: str, context: str = "Daemon de geração automática"
    ) -> str:
        """Template para erros do daemon"""
        return f"""❌ *Doctoralia — Erro no Daemon*

🔎 *Contexto:* {context}
💥 *Erro:* {error_message}

🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

⚠️ Verifique os logs para detalhes e considere reiniciar o daemon."""

    @staticmethod
    def scraping_complete(data: Dict[str, Any], save_path: Path) -> str:
        """Template para scraping concluído"""
        doctor_name = _clean_md(data.get("doctor_name") or "Médico")
        total_reviews = int(data.get("total_reviews", 0))
        with_replies = len(
            [r for r in data.get("reviews", []) if r.get("doctor_reply")]
        )
        without_replies = max(0, total_reviews - with_replies)

        status_line = (
            "🎯 *Há comentários prontos para resposta!*"
            if without_replies > 0
            else "✅ *Todos os comentários já possuem resposta.*"
        )
        return f"""🏥 *Doctoralia — Scraping Concluído*

👨‍⚕️ *Médico:* {doctor_name}
📈 *Total de comentários:* {total_reviews}
💬 *Com respostas:* {with_replies}
🕳️ *Sem respostas:* {without_replies}

📁 *Arquivo:* `{save_path.name}`
🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

{status_line}"""

    @staticmethod
    def responses_generated(responses: List[Dict[str, Any]]) -> str:
        """Template para respostas geradas manualmente"""
        total = len(responses)
        preview_limit = 5

        message = f"""🤖 *Doctoralia — Respostas Geradas*

📊 *Resumo*
• Total: *{total}* resposta(s)
• Arquivos salvos em `data/responses/`

📝 *Comentários processados*:"""

        for i, response in enumerate(responses[:preview_limit], 1):
            author = _clean_md(response.get("author", "Anônimo"))
            comment = _clean_md(response.get("comment", "") or "")
            comment_preview = (
                comment[:80] + "..."
                if len(comment) > 80
                else (comment or "Comentário vazio")
            )
            message += f"\n{i}. *{author}*: {comment_preview}"

        if total > preview_limit:
            message += f"\n… e mais {total - preview_limit} resposta(s)"

        message += f"""

🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔔 Copie e cole as respostas no Doctoralia."""
        return message

    @staticmethod
    def responses_generated_with_file(
        responses: List[Dict[str, Any]], file_path: Path
    ) -> str:
        """Template para respostas geradas com arquivo anexado"""
        total = len(responses)
        preview_limit = 3

        message = f"""🤖 *Doctoralia — Respostas Geradas*

📊 *Resumo*
• Total: *{total}* resposta(s)
• Arquivo consolidado anexado
• Conteúdo pronto para copiar/colar

📝 *Comentários processados*:"""

        for i, response in enumerate(responses[:preview_limit], 1):
            author = _clean_md(response.get("author", "Anônimo"))
            comment = _clean_md(response.get("comment", "") or "")
            comment_preview = (
                comment[:80] + "..."
                if len(comment) > 80
                else (comment or "Comentário vazio")
            )
            message += f"\n{i}. *{author}*: {comment_preview}"

        if total > preview_limit:
            message += f"\n… e mais {total - preview_limit} resposta(s)"

        message += f"""

📎 *Arquivo:* `{file_path.name}`
🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔔 Abra o arquivo anexado e copie as respostas para o Doctoralia."""
        return message

    @staticmethod
    def generic_error(error_message: str, context: str = "") -> str:
        """Template para erros genéricos"""
        return f"""❌ *Doctoralia — Erro*

🔎 *Contexto:* {context}
💥 *Erro:* {error_message}

🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""

    @staticmethod
    def custom_message(title: str, content: str, emoji: str = "📢") -> str:
        """Template para mensagens customizadas"""
        return f"""{emoji} *{_clean_md(title)}*

{_clean_md(content)}

🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""


# Configurações para personalização rápida
class NotificationConfig:
    """Configurações para personalizar notificações"""

    # Emojis principais
    EMOJIS = {
        "daemon_start": "🔄",
        "daemon_stop": "🛑",
        "success": "✅",
        "error": "❌",
        "info": "ℹ️",
        "warning": "⚠️",
        "robot": "🤖",
        "clock": "⏱️",
        "calendar": "🗓️",
        "folder": "📁",
        "doctor": "👨‍⚕️",
        "clip": "📎",
        "bell": "🔔",
    }

    # Formato de data/hora padrão
    DATE_FORMAT = "%d/%m/%Y %H:%M:%S"

    # Limite de caracteres para preview de comentários
    COMMENT_PREVIEW_LIMIT = 80

    # Número máximo de comentários mostrados em listas
    MAX_COMMENTS_SHOWN = 5
