# REL-01 — P1 — Importação transacional de staging

**Estado:** Em revisão. Implementação no [PR draft #212](https://github.com/bernardopg/doctoralia-scrapper/pull/212), head `54db82df5e3ee52b3ee1a37d9c550e5708e7e7a6`; sem merge ou aceite final.

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
