# REL-06 — P1 — Paginação e semântica de datas

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

Paginação real da fonte e distinção entre data de avaliação e coleta precisam de evidência e contrato consistente.

## Pontos de partida

`src/scraper.py`, `src/services/scrape_completeness.py`, `src/api/schemas/common.py`, `src/db/models.py`, `tests/test_scraper_parsing.py`

## Escopo e exclusões

Avaliar paginação real e alternativas ao Selenium sem presumir API; expor datas distintas e suportar ausentes, fuso e limites; integrar paginação server-side de resultados.

Não fazer coleta não autorizada nem inventar endpoint da fonte.

## Dependências

Análise independente; aceite integrado depende de REL-02 e REL-05.

## Critérios de aceite observáveis

Fixtures HTML real anonimizadas cobrem páginas, totais e respostas; datas distintas e ausentes sobrevivem à API, banco e interface; coleta autorizada confere totais e sinaliza parcialidade.

## Testes e comandos

`pytest tests/test_scraper_parsing.py tests/test_scrape_completeness.py tests/test_api_endpoints.py`; roteiro autorizado separado para runtime.

## Evidência exigida

Fixtures anonimizadas, comparação de contagens e fusos, SHA, CI e evidência da coleta autorizada ou lacuna explícita.

## Riscos

HTML e paginação da fonte mudam; dados privados exigem anonimização.
