# Doctoralia Scrapper

Sistema para coletar reviews do Doctoralia, analisar sentimento, gerar respostas sugeridas e operar o fluxo por API, worker assíncrono, dashboard web e n8n.

## Estado atual

- Stack Docker com `api`, `worker`, `dashboard`, `redis`, `selenium` e `n8n`
- API FastAPI em `http://localhost:8000`
- Dashboard Flask em `http://localhost:5000`
- Página de agendamentos Telegram em `http://localhost:5000/notifications/telegram/schedule`
- n8n em `http://localhost:5678`
- Redis/RQ para jobs assíncronos e retenção/rate limiting de integrações
- Métricas da API persistidas em Redis para visibilidade multi-processo
- Selenium remoto para scraping via browser

## Componentes

| Serviço | Porta | Função |
|---|---:|---|
| API | `8000` | Endpoints REST, health, jobs, settings, geração unitária |
| Dashboard | `5000` | Workspace operacional, histórico, relatórios, perfis e agendamentos Telegram |
| n8n | `5678` | Orquestração de workflows |
| Redis | `6379` | Fila RQ, estado transitório e TTL de jobs |
| Selenium | `4444` | Navegador remoto para scraping |
| Selenium VNC | `7900` | Debug visual do browser |

## Início rápido com Docker

```bash
cp .env.example .env
cp config/config.example.json config/config.json

docker compose up -d --build
docker compose ps
```

Serviços esperados:

- `api` saudável em `http://localhost:8000/docs`
- `dashboard` saudável em `http://localhost:5000`
- `n8n` saudável em `http://localhost:5678`
- `redis` saudável internamente e exposto em `localhost:6379`
- `selenium` saudável em `http://localhost:4444/status`

## Desenvolvimento local

```bash
make venv
cp .env.example .env
cp config/config.example.json config/config.json
```

Comandos úteis:

```bash
make api
make dashboard
make run-url URL="https://www.doctoralia.com.br/medico/exemplo"
make run-full URL="https://www.doctoralia.com.br/medico/exemplo"
make test
make lint
```

## Variáveis de ambiente principais

Use [.env.example](.env.example) como base.

Obrigatórias:

```env
API_KEY=sua-chave
WEBHOOK_SIGNING_SECRET=seu-segredo
```

Comuns no Docker:

```env
REDIS_URL=redis://redis:6379/0
SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
LOG_LEVEL=INFO
MASK_PII=true
```

Opcionais:

```env
OPENAI_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
N8N_BASIC_AUTH_ACTIVE=false
N8N_BASIC_AUTH_USER=
N8N_BASIC_AUTH_PASSWORD=
```

## API principal

Endpoints mais usados:

| Método | Endpoint | Uso |
|---|---|---|
| `POST` | `/v1/scrape:run` | Scraping síncrono |
| `POST` | `/v1/jobs` | Cria job assíncrono |
| `GET` | `/v1/jobs` | Lista jobs |
| `GET` | `/v1/jobs/{job_id}` | Consulta job |
| `POST` | `/v1/generate/response` | Gera resposta unitária |
| `GET` | `/v1/settings` | Lê settings efetivos |
| `PUT` | `/v1/settings` | Atualiza settings |
| `POST` | `/v1/settings/validate` | Valida payload de settings |
| `GET` | `/v1/health` | Health básico |
| `GET` | `/v1/ready` | Readiness com Redis, Selenium e NLTK |
| `GET` | `/v1/metrics` | Métricas Redis-backed da API |
| `GET/POST/PUT/DELETE` | `/v1/notifications/telegram/schedules` | CRUD de agendamentos Telegram |
| `POST` | `/v1/notifications/telegram/schedules/{schedule_id}/run` | Disparo manual de um agendamento |
| `GET` | `/v1/notifications/telegram/history` | Histórico persistido das notificações |
| `POST` | `/v1/notifications/telegram/test` | Envio de teste real via Telegram |
| `POST` | `/v1/hooks/n8n/scrape` | Webhook dedicado do n8n |

Exemplo:

```bash
curl -X POST http://localhost:8000/v1/scrape:run \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
    "include_analysis": true,
    "include_generation": false
  }'
```

## Redis em `localhost:6379`

Se abrir `http://localhost:6379` no navegador e receber `ERR_EMPTY_RESPONSE`, isso é esperado.

- Redis não fala HTTP.
- O browser envia HTTP.
- Redis responde no protocolo próprio dele, então a conexão parece “vazia” para o navegador.

Validação correta:

```bash
docker compose exec -T redis redis-cli ping
```

Saída esperada:

```text
PONG
```

## Testes e coverage

```bash
poetry run pytest --cov=src --cov-report=term-missing
```

Estado validado localmente nesta revisão:

- `250 passed`
- coverage total: `74%`

Áreas já fortalecidas recentemente:

- jobs assíncronos e snapshots
- integração real com Redis/RQ
- autenticação e assinatura HMAC
- validação de ambiente
- scheduler Redis-backed para notificações Telegram
- dashboard de agendamentos e histórico de notificações

## Convenções de código

- Imports internos padronizados em formato absoluto: `from src...` e `from config...`
- Formatação com `black` e `isort`
- Testes com `pytest`
- Dependências gerenciadas por `poetry`

## Limitações conhecidas

- Rate limiting da API REST como middleware global ainda não está implementado
- Cobertura ainda baixa em `src/scraper.py`, `src/response_generator.py`, `src/telegram_notifier.py` e `src/dashboard.py`
- O runner automático dos agendamentos Telegram roda no processo da API; se o serviço `api` estiver parado, os disparos recorrentes não acontecem

## Documentação complementar

- [docs/quickstart.md](docs/quickstart.md)
- [docs/api.md](docs/api.md)
- [docs/dashboard-workspace.md](docs/dashboard-workspace.md)
- [docs/n8n.md](docs/n8n.md)
- [docs/development.md](docs/development.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/overview.md](docs/overview.md)
- [docs/operations.md](docs/operations.md)

## Licença

[MIT](LICENSE)
