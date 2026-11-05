# REL-02 — P0/P1 — Contrato comum de coleta

**Estado:** Em revisão. Implementação no [PR draft #211](https://github.com/bernardopg/doctoralia-scrapper/pull/211), head `6d93948ff3d55c798f7fc34380ae63249c859251`; sem merge ou aceite final.

## Problema

Coleta síncrona e worker podem divergir em persistência, tratamento de falhas e completude; operações bloqueantes afetam o event loop.

## Pontos de partida

`src/api/v1/routers/scrape.py`, `src/jobs/tasks.py`, `src/services/scrape_completeness.py`, `src/dashboard/workspace.py`, `tests/test_scrape_collection_flow.py`, `tests/test_scrape_completeness.py`

## Escopo e exclusões

Unificar serviço síncrono/worker, persistência e erros; mover trabalho bloqueante para execução apropriada; propagar complete/partial/unknown/falha, totais, motivo e duração em API e dashboard. A frente paralela mantém `docs/collection-contract.md`.

Não incluir integrações novas nem chamar coleta parcial de completa.

## Dependências

Independente; REL-05, REL-06 e REL-08 integram o contrato.

## Critérios de aceite observáveis

Os dois caminhos produzem estado e dados equivalentes; falhas e parcialidade aparecem nos consumidores; teste mede responsividade concorrente do event loop.

## Testes e comandos

`pytest tests/test_scrape_collection_flow.py tests/test_scrape_completeness.py tests/test_jobs_tasks.py tests/test_api_endpoints.py` com serviços externos simulados.

## Evidência exigida

SHA, testes de equivalência e concorrência, CI e demonstração API/dashboard; navegador e runtime registrados separadamente.

## Riscos

Mudança de contrato pode quebrar consumidores ou mascarar resultados incompletos.

## Evidência observada em 2026-11-05

O gestor revisou o diff e reexecutou 103 casos sintéticos com saída zero no checkout isolado do PR:

```sh
/home/bitter/development/doctoralia-scrapper/.venv/bin/python -m pytest tests/test_collection_contract.py tests/test_scrape_collection_flow.py tests/test_scrape_completeness.py tests/test_jobs_tasks.py tests/test_api_endpoints.py tests/test_telegram_schedule_service.py -q
```

O agente executor reportou 108 testes e checks Black/isort/mypy aprovados no conjunto que executou. A repetição do gestor cobre o comando acima. CI remoto ainda em execução na consulta; revisão técnica independente pendente. Sem coleta externa, navegador interativo, notificação, migração ou deploy. A visibilidade entre processos continua dependendo de diretório JSON compartilhado. Não marcar esta tarefa como aceita apenas por testes sintéticos.
