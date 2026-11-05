# REL-09 — P1/P3 — CI, backup e instalações

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

A entrega precisa validar migração e recuperação além dos testes existentes e preservar instalações atuais.

## Pontos de partida

`.github/workflows/ci.yml`, `.github/workflows/docker.yml`, `scripts/backup_restore.sh`, `src/db/migrations/`, `tests/test_redis_integration.py`

## Escopo e exclusões

Preparar serviços descartáveis em CI; testar migrações, inicialização concorrente, restrições, backup/restore, downgrade documentado e instalação limpa e existente em cópias isoladas.

Nunca usar dados, containers ou volumes reais; não executar testes Redis destrutivos sem URL descartável explícita.

## Dependências

Preparação independente; aceite final depende das frentes incluídas no release.

## Critérios de aceite observáveis

Restore confere contagens e conteúdo; falha/retomada e concorrência são verificadas; instalação limpa e atualização de cópia existente passam com rollback definido.

## Testes e comandos

`make ci` e testes específicos com `TEST_REDIS_URL` descartável e `TEST_POSTGRES_URL` de serviço descartável criado para o teste; executar backup/restore somente em ambiente isolado.

## Evidência exigida

Comandos, configuração sem segredos, SHA, jobs finais, relatórios de restore e comparação de dados e limites.

## Riscos

Restore parcial, serviços externos ou credenciais reais podem invalidar ensaio e causar perda.
