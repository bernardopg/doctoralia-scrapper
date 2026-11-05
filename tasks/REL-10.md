# REL-10 — P3 — Release, artefatos e runtime

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

Release requer coerência de versões e prova da publicação e do funcionamento posterior à atualização.

## Pontos de partida

`src/version.py`, `pyproject.toml`, `scripts/verify_release_version.py`, `.github/workflows/release.yml`, `README.md`, `TODO.md`

## Escopo e exclusões

Definir versão pelo escopo realmente entregue, atualizar changelog e documentação, executar gate de release, publicar artefatos planejados e conferir checksums e versões expostas.

v2.8.0 é proposta; nenhum bump, tag, publicação ou deploy nesta ficha de planejamento.

## Dependências

REL-09 e todas as tarefas incluídas aceitas; riscos restantes registrados.

## Critérios de aceite observáveis

SHA final tem CI verde, versão pacote/API/dashboard e notas coerentes; artefatos esperados publicados e verificados; backup anterior e health/readiness, versão e fluxo principal observados após atualização.

## Testes e comandos

`python scripts/verify_release_version.py` conforme interface do script; `make ci`; consultar workflows, release, artefatos e endpoints após publicação.

## Evidência exigida

SHA/tag, links de CI e release, hashes, versões observadas, procedimento de atualização/backup e evidência runtime; não inferir publicação de CI.

## Riscos

Artefato ausente ou versão divergente; deploy e rollback dependem da instalação e aprovação operacional.
