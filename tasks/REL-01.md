# REL-01 — P1 — Importação transacional de staging

**Estado:** Em revisão. Implementação no [PR draft #212](https://github.com/bernardopg/doctoralia-scrapper/pull/212), head `710f4da8b3af5b7946d75eab5de471d9e23b15eb`; sem merge ou aceite final.

## Problema

Staging preserva cópias verificadas, mas não materializa nem reconcilia todos os dados no banco.

## Pontos de partida

`src/db/snapshot_import.py`, `src/db/models.py`, `src/db/migrations/versions/0002_snapshot_staging.py`, `tests/test_snapshot_import.py`, `tests/test_review_storage_migrations.py`

## Escopo e exclusões

Importar staging para perfis, avaliações, execuções, observações e rascunhos em transação; isolar workspace, garantir idempotência e concorrência, persistir conflitos e produzir contagens de origem/importados/duplicados/rejeitados/pendentes com proveniência. Preservar bytes originais e ambiguidade. A frente paralela mantém `docs/snapshot-migration.md`.

Não ativar leitura de produção nem alterar a frente REL-02; staging sozinho não comprova migração.

## Dependências

Esquema e staging existentes; REL-03 e REL-05 consomem o contrato resultante.

## Critérios de aceite observáveis

Reexecução e concorrência não duplicam nem cruzam workspaces; falha intermediária reverte; conflitos persistem sem associação especulativa; contagens, campos, timestamps e rascunhos conferem com a origem.

## Testes e comandos

`pytest tests/test_snapshot_import.py tests/test_review_storage_migrations.py`; integração adicional somente com `TEST_POSTGRES_URL` de PostgreSQL descartável criado para o teste.

## Evidência exigida

SHA, comandos, relatórios de comparação, caso de rollback e CI; distinguir testes de staging e importação.

## Riscos

Colisão de identidade e rollback incompleto podem causar perda ou associação indevida.

## Evidência observada em 2026-11-05

O agente executor reportou 21 testes pertinentes com PostgreSQL descartável, incluindo isolamento, concorrência, rollback e retomada, além de Black/isort/Flake8/mypy. O gestor conferiu o [CI desse head](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41965168019): os jobs Python 3.11–3.14 e o agregador All Checks Passed concluíram com sucesso. No [log Python 3.14](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41965168019/job/127040387079), a suíte terminou com 526 testes aprovados, incluindo migrações, staging e os dois testes de reconciliação contra o serviço descartável do CI. CodeQL, builds e scans também passaram; o agregador Docker ainda estava pendente na consulta.

Revisão técnica independente e ensaio de migração/restore com cópia representativa continuam pendentes. O importador mantém JSON como backend runtime e conflitos para análise; não há resolução humana implementada ou ativação PostgreSQL. A interpretação UTC de timestamps sem fuso está documentada e precisa de conferência no ensaio com dados existentes.

## Revisão independente e correções pendentes

A revisão do head `54db82d` identificou riscos materiais: rascunho removido reaparece e ordem de staging substitui cronologia; datetime válido emitido pelo scraper é rejeitado como data; contagens fora de INTEGER e caracteres NUL podem impedir retomada; identidade de perfil diverge da normalização JSON; timestamps locais sem fuso recebem UTC indevidamente. O CI verde anterior não cobre esses casos. Correções e regressões PostgreSQL são necessárias antes do aceite e da REL-05.

## Correções da primeira revisão

O head `08a20dad14dc2f2d09e7cc6244766337b74e8a53` adiciona proveniência temporal dos rascunhos e conflitos para divergências/ausências/empates; aceita datetimes de avaliações preservando a data civil; rejeita timestamps de coleta sem fuso, valores fora de INTEGER, NUL/surrogates e URLs ambíguas, preservando a origem no staging. O executor reportou 29 testes com PostgreSQL descartável e checks de estilo/tipos aprovados.

O gestor conferiu o [CI desse head](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41968083947): Python 3.11–3.14 passaram; no [log Python 3.14](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41968083947/job/127049676189), 534 testes foram aprovados, incluindo dez de reconciliação. Docker, CodeQL e Codecov patch também passaram; o Codecov reportou 92,14% no patch total, 91,30% em `snapshot_reconcile.py` e 18 linhas descobertas. Cobertura local reportada pelo executor (91% reconcile,96% staging,93% combinada) é uma medição diferente.

Uma nova revisão independente ainda é exigida. Rascunhos em conflito podem continuar materializados até decisão humana; não podem ser consumidos como aprovados pelo runtime futuro. Snapshots legados sem fuso exigem tratamento explícito de origem no ensaio. Resolução auditável, cutover e ensaio com cópia representativa continuam REL-03/05/09.

## Estado da rechecagem

A rechecagem independente de `08a20da` falhou por limite de uso do provedor antes de produzir conclusão; isso não é aprovação. Em2026-11-05 a orquestração retomou com o mesmo modelo Terra6.1 high após conferir sua disponibilidade. Nova revisão deve ser um novo delegate, preservando o head e os critérios já definidos.

## Rechecagem concluída e ajuste de limites

A revisão independente de `08a20da` executou12 testes em PostgreSQL descartável e reproduziu dois problemas: upgrade0003→0004 deixa snapshots já processados sem proveniência/conflitos e pode reportar pending0 com draft antigo ativo; conversão UTC de timestamps extremos produz OverflowError e interrompe o lote. Os demais cinco findings anteriores foram tratados para novas reconciliações, mantendo as ressalvas documentadas.

O gestor corrigiu o overflow em `39f4b1d` e adicionou regressões para ano0001 com offset+14 e ano9999 com offset−14, exigindo rejeição registrada e importação do snapshot seguinte. Passaram25 testes em PostgreSQL18 descartável recém-criado, nesta ordem: `tests/test_review_storage_migrations.py tests/test_snapshot_import.py tests/test_snapshot_reconcile.py`; o serviço foi removido após o ensaio. Black/mypy e diffcheck pertinentes passaram. A suíte de migração requer banco vazio e deve preceder as demais.

O findingP1 de upgrade/proveniência continua sem aceite e requer correção específica com teste real de migração de0003 e de instalação que já aplicou0004. O runtime futuro não pode interpretar esses rascunhos antigos como aprovados apenas porque um relatório retornou pending0.

## Reparo de upgrade implementado pelo gestor

O agente de correção não entregou mudanças; o gestor assumiu o finding e publicou `79149c6`. A revisão0005 reconstrói estados a partir de observações já reconciliadas, preserva rascunhos ativos/originais, registra incertezas legadas ainda não sinalizadas e atualiza o relatório pending. Usa locks por workspace, não duplica pendências existentes e mantém auditoria em downgrade/re-upgrade. Nenhuma resolução humana é presumida.

Passaram47 testes em PostgreSQL18 descartável, incluindo sete novos testes reais de upgrade de0003/0004, dados em ordem invertida, workspaces distintos, estados mistos, pendências existentes, reinicialização concorrente, reexecução, rollback/retomada, fuso legado incerto e observações incompletas. O serviço descartável foi removido. Black/isort/Flake8/mypy e diffcheck pertinentes passaram. O comando foi: `pytest tests/test_review_storage_migrations.py tests/test_snapshot_import.py tests/test_snapshot_reconcile.py tests/test_snapshot_upgrade.py tests/test_db_init.py -q -o addopts='' --cov=src.db --cov-report=term-missing`, usando apenas TEST_POSTGRES_URL do serviço criado para esse ensaio.

CI e nova revisão independente de `79149c6` ainda pendentes. Os resultados de cobertura/CI de08a20da não são validação desse reparo novo. O aceite integrado continua dependendo de resolução de conflitos e cutover posteriores.

## Integridade das observações legadas

A revisão independente de `79149c6` encontrou um payload parcial contendo apenas o ID que era interpretado como ausência confiável de rascunho. O gestor reproduziu a falha em PostgreSQL descartável e publicou `710f4da`: a observação deve corresponder exatamente ao único item com esse ID nos bytes originais. Divergência, ausência ou duplicidade exigem revisão de integridade; o marcador não copia textos de avaliação ou rascunho. Originais e drafts ativos permanecem preservados.

Passaram 21 testes de `tests/test_snapshot_upgrade.py` e `tests/test_snapshot_reconcile.py`, incluindo payload nulo, somente ID e objeto com campos omitidos. Black, isort, Flake8, mypy e `git diff --check` passaram. O PostgreSQL foi criado exclusivamente para esses testes e removido ao final. Push e SHA remoto confirmados. Os checks remotos consultados de `710f4da` concluíram sem falhas; o relatório Codecov consultado ainda era anterior a esse head, portanto a cobertura nova permanece não confirmada; a revisão anterior foi estática e não constitui validação independente desse novo head. O aceite integrado permanece aberto.
