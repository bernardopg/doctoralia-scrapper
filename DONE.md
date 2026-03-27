# DONE - Main Features

Inventário das entregas principais que já estão maduras para o escopo atual do projeto.

## Plataforma base

- Stack Docker funcional com `api`, `worker`, `dashboard`, `redis`, `selenium` e `n8n`.
- Health checks e limites de recursos definidos para os serviços principais.
- Configuração local compartilhada entre API, worker e dashboard via `config/`.
- Redis consolidado como backbone operacional para fila, métricas e notificações.

## API e processamento

- API FastAPI com execução síncrona e assíncrona.
- Jobs em Redis/RQ com persistência de snapshots em `data/`.
- Health, readiness, statistics, settings e métricas Redis-backed.
- Webhook dedicado para integrações n8n.
- Geração unitária de respostas e análise de qualidade disponíveis por endpoint.

## Dashboard workspace

- Overview operacional com saúde da stack, backlog, timeline e atalhos.
- Páginas dedicadas para perfis, respostas, histórico, relatórios, settings e área do operador.
- Histórico de snapshots com prune e exclusão individual.
- Relatórios com inventário de arquivos, resumo e exportação.
- Favoritos do operador persistidos em configuração.

## Telegram e notificações

- Notifier funcional com teste real de conectividade.
- Página dedicada de agendamentos Telegram no dashboard.
- CRUD completo de schedules pela API e pelo dashboard.
- Execução manual de agendamento, histórico persistido e anexos em disco.
- Relatórios `simple`, `complete` e `health`, com scraping novo opcional e geração opcional de respostas.

## Documentação e branding

- README refeito como landing page visual do repositório.
- Wiki organizada em `docs/` com hub, navegação e páginas temáticas.
- Assets próprios do projeto: logo, banner, social card e diagramas SVG.
- Screenshots reais do dashboard incluídos na documentação.

## Qualidade e validação

- Imports internos padronizados em formato absoluto.
- Cobertura ampliada nas áreas críticas de API, Redis, dashboard, jobs e Telegram.
- Estado validado desta linha: `250 passed` e `74%` de coverage.

## O que este arquivo não lista

Itens ainda abertos ou evoluções futuras ficam em [TODO.md](TODO.md).
