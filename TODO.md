# TODO - Doctoralia Scrapper

Backlog aberto e priorizado. Funcionalidades já entregues e consideradas maduras foram movidas para [DONE.md](DONE.md).

## Roadmap da revisão funcional — novembro de 2026

Executar nesta ordem. Preservar snapshots, configurações e volumes existentes durante as migrações; só marcar uma etapa como concluída após validar o caminho correspondente.

### P0 — Integridade e segurança

- [x] Corrigir a extração de datas no HTML atual da Doctoralia, mantendo compatibilidade com o formato anterior e cobrindo datas inválidas. (`tests/test_scraper_parsing.py`)
- [x] Corrigir e validar a extração do nome do profissional no cabeçalho atual da Doctoralia. (Validado no perfil de Bruna Pinto Gomes e em `tests/test_scraper_parsing.py`.)
- [ ] Impedir execução de HTML/JavaScript oriundo de avaliações, perfis e respostas em todas as telas do dashboard; cobrir texto, atributos e ações. Proteções aplicadas nas telas de respostas, perfis, histórico, relatórios, overview, saúde, configurações e agendamentos; concluir auditoria de todos os fluxos e testes em navegador.
- [ ] Substituir IDs posicionais por identidade estável de avaliação: `data-id` do Doctoralia já é usado quando presente e testado contra reordenação; falta definir fallback e reconciliação de colisões e migrar dados legados.
- [ ] Preservar rascunhos e edições ao coletar novamente, sem associá-los a outra avaliação. Os caminhos atuais de coleta, edição e limpeza usam bloqueio entre processos, escrita atômica e nomes únicos; coletas preservam rascunhos do último snapshot quando há ID da origem ou correspondência única de autor e comentário. Rascunhos mais antigos podem ser recuperados por ID estável quando a ordenação e as identidades são inequívocas; faltam reconciliação e tratamento explícito dos casos ambíguos e legados.
- [ ] Distinguir coletas completas, parciais e falhas; registrar total anunciado e extraído, motivo da parada e duração, sem apresentar ausência ou incompletude como sucesso completo. O scraper registra total e motivo, a API retorna `partial` quando a coleta é incompleta ou indeterminada, o histórico sinaliza snapshots parciais e o Telegram não os envia como relatório completo. Uma coleta real do perfil de Bruna Pinto Gomes extraiu 164/164 avaliações; faltam os fluxos de interface e integração em execução.

### P1 — Persistência e fluxo operacional

- [ ] Modelar perfis, avaliações, rascunhos e execuções no PostgreSQL com restrições, índices e migrações versionadas.
- [ ] Importar snapshots JSON existentes de forma reproduzível e verificável, preservando backup, lidando com duplicatas e registrando conflitos de identidade.
- [ ] Integrar frontend e API ao banco com consultas, filtros e paginação no servidor; manter histórico de coletas e estado das respostas independentes de snapshots.
- [ ] Unificar os caminhos síncrono e assíncrono de coleta, persistência e erros; evitar Selenium bloqueando o event loop e validar a visibilidade do resultado no dashboard.
- [ ] Corrigir o significado dos filtros de data: distinguir data da avaliação e data da coleta na API e na interface.
- [ ] Avaliar as requisições de paginação atuais e alternativas apropriadas ao Selenium; validar coleta completa em perfil real, respostas e campos, com testes de HTML real anonimizado e sem assumir API disponível.

### P2 — Simplificação e interface

- [ ] Inventariar workflows ativos, consumidores de webhooks e callbacks do n8n; identificar automações que precisam de substituição antes de removê-lo da distribuição padrão.
- [ ] Desacoplar normalização compartilhada do pacote n8n e revisar Compose, proxy, documentação e testes; preservar o volume `n8n-data` e oferecer migração das automações existentes.
- [ ] Reorganizar a navegação em visão geral, avaliações, respostas, perfis/coletas e configurações; colocar pendências e ações principais em destaque.
- [ ] Melhorar estados de carregamento, vazio, erro e coleta parcial, paginação, responsividade e acessibilidade; indicar que sugestões devem ser publicadas na Doctoralia.
- [ ] Validar a interface em tamanhos de tela diferentes e os fluxos de avaliação, edição, cópia, histórico e recuperação de falhas.

## Alta prioridade

- [ ] Criar um agendamento Telegram real de monitoramento/relatório na stack em execução e validar `next_run_at` + histórico persistido.
- [ ] Consolidar o contrato de configuração: `.env` para segredos/runtime, `config.json` para preferências não secretas e JSON Schema para validar drift.
- [x] Trocar o servidor dev do dashboard Flask por um WSGI server no container de produção. (`waitress` em produção, ver `src/dashboard/app.py`)
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
