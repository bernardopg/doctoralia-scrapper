# 🛠️ Operações & Monitoramento

## Objetivo

Centralizar práticas de operação, saúde, logs, automação e recuperação.

## Health & Status

| Endpoint | Uso |
|----------|-----|
| `/v1/health` | Verifica serviço básico |
| `/v1/ready` | Checa dependências (Redis, etc.) |
| `/v1/statistics` | Estatísticas de scraping agregadas |
| `/v1/metrics` | Métricas de performance da API |

## Workspace Web

Páginas operacionais principais:

- `/`: overview consolidado do workspace
- `/profiles`: análise por perfil com filtros por data
- `/responses`: fila de reviews sem resposta e geração manual
- `/history`: limpeza de snapshots antigos e acompanhamento dos arquivos persistidos
- `/reports`: visão analítica de storage, timeline e candidatos de limpeza
- `/me`: perfil do operador e favoritos
- `/settings`: configuração de scraping, integrações e provedores de IA

## Fluxo Assíncrono de Scraping

- Jobs assíncronos agora persistem um snapshot JSON em `data/` ao final de uma execução bem-sucedida.
- `overview`, `profiles`, `responses`, `history` e `reports` leem esses snapshots persistidos, não o payload transitório do RQ.
- O status exibido em `/history` e em `/api/tasks` usa o `status` lógico do resultado (`completed` ou `failed`), e não apenas o estado bruto de `FinishedJobRegistry`.
- IDs de reviews são normalizados como `string` no resultado unificado e no snapshot salvo para evitar falhas de validação no worker.
- Se um job falhar antes de salvar o snapshot, ele não deve aparecer nas páginas do workspace; nesse caso, verifique `/history`, `/api/tasks/<job_id>` e os logs do worker.

## Logs

- Local: `data/logs/` ou `logs/` (conforme config)
- Rotacionar (recomendado >30 dias): script cron + `find -mtime +30 -delete`
- Formato: preferir JSON estruturado onde possível

## Diagnóstico Rápido

```bash
make health
python scripts/system_diagnostic.py
python scripts/monitor_scraping.py
```

## Automação (Daemon)

| Comando | Função |
|---------|--------|
| `make daemon` | Loop contínuo |
| `make daemon-debug` | Verbose |
| `make stop` | Interrompe |
| `make status` | Estado atual |

## Agendamento (Cron Externo / n8n)

Sugerido usar n8n + agendadores em vez de cron local para flexibilidade.

## Backup

| Item | Caminho | Frequência |
|------|---------|------------|
| Extrações | `data/extractions/` | Diário |
| Respostas | `data/responses/` | Diário |
| Config local | `config/config.json` | Ao alterar |
| Logs críticos | `data/logs/*.log` | Semanal |

Sugestão script simples:

```bash
tar -czf backup_$(date +%Y%m%d).tgz data/extractions data/responses
```

## Retenção Sugerida

| Tipo | Retenção | Ação |
|------|----------|------|
| Logs brutos | 30 dias | Rotacionar |
| Extrações completas | 90 dias | Agregar resumido |
| Respostas finais | 180 dias | Arquivo frio |

## Troubleshooting (Checklist)

| Sintoma | Verificar |
|---------|-----------|
| Timeout constante | Conectividade / bloqueio site / delays curtos |
| Nenhuma avaliação | Mudança de layout / seletor quebrado |
| Resposta vazia | Exceção silenciosa / logs de erro |
| Jobs pendentes eternos | Worker parado / Redis inacessível |
| Job concluído sem aparecer no workspace | Verificar se o snapshot foi salvo em `data/` e se o job terminou como `failed` lógico |
| Webhook inválido | Assinatura ou timestamp expirado |

## Aumentando Robustez

- Ajustar backoff para plataformas mais lentas
- Introduzir proxies se volume aumentar
- Habilitar exportador de métricas (future) para Prometheus

## Alertas (Sugestão)

| Evento | Ação |
|--------|------|
| Falha > N tentativas | Notificar canal de suporte |
| Queda brusca de rating | Alerta urgente |
| Sentimento negativo > limiar | Revisão manual |
| Erro de parsing recorrente | Abrir incidente |

## Recarga de Configuração

Alterar `config/config.json` → reiniciar processo (ou recarregar se implementado hot reload no futuro).

## Segurança Operacional

- Revogar chave API em caso de vazamento
- Regenerar `WEBHOOK_SECRET` e atualizar n8n
- Auditar logs para evitar vazamento de PII

## Scripts Úteis

| Script | Objetivo |
|--------|----------|
| `scripts/system_diagnostic.py` | Checagem ampla |
| `scripts/monitor_scraping.py` | Monitor simplificado |
| `scripts/daemon.py` | Controle do loop contínuo |
| `scripts/backup_restore.sh` | Rotinas de backup/restore |

## Escalonamento

- Multiplicar workers (containers separados) → filas isoladas por prioridade (futuro)
- Parâmetros adaptativos de delay por plataforma

## Planejado (Operações Futuras)

| Feature | Status |
|---------|--------|
| Exportador Prometheus | Planejado |
| Painel Grafana | Planejado |
| Reprocessamento incremental | Em avaliação |
| Detector automático de mudança de layout | Ideia |

---
Para detalhes de arquitetura consulte `docs/overview.md`. Para deployment: `docs/deployment.md`. Para o fluxo do dashboard e geração: `docs/dashboard-workspace.md`.
