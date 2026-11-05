# REL-05 — P1 — Repositórios PostgreSQL e transição

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

Esquema e staging não substituem repositórios runtime nem definem fonte de verdade ou rollback seguro.

## Pontos de partida

`src/db/models.py`, `src/db/init_db.py`, `src/services/workspace_service.py`, `src/dashboard/workspace.py`, `src/jobs/tasks.py`, `src/api/v1/routers/`

## Escopo e exclusões

Implementar contratos e repositórios para API, worker e dashboard, isolamento por workspace, consultas, ordenação, filtros e paginação; transição opt-in JSON→PostgreSQL com recuperação e rollback documentados sem perder edições.

Não ativar por padrão antes de ensaio e aceite; não presumir downgrade sem procedimento comprovado.

## Dependências

REL-01, REL-03 e integração do contrato REL-02.

## Critérios de aceite observáveis

Leituras/escritas consistentes entre consumidores, isolamento e falha do banco explícitos; ida e rollback preservam histórico e edições numa cópia representativa.

## Testes e comandos

`pytest tests/test_workspace_service.py tests/test_db_models.py tests/test_db_init.py` e testes de integração em PostgreSQL descartável.

## Evidência exigida

Comparação JSON/banco, plano de cutover e rollback, logs de ensaio, SHA, CI e runtime.

## Riscos

Duas fontes de verdade podem divergir; rollback após novas escritas exige reconciliação.
