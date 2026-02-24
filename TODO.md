# TODO - Doctoralia Scraper

Lista organizada de tarefas pendentes, melhorias e features planejadas.

---

## 🔴 Prioridade Alta — Refatoração Estrutural

### Correções Críticas (src/)

- [x] Renomear `DoctoraliaScraper` em `multi_site_scraper.py` → `DoctoraliaMultiSiteScraper` (conflito de nomes com `scraper.py`)
- [x] Corrigir `src/jobs/tasks.py` — construtores sem args obrigatórios, métodos inexistentes (`scrape_doctor_reviews` → `scrape_reviews`), assinatura errada do `ResponseGenerator`
- [x] Remover `src/api_server.py` (API legada duplicada) — toda funcionalidade já existe em `src/api/v1/main.py`
- [x] Mover modelos Pydantic exclusivos de `api_server.py` (Settings, Quality Analysis) para `src/api/schemas/settings.py`
- [x] Migrar endpoints úteis de `api_server.py` que não existem em `src/api/v1/` (quality analysis, settings, statistics) para a API v1

### Duplicação de Código

- [x] Extrair lógica de estatísticas duplicada (`_get_scraper_stats`, `_process_data_files`, `_update_platform_stats`) de `api_server.py` e `dashboard.py` para um serviço compartilhado (`src/services/stats.py`)
- [x] Mover `EnhancedErrorHandler` de `performance_monitor.py` para `error_handling.py` (onde já existe `retry_with_backoff` — duas implementações de retry)
- [x] Remover código de exemplo morto no nível do módulo em `circuit_breaker.py` (`scraping_circuit`, `api_circuit`, `scrape_page_protected`, `call_external_api`)
- [x] Remover código de exemplo morto em `error_handling.py` (`scrape_with_retry` — nunca usado)

### Imports e Estrutura de Pacote

- [x] Eliminar hacks de `sys.path.insert()` em `api_server.py`, `dashboard.py`, `telegram_notifier.py`
- [ ] Padronizar imports: escolher entre relativos (`from .scraper`) ou absolutos (`from src.scraper`) consistentemente
- [x] Remover try/except com fallback para `None` nos imports de `api_server.py` e `dashboard.py` — mascara erros reais

### Docker e Deploy

- [x] Adicionar health checks (liveness/readiness probes) no Dockerfile e docker-compose
- [x] Definir resource limits (CPU/memória) no docker-compose para cada serviço
- [ ] Configurar HTTPS/TLS no deploy (certificados, reverse proxy)
- [ ] Adicionar logging aggregation (ELK stack ou Loki)

---

## 🟡 Prioridade Média

### Dashboard e Web UI

- [ ] Adicionar distribuição de sentimento nos relatórios
- [ ] Implementar comparação temporal de métricas (semana atual vs anterior)
- [ ] Adicionar filtro por médico e período na página de relatórios
- [ ] Implementar visualização detalhada de arquivo individual na página de relatórios
- [ ] Adicionar indicadores de status em tempo real no dashboard (API conectada, Selenium ativo, Redis online)

### API e Backend

- [ ] Implementar mecanismo de limpeza/arquivamento de jobs antigos no Redis
- [ ] Adicionar rate limiting por IP/API key nos endpoints da API
- [ ] Implementar paginação nos endpoints que retornam listas grandes
- [ ] Adicionar cache de respostas para endpoints frequentes (stats, health)
- [ ] Melhorar métricas para suporte multi-processo (Prometheus ou Redis-backed)
- [ ] Adicionar endpoint para download direto de arquivo de dados específico
- [ ] Implementar WebSocket para progresso de scraping em tempo real (substituir polling)

### Scraping

- [ ] Melhorar validação de URLs (aceitar variações de domínio, limpar parâmetros desnecessários)
- [ ] Adicionar modo de scraping incremental (apenas reviews novos desde última execução)
- [ ] Implementar detecção e tratamento de CAPTCHAs
- [ ] Adicionar proxy rotation para evitar bloqueios
- [ ] Implementar scraping de múltiplos médicos em paralelo

### Testes

- [ ] Criar testes end-to-end do workflow completo (scrape → analyze → generate → notify)
- [ ] Implementar testes de carga/stress para a API
- [ ] Adicionar testes de memory leak para execuções longas
- [ ] Criar testes de integração com Redis real (não mockado)
- [x] Adicionar testes para os endpoints de reports e settings proxy

### Scripts e Automação

- [ ] Implementar `scripts/backup_restore.sh` (referenciado mas vazio/incompleto)
- [ ] Adicionar script de migração de dados entre versões
- [ ] Configurar supervisord ou systemd para o daemon em produção
- [ ] Adicionar rotação automática de logs antigos

