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

## Revisão independente e correções pendentes

O CI do head `3b12004` concluiu com sucesso, mas a revisão independente identificou três lacunas: `DashboardServices._get_runtime_config` ainda pode ler configuração persistida; bloqueio de requests e roteamento apenas da página não garantem isolamento de rede de todo o processo/navegador; fixtures não demonstram corretamente a codificação de identificadores e vários campos da matriz. A revisão não executou o runner por esses limites e não confirmou uma brecha XSS remanescente nos caminhos inspecionados.

O gestor confirmou disponibilidade de namespaces de usuário/rede (`unshare --user --map-root-user --net true` passou nesta máquina). A correção deve isolar servidor e navegador no mesmo namespace, garantir apenas loopback efêmero, bloquear leitura de configuração real, cobrir testes negativos e limpar processos próprios mesmo em falhas iniciais. Identificadores com delimitadores URL, contadores, relatórios e histórico de notificações precisam de asserts específicos. A evidência anterior de Chromium não encerra esses critérios.

## Correção de isolamento entregue

O head `a99b2ac1a8673e1b996b6de458eaa13eb46c28df` do PR #213 passou no CI remoto. O executor reportou runner Flask/Chromium em namespace apenas loopback, configuração sintética de ambos os componentes, provas negativas de rede/configuração e regressões específicas por campo e identificador. Reportou87 testes Python e runner Chromium156.0.8078.4 aprovados; remover encoding de perfil/tarefa fez os testes falharem, e falha simulada de browser launch limpou o temporário. A auditoria de arquivos cobre operações Python e não é sandbox de filesystem; clipboard/APIs seguem simulados. Revisão independente do novo head permanece pendente.
