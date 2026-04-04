<p align="center">
  <img src="docs/assets/banner.svg" width="100%">
</p>

<p align="center">
  <strong>Pipeline Docker-first para scraping de reviews, geração de respostas e relatórios Telegram com API, dashboard, Redis/RQ, Selenium e n8n.</strong>
</p>

<p align="center">
  <a href="docs/Home.md"><strong>Wiki</strong></a> ·
  <a href="docs/quickstart.md">Quickstart</a> ·
  <a href="docs/api.md">API REST</a> ·
  <a href="docs/dashboard-workspace.md">Dashboard</a> ·
  <a href="docs/telegram-notifications.md">Telegram</a> ·
  <a href="docs/n8n.md">n8n</a> ·
  <a href="docs/about.md">About</a>
</p>

## Por que este projeto existe

Este repositório organiza uma rotina operacional completa para reviews do Doctoralia. Em vez de tratar scraping como um script solto, ele une coleta, análise, geração de respostas, snapshots persistidos, histórico, observabilidade, autenticação do dashboard e distribuição por Telegram em uma mesma stack local.

## O que você encontra aqui

| Bloco | O que faz |
|---|---|
| `api` | Expõe endpoints sync e async, settings, health, metrics e notificações Telegram |
| `worker` | Processa scraping, análise, geração e snapshots em background |
| `dashboard` | Workspace visual para operação diária, histórico, relatórios, perfil do operador e scheduler |
| `redis` | Fila RQ, métricas Redis-backed, agendamentos, locks e histórico |
| `selenium` | Navegador remoto para scraping resiliente |
| `n8n` | Orquestrações externas, callbacks e automações multi-sistema |

## Tour visual

<table>
  <tr>
    <td width="50%">
      <a href="docs/assets/dashboard-overview.png">
        <img src="docs/assets/dashboard-overview.png" alt="Overview do dashboard" width="100%">
      </a>
    </td>
    <td width="50%">
      <a href="docs/assets/dashboard-notifications.png">
        <img src="docs/assets/dashboard-notifications.png" alt="Agendamentos Telegram do dashboard" width="100%">
      </a>
    </td>
  </tr>
  <tr>
    <td><strong>Workspace operacional</strong><br>Perfis, pendências, saúde da stack, relatórios e histórico de snapshots.</td>
    <td><strong>Scheduler Telegram</strong><br>Recorrência, scraping novo, geração, anexos, health e histórico persistido.</td>
  </tr>
</table>

## Como a stack funciona

![Workflow principal do projeto](docs/assets/workflow-platform.svg)

## Início rápido

### Docker

```bash
cp .env.example .env
cp config/config.example.json config/config.json

docker compose up -d --build
docker compose ps
```

URLs locais esperadas:

- API: `http://localhost:8000/docs`
- Dashboard: `http://localhost:5000` (redireciona para `/login` quando a auth estiver ativa)
- Telegram scheduling: `http://localhost:5000/notifications/telegram/schedule`
- n8n: `http://localhost:5678` com Basic Auth configurada no `.env`
- Selenium status: `http://localhost:4444/status`

Primeiro acesso ao dashboard:

- usuário padrão: o campo `user_profile.username` em `config/config.json` (por padrão, `admin`)
- senha inicial: a `API_KEY` enquanto o bootstrap estiver ativo e ainda não existir `dashboard_password_hash`
- troca de senha: faça depois do login em `http://localhost:5000/me`

### Desenvolvimento local

```bash
make venv
cp .env.example .env
cp config/config.example.json config/config.json

make api
make dashboard
```

Comandos úteis:

```bash
make run-url URL="https://www.doctoralia.com.br/medico/exemplo"
make run-full URL="https://www.doctoralia.com.br/medico/exemplo"
make test
make lint
```

## Endpoints que importam

