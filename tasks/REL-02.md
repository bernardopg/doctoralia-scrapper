# REL-02 — P0/P1 — Contrato comum de coleta

**Estado:** Em revisão. Implementação no [PR draft #211](https://github.com/bernardopg/doctoralia-scrapper/pull/211), head `48cfbe84c938ec4269a2ef3c37fa2cf8723d30ff`; sem merge ou aceite final.

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

## Correções após revisão e CI

O CI do head `6d93948` falhou no mesmo teste n8n em Python 3.11–3.14: a fixture não fornecia `data_dir` e ainda assumia completude sem metadados. O gestor corrigiu a fixture com persistência temporária verificável e casos complete/partial/unknown. Corrigiu também a autoridade de rascunhos para ordem cronológica, incluindo parciais posteriores e ausência/limpeza de rascunho. O head `1a7c952` contém essas correções; 152 testes sintéticos passaram no conjunto anterior acrescido de `tests/n8n/test_api.py` e das regressões de cronologia. Black/isort/mypy pertinentes passaram. O CI desse novo head ainda precisa concluir.

Permanecem findings da revisão para implementação: acesso identificado a avaliações/rascunhos de snapshots parciais no dashboard, sem alterar a visão corrente completa; e preservação da causa real de falhas Selenium após retries, com regressão pelo caminho real do scraper. REL-02 continua sem aceite final.

## Segunda entrega: snapshots selecionados e falhas Selenium

O head `dc2d9ef98107d6897fd8de6e426c23108f0065ea` do PR #211 implementa acesso pelo histórico aos reviews/rascunhos de um snapshot identificado, edição no arquivo selecionado e validação de perfil, caminho e links simbólicos. A visão completa continua padrão. Exceções Selenium são propagadas após retries e expostas como tipo seguro; inicialização esgotada usa `BrowserSetupError`.

O gestor inspecionou o diff desde `1a7c952` e reexecutou 276 testes, todos aprovados:

```sh
/home/bitter/development/doctoralia-scrapper/.venv/bin/python -m pytest tests/test_collection_contract.py tests/test_partial_snapshot_access.py tests/test_jobs_tasks.py tests/test_scrape_collection_flow.py tests/test_scrape_completeness.py tests/test_api_endpoints.py tests/n8n/test_api.py tests/test_workspace_service.py tests/test_dashboard.py tests/test_dashboard_additional.py tests/test_responses_rendering.py tests/test_telegram_schedule_service.py tests/test_scraper.py tests/test_scraper_parsing.py -q -o addopts=''
```

Execução no checkout isolado da implementação, sem serviços externos. CI do novo head e revisão independente do novo diff ainda pendentes; sem teste visual interativo. A cobertura de 92,5% reportada pelo Codecov refere-se ao head anterior `1a7c952` e não prova a cobertura do novo commit. A combinação dos templates com o PR #213 precisará de validação integrada.

## Segunda revisão: caminhos reais de persistência

A revisão de `dc2d9ef` confirmou o acesso ao parcial e a fixture n8n, mas reproduziu dois problemas: `save_data` real reconcilia novamente usando o completo preferido e pode ressuscitar um rascunho antigo, divergindo do resultado retornado pela API; uma edição em snapshot histórico não tem autoridade temporal própria e pode se perder numa coleta posterior. Também confirmou que setup Selenium esgotado ainda é convertido em `BrowserSetupError`, perdendo o tipo original. A próxima correção deve usar reconciliação única e autoridade de edição explícita, com testes usando `save_data` real, não um gravador substituto.

O Codecov de `dc2d9ef` reportou patch83,54%,13 linhas descobertas. O gestor removeu tratamentos ValueError indevidos em rotas que não selecionam snapshot e ampliou regressões de seleção inválida/sem perfil;85 testes de acesso parcial/dashboard passaram. Esse ajuste está em `d4a83fd`, mas não encerra os problemas de persistência/setup acima.

## Reconciliação única e autoridade explícita de edição

O head `48cfbe84c938ec4269a2ef3c37fa2cf8723d30ff` remove a reconciliação duplicada da publicação real, registra versões de edição e tombstones para limpezas e preserva a última exceção Selenium de setup após cleanup/retries. A entrega usa o `save_data` real sob lock e mantém resultado publicado e retornado equivalentes.

O executor reportou 322 testes sintéticos, com rede desabilitada, e Black/isort/Flake8/mypy pertinentes aprovados. O gestor reexecutou 46 testes com saída zero:

```sh
/home/bitter/development/doctoralia-scrapper/.venv/bin/python -m pytest tests/test_publication_real.py tests/test_collection_contract.py tests/test_partial_snapshot_access.py -q -o addopts=''
```

O CI de `48cfbe8` concluiu sem falhas em Python 3.11–3.14; o job Python 3.14 do [run 41999573837](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41999573837) registrou 572 testes aprovados. Codecov aprovou as linhas modificadas cobertas. Isso não substitui revisão independente da nova autoridade de edição nem teste integrado com os templates de #213. Revisão independente solicitada; sem aceite final, coleta externa, deploy ou validação visual combinada.
