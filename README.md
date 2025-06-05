# 🏥 Doctoralia Scrapper

Sistema automatizado para scraping de avaliações e geração de respostas no Doctoralia com notificações via Telegram.

## 📋 Funcionalidades

- **🔍 Scraping Automático**: Coleta avaliações e comentários do site Doctoralia
- **🤖 Geração de Respostas**: Gera respostas automáticas para avaliações
- **📱 Notificações Telegram**: Receba notificações em tempo real sobre o status do sistema
- **⚙️ Daemon Mode**: Execução contínua em background
- **📊 Sistema de Logs**: Logging completo de todas as operações
- **🔧 Configuração Flexível**: Configuração através de arquivos JSON

## 🚀 Instalação

1. Clone o repositório:
```bash
git clone <repository-url>
cd doctoralia-scrapper
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o sistema:
```bash
python main.py setup
```

## 🛠️ Configuração

### Telegram (Opcional)

Para receber notificações:

1. Crie um bot com [@BotFather](https://t.me/BotFather)
2. Obtenha o token do bot
3. Obtenha seu chat_id com [@userinfobot](https://t.me/userinfobot)
4. Execute `python main.py setup` e forneça as credenciais

### Configuração Manual

Edite o arquivo `config/config.json` com suas configurações:

```json
{
  "telegram": {
    "token": "seu_bot_token",
    "chat_id": "seu_chat_id",
    "enabled": true
  },
  "scraping": {
    "headless": true,
    "timeout": 60,
    "delay_min": 2.0,
    "delay_max": 4.0
  }
}
```

## 📖 Uso

### Comandos Principais

```bash
# Configuração inicial
python main.py setup

# Executar scraping uma vez
python main.py scrape

# Gerar respostas
python main.py generate

# Executar daemon (modo contínuo)
python main.py daemon --interval 30

# Monitorar status
python scripts/monitor_scraping.py

# Diagnóstico do sistema
python scripts/system_diagnostic.py
```

### Modo Daemon

O daemon executa o sistema continuamente:

```bash
# Iniciar daemon com intervalo de 30 minutos
python main.py daemon --interval 30

# Parar daemon
python scripts/daemon.py stop
```

## 📁 Estrutura do Projeto

```
doctoralia-scrapper/
├── main.py                 # Interface principal
├── requirements.txt        # Dependências Python
├── config/                 # Configurações
│   ├── settings.py        # Classes de configuração
│   ├── templates.py       # Templates de resposta
│   └── telegram_templates.py # Templates de notificação
├── src/                   # Código fonte principal
│   ├── scraper.py        # Motor de scraping
│   ├── response_generator.py # Gerador de respostas
│   ├── telegram_notifier.py # Notificador Telegram
│   └── logger.py         # Sistema de logging
├── scripts/              # Scripts utilitários
│   ├── daemon.py        # Controle do daemon
│   ├── monitor_scraping.py # Monitor de status
│   └── system_diagnostic.py # Diagnóstico
└── data/                # Dados e logs
    ├── processed_reviews.json
    ├── logs/           # Arquivos de log
    ├── responses/      # Respostas geradas
    └── extractions/    # Dados extraídos
```

## 🔧 Scripts Utilitários

- **`scripts/daemon.py`**: Controle do processo daemon
- **`scripts/monitor_scraping.py`**: Monitor de status em tempo real
- **`scripts/system_diagnostic.py`**: Diagnóstico completo do sistema
- **`scripts/setup.py`**: Configuração automatizada
- **`scripts/install_deps.py`**: Instalação de dependências

## 📊 Logs

O sistema gera logs detalhados em `data/logs/`:

- `scraper_YYYYMM.log`: Logs do processo de scraping
- `generator_YYYYMM.log`: Logs da geração de respostas
- `daemon_YYYYMM.log`: Logs do daemon
- `debug_html_YYYYMM.log`: Debug de HTML para troubleshooting

## 🔒 Segurança

- Nunca commite credenciais no repositório
- Use variáveis de ambiente para dados sensíveis
- O arquivo `config/config.json` está no .gitignore
- Tokens e chaves são armazenados localmente

## 🐛 Troubleshooting

### Problemas Comuns

1. **Erro de WebDriver**: Instale o ChromeDriver compatível
2. **Timeout de Página**: Ajuste `scraping.timeout` na configuração
3. **Rate Limiting**: Aumente `delay_min` e `delay_max`

### Debug

Use o modo debug para análise detalhada:

```bash
python main.py scrape --debug
```

## 📄 Licença

Este projeto é privado e confidencial.

## 🤝 Contribuição

Para contribuir com o projeto:

1. Faça um fork do repositório
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Abra um Pull Request

## 📞 Suporte

Para suporte ou dúvidas, consulte os logs do sistema ou execute o diagnóstico:

```bash
python scripts/system_diagnostic.py
```
