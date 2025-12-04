# 📆 Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### 🚀 Adicionado
- Novas features em desenvolvimento

### 🔄 Alterado
- Melhorias em andamento

### 🐛 Corrigido
- Bugs em correção

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
