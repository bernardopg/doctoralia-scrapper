# 🧪 Desenvolvimento

## Ambiente

```bash
make install-dev   # dependências + extras
override? pip install -r requirements.txt
```

## Make Targets Úteis

| Comando | Descrição |
|---------|-----------|
| make install | Produção básica |
| make install-dev | Dev completo |
| make lint | flake8 / mypy / etc. |
| make format | black + isort |
| make test | pytest completo |
| make test-unit | unit tests |
| make test-integration | integração |
| make security | safety + bandit |
| make clean | remove artefatos |

## Estrutura de Código

| Arquivo | Função |
|---------|--------|
| `src/scraper.py` | Lógica principal de scraping |
| `src/multi_site_scraper.py` | Extensão futura multi-plataforma |
| `src/response_generator.py` | Geração baseada em templates |
| `src/response_quality_analyzer.py` | Métricas de sentimento/qualidade |
| `src/api.py` | FastAPI / endpoints |
| `src/performance_monitor.py` | Métricas internas |
| `src/telegram_notifier.py` | Envio de notificações |

## Padrões de Código

- Type hints obrigatórios em novas funções
- Docstrings estilo Google ou concisas com objetivo claro
- Imports agrupados: stdlib / terceiros / internos
- Evitar lógica complexa sem testes associados

## Testes

```bash
pytest -q
pytest --cov=src --cov-report=term-missing
```

Estrutura:

- `tests/test_*.py` (atual)
- Adicionar `fixtures/` para dados reutilizáveis

## Estratégia de Testes

| Tipo | Foco |
|------|------|
| Unit | Funções puras / parsing |
| Integração | Fluxo scraping + análise |
| Contrato | Formato de respostas da API |

## Logs & Debug

```python
logger.debug("extraindo bloco", extra={"url": url, "step": step})
```

Não usar prints. Em falhas críticas incluir `exc_info=True`.

## Erros & Exceções

Criar exceções específicas quando necessário (ex: `ScrapingError`, `RateLimitError`).

## Feature Flags / Config

Adicionar chaves novas no `config/config.example.json` e documentar em `docs/templates.md` se impactar templates ou comportamento de resposta.

## Commits

Seguir Conventional Commits:

- feat:
- fix:
- docs:
- test:
- chore:

## Pull Requests (Checklist Interno)

- [ ] Testes verdes
- [ ] Lint sem warnings críticos
- [ ] Documentação atualizada (se aplicável)
- [ ] Sem TODOs pendentes críticos
- [ ] Sem credenciais acidentais

## Performance

- Medir duração total e por etapa antes de otimizar
- Evitar micro-otimizações prematuras
- Abrir issue se latência média > alvo definido

## Roadmap Técnico (Sugestivo)

| Tema | Próximo Passo |
|------|---------------|
| Observabilidade | Exportador Prometheus |
| Armazenamento | Abstrair persistence para DB |
| Scraping | Introduzir rotas proxy opcionais |
| Templates | Suporte LLM com fallback |
| Segurança | JWT + escopos |

---
Dúvidas frequentes? Ver `CONTRIBUTING.md` ou abrir issue.
