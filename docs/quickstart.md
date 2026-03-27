[Wiki Home](Home.md) · [Visão Geral](overview.md) · [Dashboard Workspace](dashboard-workspace.md) · [API REST](api.md)

# Quickstart

> O caminho mais curto para ter a stack rodando, validar que está saudável e fazer o primeiro scraping sem cair em setup desnecessário.

## Caminho recomendado: Docker

### 1. Preparar arquivos locais

```bash
cp .env.example .env
cp config/config.example.json config/config.json
```

### 2. Subir a stack

```bash
docker compose up -d --build
docker compose ps
```

### 3. Conferir URLs principais

- API: `http://localhost:8000/docs`
- Dashboard: `http://localhost:5000`
- Scheduler Telegram: `http://localhost:5000/notifications/telegram/schedule`
- n8n: `http://localhost:5678`
- Selenium: `http://localhost:4444/status`

### 4. Validar Redis

```bash
docker compose exec -T redis redis-cli ping
```

Saída esperada:

```text
PONG
```

## Primeiro scraping

### Pela CLI

```bash
make run-url URL="https://www.doctoralia.com.br/medico/exemplo"
```

### Pela API

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

## Primeiro teste de notificação Telegram

1. Abra `http://localhost:5000/notifications/telegram/schedule`.
2. Use o bloco **Teste Rápido do Telegram**.
3. Informe token/chat ou deixe vazio para usar a configuração global.
4. Envie a mensagem de teste antes de ativar qualquer recorrência.

## Desenvolvimento local sem Docker

```bash
make venv
cp .env.example .env
cp config/config.example.json config/config.json

make api
make dashboard
```

Comandos úteis:

```bash
make test
make lint
make run-full URL="https://www.doctoralia.com.br/medico/exemplo"
```

## Checklist de saúde rápida

| Item | O que verificar |
|---|---|
| API | `GET /v1/health` e `GET /v1/ready` |
| Redis | `redis-cli ping` |
| Selenium | `http://localhost:4444/status` |
| Dashboard | abertura do overview e da página de notificações |
| Telegram | teste manual em `/notifications/telegram/schedule` |

## Problemas comuns

| Sintoma | Ação |
|---|---|
| `ERR_EMPTY_RESPONSE` em `localhost:6379` | Normal. Redis não responde HTTP. |
| Job assíncrono não sai da fila | Verifique `worker` e Redis. |
| Scheduler Telegram não dispara | Confirme se a API está rodando e se o agendamento está ativo. |
| Dashboard sem dados | Confira se existem snapshots em `data/`. |
| Scraping não abre browser remoto | Revise `SELENIUM_REMOTE_URL`. |

## Próximos passos

- [Visão Geral](overview.md)
- [Dashboard Workspace](dashboard-workspace.md)
- [Telegram Notifications](telegram-notifications.md)
- [Operations](operations.md)
