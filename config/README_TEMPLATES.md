# Templates de Notificação Telegram

Este arquivo contém todos os templates das mensagens enviadas via Telegram, permitindo fácil personalização das notificações.

## Como Usar

### Personalizar Mensagens

Edite o arquivo `config/telegram_templates.py` para modificar:

- **Emojis**: Altere os emojis em `NotificationConfig.EMOJIS`
- **Formato de data**: Modifique `NotificationConfig.DATE_FORMAT`
- **Textos das mensagens**: Edite diretamente os métodos da classe `TelegramTemplates`

### Tipos de Notificação Disponíveis

#### Daemon

- `daemon_started(interval_minutes)`: Notificação quando o daemon é iniciado
- `daemon_stopped()`: Notificação quando o daemon é parado
- `daemon_error(error_message, context)`: Notificação de erro no daemon

#### Geração de Respostas

- `generation_cycle_success(responses)`: Notificação de ciclo bem-sucedido
- `generation_cycle_no_responses()`: Notificação quando não há novas respostas
- `responses_generated(responses)`: Notificação para geração manual

#### Scraping

- `scraping_complete(data, save_path)`: Notificação de scraping concluído

#### Genéricas

- `generic_error(error_message, context)`: Erro genérico
- `custom_message(title, content, emoji)`: Mensagem personalizada

### Exemplo de Personalização

```python
# Modificar emoji principal
NotificationConfig.EMOJIS['success'] = '🎉'

# Modificar formato de data
NotificationConfig.DATE_FORMAT = '%d/%m/%Y às %H:%M'

# Personalizar mensagem de daemon iniciado
@staticmethod
def daemon_started(interval_minutes: int) -> str:
    return f"""🚀 *MEU DAEMON PERSONALIZADO*

⏰ Intervalo: {interval_minutes} min
📅 Iniciado: {datetime.now().strftime(NotificationConfig.DATE_FORMAT)}

🔥 Sistema rodando!"""
```

## Configurações Rápidas

### Emojis Principais

```python
EMOJIS = {
    'daemon_start': '🔄',
    'daemon_stop': '🛑',
    'success': '✅',
    'error': '❌',
    'info': 'ℹ️',
    'warning': '⚠️',
    'robot': '🤖',
    'clock': '⏰',
    'calendar': '📅',
    'folder': '📁',
    'doctor': '👨‍⚕️',
    'bell': '🔔'
}
```

### Limites Configuráveis

- `COMMENT_PREVIEW_LIMIT`: Caracteres mostrados dos comentários (padrão: 50)
- `MAX_COMMENTS_SHOWN`: Máximo de comentários em listas (padrão: 5)

## Função send_notification

O daemon agora possui uma função centralizada `send_notification()` que aceita os seguintes tipos:

```python
# Iniciar daemon
daemon.send_notification("daemon_started", interval_minutes=30)

# Parar daemon
daemon.send_notification("daemon_stopped")

# Sucesso na geração
daemon.send_notification("generation_success", responses=responses_list)

# Nenhuma resposta nova
daemon.send_notification("generation_no_responses")

# Erro no daemon
daemon.send_notification("daemon_error",
                        error_message="Descrição do erro",
                        context="Contexto do erro")

# Mensagem personalizada
daemon.send_notification("custom",
                        title="Meu Título",
                        content="Meu conteúdo",
                        emoji="🔥")
```

Isso centraliza todas as notificações em um só lugar, facilitando o controle e debug.
