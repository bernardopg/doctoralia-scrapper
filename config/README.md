# Configuração

Este diretório contém os arquivos de configuração do projeto.

## Arquivos

- `config.example.json` - Arquivo de exemplo com todas as configurações necessárias
- `config.json` - Arquivo de configuração real (não versionado)

## Setup Inicial

1. Copie o arquivo de exemplo:

   ```bash
   cp config/config.example.json config/config.json
   ```

2. Edite o `config.json` com suas configurações reais:
   - `telegram.token` - Token do seu bot do Telegram
   - `telegram.chat_id` - ID do chat onde receberá as notificações
   - `urls.profile_url` - URL do seu perfil no Doctoralia
   - Outras configurações conforme necessário

⚠️ **Importante**: O arquivo `config.json` contém informações sensíveis e não deve ser commitado no repositório. Ele já está incluído no `.gitignore`.
