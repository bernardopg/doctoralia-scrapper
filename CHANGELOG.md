# 📆 Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### 🚀 Adicionado
- **Serviço compartilhado de estatísticas** (`src/services/stats.py`) — elimina duplicação entre API e Dashboard
- **Endpoints migrados para API v1**: `/v1/statistics`, `/v1/analyze/quality`, `/v1/settings`
- **Schemas Pydantic para settings** (`src/api/schemas/settings.py`)
- **Health checks** no Dockerfile e docker-compose para todos os serviços
- **Resource limits** (CPU/memória) no docker-compose
- **Testes para reports e settings proxy** (11 novos testes)
- **Página de Relatórios funcional** (`reports.html`)
  - Resumo com total de arquivos, reviews e médicos
  - Listagem de arquivos de dados com paginação
  - Exportação de dados em CSV e JSON
- **Proxy de settings no Dashboard**
  - Rotas proxy: `GET/PUT /api/settings`, `POST /api/settings/validate`
  - Dashboard agora centraliza todas as chamadas à API
- **Progresso em tempo real para scraping**
  - Callback de progresso no `DoctoraliaScraper`
  - Polling automático a cada 2s na página de histórico
- **Persistência de dados no scraping via API**

### 🔄 Alterado
- `settings.html` agora usa proxy do Dashboard (`/api/...`) em vez de URL hardcoded da API
- `history.html` com polling automático para tasks ativas
- Suporte a formato dual de dados (flat e nested) no Dashboard
- `EnhancedErrorHandler` movido de `performance_monitor.py` para `error_handling.py`
- `DoctoraliaScraper` renomeado para `DoctoraliaMultiSiteScraper` em `multi_site_scraper.py`
- Documentação consolidada: n8n (3 arquivos -> 1), deployment (2 -> 1), quickstart (2 -> 1)

### 🗑️ Removido
- `src/api_server.py` — API legada removida, funcionalidade migrada para `src/api/v1/`
- Hacks de `sys.path.insert()` em `dashboard.py` e `telegram_notifier.py`
- Código de exemplo morto em `circuit_breaker.py` e `error_handling.py`
- Documentação duplicada: `n8n-integration.md`, `n8n-workflows-guide.md`, `production-deployment.md`, `quick-start-guide.md`, `AUTOMATED_SETUP.md`

### 🐛 Corrigido
- Fix construtores e métodos em `src/jobs/tasks.py`
- Fix `sys.path` em `dashboard.py` para resolução correta de imports
- Fix caminho de dados: `data/` em vez de `data/scraped_data/`
- Fix `request.get_json()` com `force=True` para robustez no quality-analysis
- Fix dependência NLTK `punkt_tab` para análise de qualidade
- Fix referências incorretas na documentação (endpoints, paths de arquivos)

---

## [0.1.0] - 2025-04-12

### 🚀 Adicionado

#### Core
- **Sistema de Scraping Resiliente**
  - Web scraping com Selenium e BeautifulSoup
  - Circuit breaker para proteção contra falhas
  - Retries inteligentes com backoff exponencial
  - Delays dinâmicos anti-detecção
  - Cache de extrações para otimização

- **API REST Completa (v1)**
  - Endpoints versionados com FastAPI
  - Autenticação via API Key
  - Rate limiting configurável
  - Jobs assíncronos com Redis/RQ
  - Webhooks assinados (HMAC-SHA256)
  - Documentação OpenAPI automática

- **Análise e Geração de Respostas**
  - Análise de sentimento com NLTK
  - Categorização automática de reviews
  - Geração de respostas baseadas em templates
  - Sistema de qualidade de respostas

- **Sistema de Notificações**
  - Integração completa com Telegram Bot
  - Templates de mensagens customizáveis
  - Notificações em tempo real

#### Infraestrutura
- **Docker Support**
  - Dockerfile otimizado para produção
  - docker-compose para desenvolvimento
  - Worker separado para jobs assíncronos

