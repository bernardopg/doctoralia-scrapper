[Wiki Home](Home.md) · [Quickstart](quickstart.md) · [Visão Geral](overview.md) · [Telegram Notifications](telegram-notifications.md)

# Operations & Monitoring

## Objetivo

Esta página concentra o runbook do projeto: health, logs, agendamentos, retenção, backup e diagnóstico rápido.

## Endpoints de saúde

| Endpoint | Uso |
|---|---|
| `/v1/health` | disponibilidade básica da API |
| `/v1/ready` | readiness com Redis, queue, Selenium e NLTK |
| `/v1/statistics` | estatísticas agregadas |
| `/v1/metrics` | métricas Redis-backed da API |

## Painéis operacionais no dashboard

| Página | Uso |
|---|---|
| `/` | visão consolidada do workspace |
| `/history` | auditoria e prune de snapshots |
| `/reports` | inventário e resumo executivo |
| `/health-check` | leitura visual de saúde |
| `/notifications/telegram/schedule` | agendamentos e histórico de notificações |

## Fluxo assíncrono do projeto

1. A API enfileira um job em Redis.
2. O worker processa scraping, análise e geração.
3. O resultado final é salvo como snapshot em `data/`.
4. O dashboard passa a enxergar o novo estado operacional.
5. O scheduler Telegram pode usar esse snapshot ou disparar um novo scraping.

## Logs e arquivos importantes

| Item | Caminho |
|---|---|
| Snapshots | `data/` |
| Anexos de notificações | `data/notifications/` |
| Logs locais | `data/logs/` ou `logs/` |
| Config local | `config/config.json` |

## Diagnóstico rápido

```bash
make health
python scripts/system_diagnostic.py
python scripts/monitor_scraping.py
docker compose ps
```

## Scheduler Telegram: regra operacional

> O scheduler recorrente roda no processo da API. Se o serviço `api` cair, as recorrências param mesmo que Redis continue saudável.

Checklist quando um agendamento não dispara:

1. confirme que `api` está no ar
2. confirme que o agendamento está `enabled`
3. confira `next_run_at`
4. confira histórico em `/v1/notifications/telegram/history`
5. confira se há erro salvo em `last_error`

## Backups e retenção

| Item | Frequência sugerida | Observação |
|---|---|---|
| `data/` | diária | mantém snapshots e anexos |
| `config/config.json` | a cada mudança | contém comportamento da stack |
| logs críticos | semanal | rotacione ou compacte |

Exemplo simples:

```bash
tar -czf backup_$(date +%Y%m%d).tgz data config/config.json
```

## Troubleshooting

| Sintoma | Verificar |
|---|---|
| Browser em `localhost:6379` retorna vazio | Normal. Redis não fala HTTP. |
| Jobs pendentes para sempre | Worker parado ou Redis inacessível |
| Workspace sem atualização | Snapshot não salvo ou leitura incorreta de `data/` |
| Histórico Telegram vazio | Nenhum envio concluído ou Redis limpo |
| Health parcial | Dependência fora do ar, especialmente Selenium |
| Callback n8n falhando | Assinatura HMAC, timeout ou URL de callback |

## Robustez sugerida

- rotacionar logs antigos
- versionar ou copiar snapshots críticos
- monitorar Redis e Selenium junto da API
- separar filas por prioridade se o volume crescer

## Próximas leituras

- [Telegram Notifications](telegram-notifications.md)
- [n8n](n8n.md)
- [Deployment](deployment.md)
