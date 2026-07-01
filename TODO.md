# TODO - Doctoralia Scrapper

Backlog aberto e priorizado. Funcionalidades já entregues e consideradas maduras foram movidas para [DONE.md](DONE.md).

## Alta prioridade

- [ ] Criar um agendamento Telegram real de monitoramento/relatório na stack em execução e validar `next_run_at` + histórico persistido.
- [ ] Consolidar o contrato de configuração: `.env` para segredos/runtime, `config.json` para preferências não secretas e JSON Schema para validar drift.
- [ ] Trocar o servidor dev do dashboard Flask por um WSGI server no container de produção.
- [ ] Persistir no backend os campos completos do perfil do operador: `email`, avatar, time, membros e plano.
- [ ] Introduzir modelo multiusuário com convite, papéis e isolamento por workspace/equipe.
- [x] Configurar HTTPS/TLS no deploy com reverse proxy e certificados. (Caddy + `docker-compose.prod.yml`)
- [x] Adicionar smoke test Docker de produção para readiness, Caddy e Telegram real opcional. (`make docker-smoke-prod`, `make docker-smoke-prod-telegram`)
- [x] Implementar limpeza e arquivamento de jobs antigos no Redis.
- [x] Adicionar rate limiting por IP/API key nos endpoints da API.
- [x] Adicionar CSRF protection nas ações autenticadas do dashboard (`login`, `logout`, troca de senha e futuras mutações web).
- [x] Mascarar segredos na tela de settings sem perder rotação de chave.
- [x] Criar testes end-to-end do fluxo completo: scrape -> analyze -> generate -> notify. (`tests/test_e2e_flow.py`)
- [x] Implementar `scripts/backup_restore.sh` de forma real, com restore validado. (data/config/.env/Redis/n8n + `verify`)

## Prioridade média

- [ ] Evoluir a página `/me` para edição real de avatar e email, e expandir preferências do operador além das credenciais já suportadas.
- [ ] Conectar `/me` a uma rota/identidade real de usuário, em vez de depender apenas de contexto local e `?user=...`.
- [ ] Permitir rotação e gestão da autenticação do dashboard pela UI de settings, incluindo estado do bootstrap e TTL de sessão.
- [ ] Adicionar política de sessão mais completa: expiração absoluta/inativa, invalidação global e trilha de sessões ativas.
- [ ] Adicionar gestão de equipe na interface: convites, membros ativos, remoção e papéis.
- [ ] Exibir informações reais de plano/licenciamento e limites do workspace, em vez de placeholders de UI.
- [ ] Adicionar paginação ou virtualização na fila de respostas pendentes.
- [ ] Permitir geração em lote por perfil na página de respostas.
- [ ] Exibir comparação temporal por perfil no dashboard.
- [ ] Adicionar diff entre snapshot atual e anterior no histórico.
- [ ] Mostrar distribuição de sentimento nos relatórios.
- [ ] Adicionar endpoint para download direto de um arquivo específico.
- [ ] Substituir polling por WebSocket para progresso em tempo real.
- [ ] Melhorar validação de URLs e limpar parâmetros supérfluos.
- [ ] Implementar scraping incremental de reviews novos.
- [ ] Tratar CAPTCHA e bloqueios com estratégia explícita.
- [ ] Evoluir o histórico do scheduler Telegram para paginação/filtros server-side quando o volume crescer além do modo client-side atual.
- [ ] Permitir presets por favorito em `/me` para rodar scraping com parâmetros salvos por perfil.

## Refatorações e robustez identificadas na vistoria

- [x] Quebrar `src/api/v1/main.py` em routers FastAPI por domínio (`auth`, `health`, `jobs`, `scrape`, `generate`, `analyze`, `metrics`, `settings`, `telegram`) e centralizar dependências injetáveis em `src/api/v1/providers.py`.
- [x] Quebrar `src/dashboard.py` em módulos Flask menores (`app`, `auth`, `pages`, `reports`, `notifications`, `services`, `workspace`, `api_proxy`, `user_profile`), separando rotas, autenticação, leitura de dados e renderização.
- [x] Extrair provedores de IA de `src/response_generator.py` para `src/providers/`, mantendo o gerador focado em templates e orquestração.
- [x] Endurecer `_is_fatal_error` em `src/error_handling.py`, incluindo exceções próprias do scraper e casos Selenium conhecidos.
- [x] Completar `scripts/backup_restore.sh` com backup/restore reais e validação automatizada do restore.

