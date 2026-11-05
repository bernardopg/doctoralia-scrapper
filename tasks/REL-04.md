# REL-04 — P0 — Auditoria XSS em navegador

**Estado:** Em revisão. Implementação no [PR draft #213](https://github.com/bernardopg/doctoralia-scrapper/pull/213), head `3b1200488c82d8f3d232f42a308c852fa2c14fef`; sem merge ou aceite final.

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

## Evidência reportada pelo executor

Regressão em Chromium 156, dados sintéticos e API simulada; o agente reportou execução do payload de relatório antes da correção e ausência após. Reportou 87 testes Python e Black/isort/Flake8/mypy pertinentes aprovados. Clipboard foi simulado; outros navegadores, autenticação de produção e serviços reais não foram validados. A preparação inicial fez um GET à API local que recebeu 401, sem payload; o runner final bloqueia chamadas externas. Revisão independente, conferência do isolamento e CI final ainda pendentes. Matriz e comandos em `docs/dashboard-security-audit.md` no PR de implementação.
