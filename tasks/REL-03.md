# REL-03 — P0 — Identidade, conflitos e rascunhos

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

IDs ausentes, legados ou repetidos e alterações de fingerprint tornam associações automáticas e restauração de rascunhos arriscadas.

## Pontos de partida

`src/services/review_identity.py`, `src/services/review_reconciliation.py`, `src/services/snapshot_storage.py`, `src/services/workspace_service.py`, `tests/test_snapshot_storage.py`

## Escopo e exclusões

Definir reconciliação explícita e resolução auditável de conflitos persistidos, preservando rascunhos, exclusões intencionais, origem e casos ambíguos.

Não presumir identidade por fingerprint ambíguo nem vincular rascunhos automaticamente em dúvida.

## Dependências

Análise independente; integração depende de REL-01 e seus conflitos persistidos.

## Critérios de aceite observáveis

Reordenação, duplicatas, edição, autor ausente, desaparecimento/reaparição, snapshots parciais e concorrência preservam dados; decisão registrada e reproduzível. O importador do PR #212 pode manter rascunhos conflitantes materializados: a resolução deve identificar todas as pendências por avaliação, registrar autor/decisão/versão e impedir que um rascunho pendente seja tratado como aprovado.

## Testes e comandos

`pytest tests/test_snapshot_storage.py tests/test_workspace_service.py tests/test_snapshot_import.py` e casos de integração descartáveis introduzidos pela frente.

## Evidência exigida

Casos e contagens antes/depois, trilha de decisão, SHA, CI; demonstrar recuperação com cópia representativa.

## Riscos

Associação incorreta pode publicar ou apagar rascunhos de outra avaliação.
