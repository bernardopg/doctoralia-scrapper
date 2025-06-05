# 🏥 Doctoralia Scraper

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
cd doctoralia-scraper
```

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

1. Configure as variáveis de ambiente (opcional):

```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações específicas
```

O arquivo `.env.example` contém todas as variáveis disponíveis com exemplos.

1. Configure o sistema:

```bash
python main.py setup
```

### Usando o Makefile (Recomendado)

O projeto inclui um Makefile com comandos úteis:

```bash
# Ver todos os comandos disponíveis
make help

# Instalar dependências
make install

# Instalar dependências de desenvolvimento
make install-dev

# Configurar projeto
make setup

# Criar arquivo .env
make setup-env

# Executar scraping
make run                    # Scraping interativo (solicita URL)
make run-url URL=<url>      # Scraping com URL específica
make run-full-url URL=<url> # Workflow completo com URL específica

# Executar testes
make test
```

## 🚀 Início Rápido

Após a instalação, você pode começar a usar o sistema imediatamente:

```bash
# 1. Configuração inicial (opcional, mas recomendado)
make setup

# 2. Fazer scraping de um médico específico
make run-url URL=https://www.doctoralia.com.br/seu-medico/especialidade/cidade

# 3. Ou executar o workflow completo (scraping + geração de respostas)
make run-full-url URL=https://www.doctoralia.com.br/seu-medico/especialidade/cidade

# 4. Verificar resultados
make status
```

### Exemplo Prático

```bash
# Scraping da Dra. Bruna Pinto Gomes
make run-url URL=https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte

# Workflow completo
make run-full-url URL=https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte
```

## 🛠️ Configuração

### Telegram (Opcional)

Para receber notificações:

1. Crie um bot com [@BotFather](https://t.me/BotFather)
1. Obtenha o token do bot
1. Obtenha seu chat_id com [@userinfobot](https://t.me/userinfobot)
1. Execute `python main.py setup` e forneça as credenciais

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

> **Nota**: Use o arquivo `config/config.example.json` como template. Consulte `config/README_TEMPLATES.md` para documentação detalhada sobre templates de resposta.

## 📖 Uso

> **💡 Dica**: Execute `make help` para ver todos os comandos disponíveis com suas descrições.

### Comandos Principais

```bash
# Usando Makefile (recomendado)
make setup              # Configuração inicial
make run                # Executar scraping uma vez
make run-url URL=<url>  # Executar scraping com URL específica
make run-full-url URL=<url> # Executar workflow completo com URL específica
make generate           # Gerar respostas
make daemon             # Executar daemon (modo contínuo)
make daemon-debug       # Daemon em modo debug
make monitor            # Monitorar status
make status             # Mostrar status do sistema
make stop               # Parar daemon

# Usando Python diretamente
python main.py setup
python main.py scrape
python main.py scrape --url <url>
python main.py run --url <url>
python main.py generate
python main.py daemon --interval 30
python scripts/monitor_scraping.py
python scripts/system_diagnostic.py
```

### Executando com URL Específica

Para fazer scraping de um médico específico, você pode usar os novos comandos:

```bash
# Apenas scraping
make run-url URL=https://www.doctoralia.com.br/medico/especialidade/cidade

# Workflow completo (scraping + geração de respostas)
make run-full-url URL=https://www.doctoralia.com.br/medico/especialidade/cidade

# Exemplo prático
make run-url URL=https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte
make run-full-url URL=https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte
```

### Modo Daemon

O daemon executa o sistema continuamente:

```bash
# Usando Makefile
make daemon             # Iniciar daemon em background
make daemon-debug       # Iniciar daemon em modo debug
make stop               # Parar daemon em execução
make status             # Verificar status do daemon

# Usando Python diretamente
python main.py daemon --interval 30  # Iniciar com intervalo personalizado
python scripts/daemon.py stop        # Parar daemon
```

## 📁 Estrutura do Projeto

```text
doctoralia-scraper/
├── main.py                 # Interface principal
├── requirements.txt        # Dependências Python
├── requirements-dev.txt    # Dependências de desenvolvimento
├── pyproject.toml         # Configuração do projeto Python
├── setup.cfg              # Configuração de ferramentas
├── Makefile               # Comandos de automação
├── CONTRIBUTING.md        # Guia de contribuição
├── LICENSE                # Licença do projeto
├── .env.example           # Exemplo de variáveis de ambiente
├── config/                # Configurações
│   ├── __init__.py       # Módulo Python
│   ├── settings.py       # Classes de configuração
│   ├── templates.py      # Templates de resposta
│   ├── telegram_templates.py # Templates de notificação
│   ├── config.example.json # Exemplo de configuração
│   └── README_TEMPLATES.md # Documentação de templates
├── src/                   # Código fonte principal
│   ├── __init__.py       # Módulo Python
│   ├── scraper.py        # Motor de scraping
│   ├── response_generator.py # Gerador de respostas
│   ├── telegram_notifier.py # Notificador Telegram
│   └── logger.py         # Sistema de logging
├── scripts/              # Scripts utilitários
│   ├── daemon.py        # Controle do daemon
│   ├── monitor_scraping.py # Monitor de status
│   ├── system_diagnostic.py # Diagnóstico
│   ├── setup.py         # Configuração automatizada
│   ├── install_deps.py  # Instalação de dependências
│   └── init.py          # Inicialização
├── tests/               # Testes automatizados
│   ├── conftest.py     # Configuração dos testes
│   ├── fixtures/       # Dados de teste
│   ├── integration/    # Testes de integração
│   └── unit/           # Testes unitários
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
- **`scripts/init.py`**: Script de inicialização

