#!/usr/bin/env python3
"""
Templates para mensagens do Telegram
Permite personalização fácil das notificações
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class TelegramTemplates:
    """Templates personalizáveis para mensagens do Telegram"""

    @staticmethod
    def daemon_started(interval_minutes: int) -> str:
        """Template para notificação de daemon iniciado"""
        return f"""🔄 *Daemon Automático Iniciado*

⏰ *Intervalo:* {interval_minutes} minutos
🤖 *Função:* Geração automática de respostas
📅 *Iniciado em:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

✅ Sistema funcionando em segundo plano"""

    @staticmethod
    def daemon_stopped() -> str:
        """Template para notificação de daemon parado"""
        return f"""🛑 *Daemon Automático Finalizado*

📅 *Finalizado em:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

⚠️ Geração automática interrompida"""

    @staticmethod
    def generation_cycle_success(responses: List[Dict[str, Any]]) -> str:
        """Template para ciclo de geração bem-sucedido"""
        total = len(responses)

        message = f"""🤖 *Doctoralia - Respostas Geradas Automaticamente*

📊 *Resumo do Ciclo:*
• {total} nova(s) resposta(s) gerada(s)
• Arquivos salvos na pasta `responses/`
• Processamento automático concluído

📝 *Últimos comentários processados:*
"""

        # Mostra até 3 comentários para não ficar muito longo
        for i, response in enumerate(responses[:3], 1):
            author = response.get("author", "Anônimo")
            comment = response.get("comment", "")
            comment_preview = comment[:50] + "..." if len(comment) > 50 else comment
            message += f"\n{i}. *{author}*: {comment_preview}"

        if total > 3:
            message += f"\n... e mais {total - 3} resposta(s)"

        message += f"""

📅 *Data do ciclo:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔔 *Próximo ciclo automático em breve!*
✅ *Copie e cole as respostas no Doctoralia*"""

        return message

    @staticmethod
    def generation_cycle_no_responses() -> str:
        """Template para ciclo sem novas respostas"""
        return f"""ℹ️ *Doctoralia - Ciclo Automático*

📊 *Status:* Nenhuma nova resposta necessária
✅ *Todos os comentários já possuem resposta*

📅 *Verificação em:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔄 *Próxima verificação automática em breve*"""

    @staticmethod
    def daemon_error(error_message: str, context: str = "Daemon de geração automática") -> str:
        """Template para erros do daemon"""
        return f"""❌ *Doctoralia - Erro no Daemon*

🔍 *Contexto:* {context}
💥 *Erro:* {error_message}

📅 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

⚠️ *Verificar logs para mais detalhes*
🔧 *Daemon pode ter sido interrompido*"""

    @staticmethod
    def scraping_complete(data: Dict[str, Any], save_path: Path) -> str:
        """Template para scraping concluído"""
        doctor_name = data.get("doctor_name", "Médico")
        total_reviews = data.get("total_reviews", 0)

        with_replies = len([r for r in data.get("reviews", []) if r.get("doctor_reply")])
        without_replies = total_reviews - with_replies

        return f"""🏥 *Doctoralia - Scraping Concluído*

👨‍⚕️ *Médico:* {doctor_name}
📊 *Total de comentários:* {total_reviews}
💬 *Com respostas:* {with_replies}
🔇 *Sem respostas:* {without_replies}

📁 *Dados salvos em:* `{save_path.name}`
📅 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

{f"🎯 *{without_replies} comentários prontos para resposta!*" if without_replies > 0 else "✅ *Todos os comentários já possuem resposta*"}"""

    @staticmethod
    def responses_generated(responses: List[Dict[str, Any]]) -> str:
        """Template para respostas geradas manualmente"""
        total = len(responses)

        message = f"""🤖 *Doctoralia - Respostas Geradas*

📊 *Resumo:*
• {total} nova(s) resposta(s) gerada(s)
• Arquivos salvos na pasta `responses/`

📝 *Comentários processados:*
"""

        for i, response in enumerate(responses[:5], 1):
            author = response.get("author", "Anônimo")
            comment = response.get("comment", "")
            comment_preview = comment[:50] + "..." if len(comment) > 50 else comment
            message += f"\n{i}. *{author}*: {comment_preview}"

        if total > 5:
            message += f"\n... e mais {total - 5} resposta(s)"

        message += f"""

📅 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔔 *Copie e cole as respostas no Doctoralia!*"""

        return message

    @staticmethod
    def responses_generated_with_file(responses: List[Dict[str, Any]], file_path: Path) -> str:
        """Template para respostas geradas com arquivo anexado"""
        total = len(responses)

        message = f"""🤖 *Doctoralia - Respostas Geradas*

📊 *Resumo:*
• {total} nova(s) resposta(s) gerada(s)
• Arquivo único consolidado anexado
• Todas as respostas prontas para copiar/colar

📝 *Comentários processados:*
"""

        for i, response in enumerate(responses[:3], 1):
            author = response.get("author", "Anônimo")
            comment = response.get("comment", "")
            comment_preview = comment[:50] + "..." if len(comment) > 50 else comment
            message += f"\n{i}. *{author}*: {comment_preview}"

        if total > 3:
            message += f"\n... e mais {total - 3} resposta(s)"

        message += f"""

📁 *Arquivo:* `{file_path.name}`
📅 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔔 *Abra o arquivo anexado e copie as respostas para o Doctoralia!*"""

        return message

    @staticmethod
    def generic_error(error_message: str, context: str = "") -> str:
        """Template para erros genéricos"""
        return f"""❌ *Doctoralia - Erro*

🔍 *Contexto:* {context}
💥 *Erro:* {error_message}

📅 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""

    @staticmethod
    def custom_message(title: str, content: str, emoji: str = "📢") -> str:
        """Template para mensagens customizadas"""
        return f"""{emoji} *{title}*

{content}

📅 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""


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
        "clock": "⏰",
        "calendar": "📅",
        "folder": "📁",
        "doctor": "👨‍⚕️",
        "bell": "🔔",
    }

    # Formato de data/hora padrão
    DATE_FORMAT = "%d/%m/%Y %H:%M:%S"

    # Limite de caracteres para preview de comentários
    COMMENT_PREVIEW_LIMIT = 50

    # Número máximo de comentários mostrados em listas
    MAX_COMMENTS_SHOWN = 5
