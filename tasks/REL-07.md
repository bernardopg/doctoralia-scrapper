# REL-07 — P2 — Inventário n8n e normalização desacoplada

**Estado:** Planejado. **Evidência atual:** planejamento; nenhum teste ou implantação desta ficha é afirmado por este PR.

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
