# REL-07 — P2 — Inventário n8n e normalização desacoplada

**Estado:** Em revisão parcial. Implementação no [PR draft #214](https://github.com/bernardopg/doctoralia-scrapper/pull/214), head `6b89a8dae2dadc86e17e695d1560537f965f731d`; inventário local/externo e ensaio de retorno ainda pendentes.

## Problema

Consumidores e workflows existentes podem depender da distribuição n8n e da normalização acoplada.

## Pontos de partida

`src/integrations/n8n/normalize.py`, `tests/n8n/test_normalize.py`, `examples/n8n/`, `docs/n8n.md`, `docker-compose.yml`

## Escopo e exclusões

Inventariar workflows, callbacks e consumidores; propor substituições, exportação e migração; extrair normalização compartilhada e preservar compatibilidade; revisar Compose, proxy e documentação.

Não remover n8n nem apagar `n8n-data` antes de inventário e migração comprovados; não disparar webhooks reais.

## Dependências

Inventário e extração independentes; integração de resultados deve respeitar REL-02.

## Critérios de aceite observáveis

Inventário identifica responsáveis e destinos; testes de contrato passam para consumidores existentes; roteiro de exportação e retorno preserva dados.

## Testes e comandos

`pytest tests/n8n/test_normalize.py tests/n8n/test_api.py`; validar configuração Compose sem iniciar stack real.

## Evidência exigida

Inventário revisado, fixtures de contrato, ensaio isolado de exportação/retorno, SHA e CI.

## Riscos

Workflows externos não observados podem ser interrompidos.

## Execução autorizada

Extrair normalização compartilhada para módulo neutro com shim de importação n8n e testes de equivalência, sem mudar contratos. Inventariar fontes e consumidores do repositório e metadados da instalação local apenas por leitura, se houver acesso seguro; preservar workflows, callbacks e volume n8n-data. Não concluir inventário externo sem evidência e não remover o serviço neste PR. Dados de workflows, credenciais e URLs com segredos não devem ser commitados.

## Entrega de normalização e inventário parcial

O PR #214 extrai a normalização para `src/normalization.py`, conserva o caminho antigo como shim e documenta fluxos, dependências e gates em `docs/integration-inventory.md`. O executor reportou 157 testes direcionados, Black, isort, Flake8, mypy e validação dos três conjuntos Compose com dados fictícios aprovados. O gestor confirmou no remoto o head e os checks concluídos sem falhas, incluindo Codecov, CI, Docker e CodeQL; revisão independente solicitada.

O inventário identifica os exemplos e contratos do repositório e a existência do serviço/volume local, mas não verifica workflows instalados, responsáveis e consumidores externos. Exportação/restauração não ensaiadas. Serviço e volume n8n foram preservados; esta entrega não atende aos gates de remoção. A integração dos imports com #211 também permanece pendente.