## 📊 Logs e Dados

O sistema gera logs detalhados e armazena dados em `data/`:

### Estrutura de Logs (`data/logs/`)

- `scraper_YYYYMM.log`: Logs do processo de scraping
- `generator_YYYYMM.log`: Logs da geração de respostas
- `daemon_YYYYMM.log`: Logs do daemon
- `debug_html_YYYYMM.log`: Debug de HTML para troubleshooting
- `setup_YYYYMM.log`: Logs da configuração inicial
- `status_YYYYMM.log`: Logs de verificação de status

### Dados Processados

- `data/processed_reviews.json`: Avaliações já processadas
- `data/responses/`: Respostas geradas para cada avaliação
- `data/extractions/`: Dados extraídos organizados por data e médico
  - Cada extração contém:
    - `complete_data.json`: Dados completos
    - `extraction_summary.json`: Resumo da extração
    - `with_replies.json`: Avaliações com respostas
    - `without_replies.json`: Avaliações sem respostas

## 🔒 Segurança

- Nunca commite credenciais no repositório
- Use variáveis de ambiente para dados sensíveis
- O arquivo `config/config.json` está no .gitignore
- Tokens e chaves são armazenados localmente
- Use o arquivo `.env.example` como template para suas configurações

## 🧪 Testes

O projeto inclui testes automatizados organizados em:

```bash
# Usando Makefile (recomendado)
make test              # Executar todos os testes
make test-unit         # Executar testes unitários
make test-integration  # Executar testes de integração

# Usando pytest diretamente
python -m pytest                    # Todos os testes
python -m pytest tests/unit/        # Testes unitários
python -m pytest tests/integration/ # Testes de integração
python -m pytest --cov=src          # Com cobertura
```

### Estrutura de Testes

- **`tests/unit/`**: Testes unitários de componentes individuais
- **`tests/integration/`**: Testes de integração entre componentes
- **`tests/fixtures/`**: Dados de teste e fixtures
- **`conftest.py`**: Configurações compartilhadas dos testes

## 🛠️ Desenvolvimento

### Ambiente de Desenvolvimento

```bash
# Instalar dependências de desenvolvimento
make install-dev

# Formatar código
make format

# Verificar formatação sem alterar arquivos
make format-check

# Verificar estilo de código
make lint

# Executar verificações de segurança
make security

# Executar testes com cobertura HTML
make test-coverage

# Limpar arquivos temporários
make clean
```

### Qualidade de Código

O projeto utiliza várias ferramentas para manter a qualidade:

- **Black**: Formatação automática de código
- **isort**: Organização de imports
- **flake8**: Verificação de estilo
- **mypy**: Verificação de tipos
- **pylint**: Análise estática
- **bandit**: Verificação de segurança
- **safety**: Verificação de vulnerabilidades em dependências

### Configuração do Projeto

- **`pyproject.toml`**: Configuração moderna do projeto Python (PEP 518)
- **`setup.cfg`**: Configuração das ferramentas de qualidade
- **`requirements.txt`**: Dependências de produção
- **`requirements-dev.txt`**: Dependências de desenvolvimento

## 🐛 Troubleshooting

### Problemas Comuns

1. **Erro de WebDriver**: Instale o ChromeDriver compatível
1. **Timeout de Página**: Ajuste `scraping.timeout` na configuração
1. **Rate Limiting**: Aumente `delay_min` e `delay_max`

### Debug

Use o modo debug para análise detalhada:

```bash
python main.py scrape --debug
```

## 📄 Licença

Este projeto é privado e confidencial.

## 🤝 Contribuição

Para contribuir com o projeto, consulte o [Guia de Contribuição](CONTRIBUTING.md) completo.

### Processo Rápido

1. Faça um fork do repositório
1. Crie uma branch para sua feature: `git checkout -b feature/nova-funcionalidade`
1. Faça suas alterações seguindo os padrões de código
1. Execute os testes: `make test`
1. Commit suas mudanças: `git commit -m "feat: adiciona nova funcionalidade"`
1. Push para sua branch: `git push origin feature/nova-funcionalidade`
1. Abra um Pull Request

### Antes de Contribuir

- Leia o [CONTRIBUTING.md](CONTRIBUTING.md)
- Execute `make install-dev` para instalar dependências de desenvolvimento
- Execute `make lint` e `make test` antes de fazer commit
- Siga os padrões de commit convencionais

## 📞 Suporte

Para suporte ou dúvidas, consulte os logs do sistema ou execute o diagnóstico:

```bash
python scripts/system_diagnostic.py
```