## Prioridade baixa

- [ ] Reduzir ruído residual de browser no dashboard (`favicon`, autofill de extensões de terceiros e associações de labels remanescentes).
- [ ] Adicionar auditoria de alterações de perfil do operador e favoritos.
- [ ] Adicionar auditoria de autenticação: logins, logouts, troca de senha e tentativas inválidas.
- [ ] Permitir upload real de foto de perfil com storage local/remoto configurável.
- [ ] Logging aggregation centralizada, como Loki ou ELK.
- [ ] Testes de carga e stress da API.
- [ ] Testes de memory leak para execuções longas.
- [ ] Proxy rotation para scraping mais agressivo.
- [ ] Processamento paralelo de múltiplos médicos.
- [ ] Fallback inteligente entre provedores de IA.
- [ ] Registrar custo e uso por provedor externo.
- [ ] Integração com Slack e webhook genérico além do Telegram.
- [ ] Completar type hints faltantes em módulos legados.
- [ ] Criar configs por ambiente e JSON Schema do `config.json`.

## Documentação ainda desejável

- [ ] Expandir `docs/deployment.md` para um playbook de produção mais detalhado.
- [ ] Adicionar diagramas de sequência além dos diagramas de workflow já existentes.
- [ ] Criar runbook focado em incidentes de produção e recuperação.

## UX
- [ ] Melhorar mensagens de erro e feedback para o usuário no dashboard.
- [ ] Adicionar loading states e indicadores de progresso mais claros.
- [ ] Tornar a interface mais responsiva e mobile-friendly.
- [ ] Adicionar tooltips e documentação inline para campos e ações complexas.
- [ ] Permitir customização de notificações e alertas pelo usuário.
- [ ] Adicionar dark mode.
- [ ] Permitir reordenação e customização do layout do dashboard.
- [ ] Adicionar gráficos e visualizações mais ricas para análise de dados.
- [ ] Adicionar suporte a múltiplos idiomas na interface.
- [ ] Adicionar onboarding e tutoriais para novos usuários.
- [ ] Permitir exportação de dados e relatórios em formatos como CSV/PDF.
- [ ] Adicionar suporte a temas e personalização visual do dashboard.
- [ ] Adicionar suporte a acessibilidade (a11y) para usuários com necessidades especiais.
- [ ] Adicionar suporte a notificações push no navegador.
- [ ] Adicionar suporte a autenticação social (Google, Facebook, etc.) para o dashboard.
- [ ] Adicionar suporte a integração com calendários (Google Calendar, Outlook) para agendamento de tarefas e lembretes.
- [ ] Adicionar suporte a integração com ferramentas de CRM para exportação de contatos e dados de clientes.
- [ ] Adicionar suporte a integração com ferramentas de análise de dados como Google Analytics ou Mixpanel para monitoramento de uso e comportamento do usuário.
- [ ] Adicionar suporte a integração com ferramentas de comunicação como Slack ou Microsoft Teams para notificações e alertas em tempo real.
- [ ] Adicionar suporte a integração com ferramentas de automação como Zapier ou Integromat para criar fluxos de trabalho personalizados.
- [ ] Adicionar suporte a integração com ferramentas de armazenamento em nuvem como Google Drive ou Dropbox para backup e exportação de dados.
- [ ] Adicionar suporte a integração com ferramentas de monitoramento de desempenho como New Relic ou Datadog para monitoramento de saúde e performance da aplicação.
- [ ] Adicionar suporte a integração com ferramentas de teste de usabilidade como UserTesting ou Hotjar para coleta de feedback dos usuários e melhoria contínua da interface.
- [ ] Adicionar suporte a integração com ferramentas de análise de sentimentos como IBM Watson ou Google Cloud Natural Language para análise avançada de reviews e feedback dos clientes.
- [ ] Adicionar suporte a integração com ferramentas de análise de concorrência como SEMrush ou Ahrefs para monitoramento de concorrentes e análise de mercado.
## Referência

- Entregas maduras: [DONE.md](DONE.md)
- Histórico de releases: [CHANGELOG.md](CHANGELOG.md)