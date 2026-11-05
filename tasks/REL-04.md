# REL-04 — P0 — Auditoria XSS em navegador

**Estado:** Em andamento. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

Correções de renderização já entregues não comprovam todos os contextos e fluxos em navegador real.

## Pontos de partida

`templates/`, `src/dashboard/pages.py`, `src/dashboard/reports.py`, `tests/test_responses_rendering.py`, `tests/test_dashboard.py`

## Escopo e exclusões

Auditar avaliações, perfis e respostas em texto, atributos, URLs e ações; validar edição, cópia, histórico e relatórios com entradas hostis inertes.

Não enviar payloads a serviços reais nem considerar testes de template prova de execução em navegador.

## Dependências

Independente das primeiras frentes.

## Critérios de aceite observáveis

Payloads não executam nem criam URLs/ações inseguras em todos os contextos auditados; falhas corrigidas têm regressão.

## Testes e comandos

`pytest tests/test_responses_rendering.py tests/test_dashboard.py`; executar roteiro em navegador real com dados locais sintéticos.

## Evidência exigida

Matriz de páginas/contextos, navegador e versão, capturas/logs, SHA e CI; registrar limites.

## Riscos

Contextos dinâmicos ou dados históricos podem escapar da cobertura.