| Método | Endpoint | Uso |
|---|---|---|
| `POST` | `/v1/scrape:run` | Scraping síncrono |
| `POST` | `/v1/jobs` | Cria job assíncrono |
| `GET` | `/v1/jobs/{job_id}` | Consulta job |
| `GET` | `/v1/ready` | Readiness com Redis, Selenium e NLTK |
| `GET` | `/v1/metrics` | Métricas da API persistidas em Redis |
| `GET` | `/v1/auth/status` | Estado da autenticação do dashboard |
| `POST` | `/v1/auth/login` | Validação de credenciais do dashboard |
| `POST` | `/v1/auth/change-password` | Rotação da senha dedicada do dashboard |
| `GET/POST/PUT/DELETE` | `/v1/notifications/telegram/schedules` | CRUD do scheduler Telegram |
| `POST` | `/v1/notifications/telegram/schedules/{schedule_id}/run` | Disparo manual |
| `GET` | `/v1/notifications/telegram/history` | Histórico persistido |
| `POST` | `/v1/notifications/telegram/test` | Validação real do bot |
| `POST` | `/v1/hooks/n8n/scrape` | Webhook dedicado do n8n |

## Estado atual do projeto

| Tema | Situação |
|---|---|
| Stack Docker | `api`, `worker`, `dashboard`, `redis`, `selenium`, `n8n` |
| Workspace web | Operacional, autenticado e com scheduler Telegram integrado |
| Persistência | Snapshots em `data/` e histórico/schedules em Redis |
| Métricas da API | Redis-backed, multi-processo |
| n8n local | preso em `127.0.0.1:5678`, com auth e encryption key obrigatórias |
| Testes | suíte cobrindo áreas críticas de API, dashboard, jobs, Redis e Telegram |
| Auth do dashboard | login web, sessão assinada, bootstrap via `API_KEY` e rotação em `/me` |

## Redis em `localhost:6379`

Se você abrir `http://localhost:6379` no navegador e receber `ERR_EMPTY_RESPONSE`, isso é esperado.

- Redis está rodando.
- O browser fala HTTP.
- Redis não fala HTTP.

Validação correta:

```bash
docker compose exec -T redis redis-cli ping
```

Saída esperada:

```text
PONG
```

## Wiki do repositório

O `README` agora é só a entrada. A documentação foi reorganizada em formato de wiki dentro de `docs/`.

| Página | Para que serve |
|---|---|
| [docs/Home.md](docs/Home.md) | Hub principal da wiki |
| [docs/about.md](docs/about.md) | Texto de vitrine, metadata e assets do repositório |
| [docs/quickstart.md](docs/quickstart.md) | Setup rápido |
| [docs/overview.md](docs/overview.md) | Arquitetura e responsabilidades |
| [docs/dashboard-workspace.md](docs/dashboard-workspace.md) | Operação diária no dashboard |
| [docs/telegram-notifications.md](docs/telegram-notifications.md) | Scheduler Telegram completo |
| [docs/api.md](docs/api.md) | Referência da API |
| [docs/n8n.md](docs/n8n.md) | Workflows e integração externa |
| [docs/operations.md](docs/operations.md) | Runbook e troubleshooting |
| [docs/development.md](docs/development.md) | Padrões de desenvolvimento |
| [docs/deployment.md](docs/deployment.md) | Guia de deploy |
| [docs/templates.md](docs/templates.md) | Templates e mensagens |

## Assets visuais adicionados

- [docs/assets/logo.svg](docs/assets/logo.svg)
- [docs/assets/banner.svg](docs/assets/banner.svg)
- [docs/assets/social-card.svg](docs/assets/social-card.svg)
- [docs/assets/workflow-platform.svg](docs/assets/workflow-platform.svg)
- [docs/assets/workflow-telegram.svg](docs/assets/workflow-telegram.svg)

## Convenções técnicas

- Imports internos padronizados em formato absoluto: `from src...` e `from config...`
- Dependências gerenciadas por `poetry`
- Formatação com `black` e `isort`
- Testes com `pytest`

## Limitações atuais

- Rate limiting global da API REST ainda não existe como middleware completo.
- O scheduler recorrente depende da API estar de pé.
- A troca de senha do dashboard hoje valida apenas o mínimo de caracteres no backend; complexidade adicional ainda é recomendação de UX, não requisito de servidor.
- Ainda há espaço para subir coverage em `src/scraper.py`, `src/response_generator.py`, `src/telegram_notifier.py` e `src/dashboard.py`.

## Licença

[MIT](LICENSE)
