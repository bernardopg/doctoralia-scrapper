# Armazenamento PostgreSQL (opt-in)

`STORAGE_BACKEND=json` continua sendo o padrão. Com `STORAGE_BACKEND=postgres`, o dashboard passa a ler perfis, coletas, avaliações e rascunhos do PostgreSQL, enquanto os snapshots JSON continuam sendo gravados como cópia de retorno.

## Como funciona

| Operação | `json` | `postgres` |
| --- | --- | --- |
| Coleta (API, worker, Telegram) | grava snapshot JSON | grava snapshot JSON e, em seguida, faz staging (idempotente por checksum) e reconciliação de todo o diretório no banco |
| Leitura do dashboard | snapshots JSON | `scrape_runs`, `review_observations`, `reviews` e `review_drafts` |
| Edição de rascunho | JSON com `draft_edit.version` | recusa (HTTP 409) se houver conflito pendente; senão grava JSON e banco |
| Rascunho com conflito pendente | não existe | aparece como "Conflito de rascunho pendente", sem texto aprovado e com edição bloqueada |

- Edições publicadas com `draft_edit.version` maior que a última aceita não geram conflito (migração `0007_draft_edit_version`). Divergências sem versão continuam sendo conflitos explícitos, resolvidos com `python -m src.db.draft_resolution`.
- Se o banco falhar durante uma coleta, o snapshot JSON já está salvo; o erro é registrado e a próxima sincronização recupera o atraso. `storage_backend.status()` expõe o resultado da última sincronização.
- Avaliações sem identidade estável `doctoralia:<n>` são rejeitadas na reconciliação e não aparecem na leitura do banco; cada coleta informa `collection.rejected_reviews`. Snapshots coletados por versões até a 2.7.2 usam IDs posicionais (`"1"`, `"2"`): **é preciso uma coleta nova antes de ativar o backend.**
- Exclusão e limpeza de snapshots no histórico continuam operando sobre arquivos JSON; com `postgres` o histórico mostra coletas do banco (`db:<run_id>`), que não são apagadas pela interface.

## Cutover

1. Atualize para a versão com a migração `0007` e faça backup: `scripts/backup_restore.sh backup` e `scripts/backup_restore.sh verify <arquivo>`.
2. Faça uma coleta nova de cada perfil com a versão atual (IDs `doctoralia:<n>`).
3. Ensaie numa cópia: `DATABASE_URL=<banco descartável> python -m src.db.review_store sync --data-dir <cópia de data/>`. Confira `reconciled.rejected` e `reconciled.pending`.
4. Na instalação: `python -m src.db.review_store sync --data-dir data` (workspace `default` criado por `init-and-seed`).
5. Resolva conflitos: `python -m src.db.draft_resolution list --workspace-id <id>` e `resolve ...`.
6. Defina `STORAGE_BACKEND=postgres` no `.env` e recrie `api`, `worker` e `dashboard`.
7. Compare a fila de respostas antes e depois (pendentes, sugestões salvas) e acompanhe os logs de sincronização.

## Rollback

1. `python -m src.db.review_store export-drafts --data-dir data`: grava os rascunhos aprovados no banco (incluindo decisões de conflito) no snapshot JSON mais recente de cada perfil, com nova `draft_edit.version`. Rascunhos ainda pendentes não são exportados.
2. Defina `STORAGE_BACKEND=json` e recrie `api`, `worker` e `dashboard`.
3. Os dados do banco permanecem; reativar `postgres` depois reconcilia os snapshots novos.

Downgrade de esquema abaixo de `0006` apaga o histórico de decisões; prefira restaurar o backup do banco.
