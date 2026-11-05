# REL-01 — P1 — Importação transacional de staging

**Estado:** Em andamento. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

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
