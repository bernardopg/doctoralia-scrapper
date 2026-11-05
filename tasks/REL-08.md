# REL-08 — P2 — UX acessível e estados

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

## Problema

Navegação e feedback podem ocultar pendências, erros e parcialidade, dificultando resposta e recuperação.

## Pontos de partida

`templates/`, `src/dashboard/pages.py`, `src/dashboard/workspace.py`, `docs/dashboard-workspace.md`, `tests/test_dashboard.py`

## Escopo e exclusões

Organizar visão geral, avaliações, respostas, perfis/coletas e configurações; estados de carregamento, vazio, erro, progresso e parcial; responsividade, teclado, rótulos e paginação. Informar publicação manual de sugestões na Doctoralia.

Não prometer multiusuário, licenciamento ou integrações novas como requisitos deste release.

## Dependências

Análise independente; aceite integrado depende de REL-02, REL-03, REL-05 e REL-06.

## Critérios de aceite observáveis

Navegação por teclado e nomes acessíveis; estados distinguem parcial/falha; fluxo avaliação→edição→cópia→histórico→recuperação funciona em tamanhos distintos.

## Testes e comandos

`pytest tests/test_dashboard.py tests/test_dashboard_additional.py`; roteiro de navegador real com dados sintéticos e ferramentas de acessibilidade.

## Evidência exigida

Matriz de telas/tamanhos, navegador, evidências de teclado e estados, SHA, CI e limites.

## Riscos

Mocks podem não reproduzir latência, acessibilidade e falhas reais.
