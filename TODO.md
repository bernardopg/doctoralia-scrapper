# TODO - Doctoralia Scraper

Lista organizada de tarefas pendentes, melhorias e features planejadas.

---

## Prioridade Alta

### Bugs e Correções Críticas

- [ ] Criar `worker-entrypoint.sh` referenciado no Dockerfile (build do worker falha sem ele)
- [ ] Corrigir health check do Selenium na API (`src/api/v1/main.py`) que retorna `status=True` hardcoded sem verificar conexão real
- [ ] Validar `.env` no startup dos serviços (falha silenciosa quando variáveis obrigatórias estão ausentes)
- [ ] Corrigir `circuit_breaker.py` que levanta `Exception` genérica em vez de `CircuitBreakerOpenException`

### Docker e Deploy

- [ ] Adicionar health checks (liveness/readiness probes) no Dockerfile e docker-compose
- [ ] Definir resource limits (CPU/memória) no docker-compose para cada serviço
- [ ] Configurar HTTPS/TLS no deploy (certificados, reverse proxy)
- [ ] Adicionar logging aggregation (ELK stack ou Loki)

---

## Prioridade Média

### Dashboard e Web UI

- [ ] Adicionar testes para as rotas Flask do Dashboard
- [ ] Implementar gráficos de tendência no dashboard (evolução de reviews ao longo do tempo)
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

- [ ] Criar testes end-to-end do workflow completo (scrape -> analyze -> generate -> notify)
- [ ] Adicionar testes para rotas do Dashboard Flask
- [ ] Implementar testes de carga/stress para a API
- [ ] Adicionar testes de memory leak para execuções longas
- [ ] Criar testes de integração com Redis real (não mockado)
- [ ] Adicionar testes para os endpoints de reports e settings proxy

### Scripts e Automação

- [ ] Implementar `scripts/backup_restore.sh` (referenciado mas vazio/incompleto)
- [ ] Adicionar script de migração de dados entre versões
- [ ] Configurar supervisord ou systemd para o daemon em produção
- [ ] Adicionar rotação automática de logs antigos

---

## Prioridade Baixa

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

## Concluído

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

---

## Notas

- **Python**: Projeto roda em Python 3.14 (Arch Linux); lxml 6.0.2+ necessário
- **Dados**: 272 arquivos JSON em `data/`, ~10.880 reviews coletados
- **Cobertura de testes**: ~85% (105 test methods em 18 arquivos)
- **Serviços**: API (FastAPI :8080), Dashboard (Flask :5000), Redis (:6379), Selenium (:4444)
