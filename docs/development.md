[Wiki Home](Home.md) · [Visão Geral](overview.md) · [API REST](api.md) · [Templates](templates.md)

# Desenvolvimento

## Ambiente local

```bash
make install-dev
cp .env.example .env
cp config/config.example.json config/config.json
```

Se quiser rodar a stack inteira com menos atrito, prefira Docker. Use este guia quando o objetivo for desenvolvimento e testes mais finos.

## Comandos úteis

| Comando | Descrição |
|---|---|
| `make install-dev` | instala dependências de desenvolvimento |
| `make lint` | checagens de qualidade |
| `make format` | formatação |
| `make test` | suíte completa |
| `make api` | sobe a API local |
| `make dashboard` | sobe o dashboard local |
| `make run-url URL=...` | scraping rápido |
| `make run-full URL=...` | fluxo mais completo |

## Estrutura do código

| Área | Responsabilidade |
|---|---|
| `src/api/` | schemas, deps e endpoints |
| `src/jobs/` | fila, tasks e execução assíncrona |
| `src/services/` | serviços de domínio, como scheduler Telegram e estatísticas |
| `src/` | scraping, geração, análise e utilitários centrais |
| `templates/` | páginas do dashboard |
| `tests/` | suíte automatizada |

## Padrões que o projeto já segue

- imports internos absolutos: `from src...` e `from config...`
- type hints em código novo
- documentação atualizada junto de features relevantes
- testes obrigatórios para lógica não trivial
- sem `print`; use logger com contexto

## Testes

```bash
pytest -q
pytest --cov=src --cov-report=term-missing
```

Categorias principais:

| Tipo | Foco |
|---|---|
| Unitário | funções puras e normalização |
| Integração | API, Redis, fila e serviços |
| Fluxo | dashboard, scheduler Telegram e jobs |

## Mudanças que exigem atenção extra

### Configuração

Se uma alteração impactar runtime, atualize:

- `.env.example`
- `config/config.example.json`
- a página correspondente em `docs/`

### Scheduler Telegram

Se tocar em notificações, revise:

- `src/services/telegram_schedule_service.py`
- `src/api/schemas/notifications.py`
- `src/api/v1/main.py`
- `src/dashboard.py`
- `docs/telegram-notifications.md`

### Workspace do dashboard

Se tocar em snapshots, histórico ou relatórios, valide também o comportamento do dashboard com dados reais em `data/`.

## Commits

Use Conventional Commits:

- `feat:`
- `fix:`
- `docs:`
- `test:`
- `chore:`

## Checklist antes de fechar um ciclo

- testes verdes
- docs coerentes com o runtime
- nenhuma credencial exposta
- comportamento validado nos fluxos principais afetados

## Próximas leituras

- [Templates](templates.md)
- [Operations](operations.md)
- [Deployment](deployment.md)
