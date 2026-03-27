[Wiki Home](Home.md) · [Quickstart](quickstart.md) · [Operations](operations.md) · [Telegram Notifications](telegram-notifications.md)

![Workflow principal](assets/workflow-platform.svg)

# Visão Geral e Arquitetura

## Tese do projeto

Este repositório não tenta resolver só a coleta. Ele resolve a rotina inteira:

1. entrar com uma URL ou agenda recorrente
2. executar scraping de forma resiliente
3. normalizar e enriquecer o resultado
4. persistir snapshots e histórico
5. distribuir a informação por dashboard, API, n8n ou Telegram

## Componentes principais

| Componente | Papel |
|---|---|
| `src/scraper.py` | Coleta e extração de reviews do Doctoralia |
| `src/response_quality_analyzer.py` | Sentimento, qualidade e heurísticas |
| `src/response_generator.py` | Respostas locais ou com provedores externos |
| `src/api/v1/main.py` | Interface HTTP, jobs, settings, metrics e notificações |
| `src/jobs/tasks.py` | Pipeline executado pelo worker |
| `src/services/telegram_schedule_service.py` | Scheduler Telegram Redis-backed |
| `src/dashboard.py` | Workspace Flask para operação diária |
| Redis / RQ | Fila, métricas, histórico e schedules |
| Selenium | Browser remoto para scraping |

## Três superfícies de entrada

### Dashboard

Voltado para operação humana. O operador inicia scraping, acompanha pendências, consulta histórico, exporta relatórios e agenda notificações sem sair da interface.

### API

Voltada para integrações e clientes programáticos. Expõe execução síncrona, jobs assíncronos, métricas, health e CRUD do scheduler Telegram.

### n8n

Voltado para orquestrações externas. Entra quando o fluxo precisa de branching, múltiplos destinos ou sistemas adicionais além do Telegram.

## Backbone real: Redis

Hoje Redis é uma peça central e não apenas fila.

| Uso | O que fica lá |
|---|---|
| Jobs | filas RQ e estados transitórios |
| Métricas da API | volume, latência, falhas, requests em andamento |
| Scheduler Telegram | definições, locks e histórico |
| TTL e rate limiting | controles operacionais e deduplicação |

## Fluxo resumido

1. Uma URL entra por dashboard, API ou n8n.
2. A API decide entre execução síncrona ou job assíncrono.
3. O worker usa Selenium para coletar a página.
4. O resultado é normalizado.
5. Opcionalmente entram análise de sentimento e geração de respostas.
6. O snapshot vai para `data/`.
7. O dashboard lê esse snapshot para exibir workspace, relatórios e histórico.
8. O Telegram pode consumir o resultado por envio manual ou recorrente.

## Diretórios importantes

| Diretório | Conteúdo |
|---|---|
| `src/` | código principal |
| `config/` | settings e templates |
| `templates/` | páginas HTML do dashboard |
| `static/` | CSS e assets do dashboard |
| `data/` | snapshots, notificações, relatórios e arquivos gerados |
| `examples/n8n/` | workflows prontos |
| `docs/` | wiki do repositório |

## Decisões arquiteturais que importam

- O dashboard não reimplementa a lógica de negócio. Ele faz proxy da API e organiza a experiência operacional.
- Snapshots persistidos são a fonte do workspace web, não o payload transitório do RQ.
- O scheduler Telegram roda dentro da API, o que simplifica o deployment, mas cria dependência direta do processo `api`.
- Métricas da API são Redis-backed para evitar visão quebrada em múltiplos processos.

## Limites atuais

- O scheduler ainda depende de um processo único da API.
- O rate limiting global de entrada ainda não está consolidado como middleware completo.
- `src/scraper.py` e `src/response_generator.py` ainda têm margem de cobertura e simplificação.

## Leitura recomendada depois desta

- [Dashboard Workspace](dashboard-workspace.md)
- [Telegram Notifications](telegram-notifications.md)
- [Operations](operations.md)