- **CI/CD com GitHub Actions**
  - Workflow de CI (lint, tests, security)
  - Workflow de Docker build
  - Workflow de release automático

- **Observabilidade**
  - Dashboard web com Flask
  - Métricas de performance
  - Health checks configuráveis
  - Logs estruturados

#### Integrações
- **n8n Workflows**
  - `sync-scraping-workflow.json` - Scraping síncrono
  - `async-webhook-workflow.json` - Jobs assíncronos
  - `batch-processing-workflow.json` - Processamento em lote
  - `complete-doctoralia-workflow.json` - Workflow completo

#### Documentação
- README.md profissional com badges e diagramas
- Documentação modular em `docs/`
  - `quickstart.md` - Guia de início rápido
  - `overview.md` - Arquitetura do sistema
  - `api.md` - Referência da API
  - `n8n.md` - Guia de integração n8n
  - `deployment.md` - Deploy para produção
  - `operations.md` - Operações e monitoramento
  - `development.md` - Ambiente de desenvolvimento
  - `templates.md` - Customização de templates

#### Segurança
- SECURITY.md com política de segurança
- CODE_OF_CONDUCT.md
- Análise estática com Bandit
- Verificação de dependências com Safety
- Dependabot configurado

#### DevOps
- Makefile com comandos úteis
- Scripts de automação em `scripts/`
- Templates de issue e PR no GitHub
- Pre-commit hooks configurados

### 🔄 Alterado
- N/A (release inicial)

### 🐛 Corrigido
- N/A (release inicial)

### ⚠️ Deprecated
- N/A (release inicial)

### 🗑️ Removido
- N/A (release inicial)

### 🔒 Segurança
- Implementação inicial de todas as medidas de segurança

---

## [0.0.2] - 2025-03-15 (Pré-release)

### 🚀 Adicionado
- Sistema de cache de extrações
- Make targets: `dashboard`, `api`, `diagnostic`, `health`, `optimize`
- Circuit breaker para proteção de requests

### 🔄 Alterado
- Redução de dependências (~40%)
- Padronização de docstrings e type hints
- Reorganização da estrutura de diretórios

### 🗑️ Removido
- Arquivos de debug temporários
- Scripts não utilizados

---

## [0.0.1] - 2025-02-01 (Pré-release)

### 🚀 Adicionado
- Implementação inicial do scraper
- Estrutura básica do projeto
- Testes unitários iniciais
- Configuração básica

---

## Legenda

| Emoji | Tipo de Mudança |
|-------|-----------------|
| 🚀 | Adicionado - Nova feature |
| 🔄 | Alterado - Mudança em feature existente |
| ⚠️ | Deprecated - Feature que será removida |
| 🗑️ | Removido - Feature removida |
| 🐛 | Corrigido - Bug fix |
| 🔒 | Segurança - Correção de vulnerabilidade |

---

## Links

- [Unreleased]: https://github.com/bernardopg/doctoralia-scrapper/compare/v0.1.0...HEAD
- [0.1.0]: https://github.com/bernardopg/doctoralia-scrapper/releases/tag/v0.1.0
- [0.0.2]: https://github.com/bernardopg/doctoralia-scrapper/releases/tag/v0.0.2
- [0.0.1]: https://github.com/bernardopg/doctoralia-scrapper/releases/tag/v0.0.1

---

## Como Contribuir com o Changelog

Ao fazer uma contribuição, por favor adicione uma entrada na seção `[Unreleased]` seguindo este formato:

```markdown
### 🚀 Adicionado
- Descrição clara da nova feature ([#123](link-para-pr))

### 🐛 Corrigido
- Descrição do bug corrigido ([#124](link-para-pr))
```

**Dicas:**
- Use tempo presente ("Adiciona", não "Adicionado" ou "Adicionando")
- Seja conciso mas descritivo
- Inclua link para a PR/Issue quando aplicável
- Agrupe mudanças relacionadas

---

*Mantido por [@bernardopg](https://github.com/bernardopg)*