---

## 🔵 Prioridade Baixa

### Integrações

- [ ] Implementar integração com OpenAI para geração de respostas (variável `OPENAI_API_KEY` já existe no `.env.example`)
- [ ] Criar adaptadores para outras plataformas no multi-site scraper (ZocDoc, Healthgrades, Google Reviews)
- [ ] Documentar e validar workflows de exemplo do n8n (`examples/n8n/`)
- [ ] Adicionar integração com Slack como alternativa ao Telegram
- [ ] Implementar webhook genérico para notificações (além do n8n)

### Qualidade de Código

- [ ] Completar type hints faltantes em `src/dashboard.py` e `src/health_checker.py`
- [ ] Adicionar validação de schema JSON nos dados de reviews
- [ ] Criar configs por ambiente (dev/staging/production)
- [ ] Remover `noqa` comments desnecessários e corrigir os issues subjacentes
- [ ] Adicionar JSON Schema para validação do `config.json`

### Documentação

- [ ] Expandir `docs/deployment.md` com guia completo de produção
- [ ] Criar guia de troubleshooting com problemas comuns e soluções
- [ ] Documentar API contracts manualmente (além do auto-generated OpenAPI)
- [ ] Adicionar diagramas de sequência para os fluxos principais
- [ ] Criar runbook de operações para incidentes em produção

### Performance

- [ ] Implementar cache de extrações para evitar re-scraping
- [ ] Otimizar health checker para não fazer requests de rede a cada verificação
- [ ] Lazy loading do NLTK data (evitar bloqueio na primeira chamada)
- [ ] Adicionar connection pooling para requests HTTP

---

## ✅ Concluído

- [x] Criar `worker-entrypoint.sh` referenciado no Dockerfile
- [x] Corrigir health check do Selenium na API (`src/api/v1/main.py`)
- [x] Validar `.env` no startup dos serviços
- [x] Corrigir `circuit_breaker.py` — `CircuitBreakerOpenException` em vez de `Exception` genérica
- [x] Fix `sys.path` para resolução de imports em `api_server.py` e `dashboard.py`
- [x] Implementar progresso em tempo real no scraping via callbacks
- [x] Adicionar polling automático na página de histórico
- [x] Corrigir caminho de dados (`data/` em vez de `data/scraped_data/`)
- [x] Suporte dual de formato de dados (flat e nested)
- [x] Persistir dados de scraping via API
- [x] Implementar página de relatórios funcional (listagem, resumo, exportação CSV/JSON)
- [x] Trocar URL hardcoded do `settings.html` por proxy do dashboard
- [x] Adicionar rotas proxy para settings no dashboard
- [x] Fix `request.get_json()` com `force=True` no quality-analysis
- [x] Download automático do NLTK `punkt_tab`
- [x] Adicionar testes para as rotas Flask do Dashboard
- [x] Implementar gráficos de tendência no dashboard
- [x] Renomear `DoctoraliaScraper` em `multi_site_scraper.py` → `DoctoraliaMultiSiteScraper`
- [x] Corrigir `src/jobs/tasks.py` — construtores, métodos e assinaturas
- [x] Remover `src/api_server.py` — modelos e endpoints migrados para API v1
- [x] Criar `src/api/schemas/settings.py` com modelos de Settings e Quality Analysis
- [x] Migrar endpoints de quality analysis, statistics e settings para `/v1/`
- [x] Criar `src/services/stats.py` — serviço compartilhado de estatísticas (elimina duplicação)
- [x] Mover `EnhancedErrorHandler` para `error_handling.py`
- [x] Eliminar hacks de `sys.path.insert()` em `dashboard.py` e `telegram_notifier.py`
- [x] Remover try/except com fallback para `None` nos imports do `dashboard.py`
- [x] Adicionar health checks (liveness/readiness) no Dockerfile e docker-compose
- [x] Definir resource limits (CPU/memória) no docker-compose para todos os serviços
- [x] Adicionar testes para reports (files, summary, export JSON/CSV) e settings proxy (503 quando API indisponível)

---

## Notas

- **Python**: Projeto roda em Python 3.14 (Arch Linux); lxml 6.0.2+ necessário
- **Dados**: 272 arquivos JSON em `data/`, ~10.880 reviews coletados
- **Cobertura de testes**: ~87% (132 test methods em 18 arquivos)
- **Serviços**: API (FastAPI :8000), Dashboard (Flask :5000), Redis (:6379), Selenium (:4444)
- **Estrutura recomendada para `src/`**: reorganizar em subpacotes temáticos (core, responses, notifications, monitoring, infrastructure) — ver seção de Refatoração Estrutural
