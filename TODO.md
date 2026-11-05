# TODO e roadmap — Doctoralia Scrapper

Este arquivo acompanha a revisão funcional e o trabalho para o próximo release. Os blocos P0–P3 abaixo são o escopo acordado para a revisão; o backlog adicional permanece ao final e não deve ser confundido com funcionalidades já entregues. Marque uma tarefa apenas depois da implementação **e** da validação indicada. Preserve snapshots, configurações e volumes existentes em todas as migrações.

## Estado confirmado — 4 de novembro de 2026

- A última versão publicada é `v2.7.2`. As alterações posteriores estão em `main`, mas ainda não compõem um novo release.
- A extração foi ajustada para as datas e o cabeçalho atuais da Doctoralia. Uma coleta real anterior do perfil de Bruna Pinto Gomes obteve 164/164 avaliações; isso não comprova coletas futuras nem todos os campos e fluxos.
- Os snapshots e rascunhos continuam em JSON. Há bloqueio entre processos, gravação atômica e reconciliação conservadora de rascunhos ([#202](https://github.com/bernardopg/doctoralia-scrapper/pull/202), [#205](https://github.com/bernardopg/doctoralia-scrapper/pull/205)); ambiguidades e dados legados ainda exigem tratamento explícito.
- A coleta usa ID da Doctoralia, fingerprint quando possível e ID temporário para identidades ambíguas ([#201](https://github.com/bernardopg/doctoralia-scrapper/pull/201), [#206](https://github.com/bernardopg/doctoralia-scrapper/pull/206)). O fallback pode mudar quando os dados da avaliação mudam; ele não prova que duas avaliações são a mesma.
- O dashboard recebeu proteções de renderização. A auditoria completa de entradas, atributos e ações em navegador ainda está aberta.
- O PostgreSQL possui migrações versionadas para perfis, avaliações, execuções, observações e rascunhos ([#207](https://github.com/bernardopg/doctoralia-scrapper/pull/207)). O staging armazena bytes originais por workspace e checksum, após backup verificado ([#208](https://github.com/bernardopg/doctoralia-scrapper/pull/208)). **Staging não é migração normalizada**: não resolve conflitos e não alimenta a API ou o dashboard.
- CI, Docker e CodeQL de `main` passaram para o merge `1f8389a`; essa evidência não substitui os testes do próximo commit ou de um release.

## Planejamento do próximo release

O [roadmap](ROADMAP.md) e as [fichas REL-01–REL-10](tasks/README.md) detalham dependências, aceite e evidências das prioridades abaixo. A [foto de prontidão](docs/release-readiness.md) registra a base e os checks consultados. REL-01 (importação transacional) e REL-02 (contrato de coleta) estão **em andamento**, ainda sem aceite. A versão v2.8.0 é candidata sujeita ao escopo entregue; não houve bump. O backlog adicional permanece para priorização separada.

## P0 — Integridade e segurança antes da migração

- [ ] **Identidade e conflitos.** Definir e implementar reconciliação explícita de IDs legados, fingerprints alterados, colisões e IDs de origem repetidos; manter os casos incertos separados, sem associar rascunhos automaticamente. Validar reordenação, duplicatas, edição de texto, ausência de autor e restauração de dados históricos.
- [ ] **Rascunhos.** Preservar edições e exclusões intencionais ao recolher ou importar; recuperar rascunhos históricos somente com correspondência inequívoca. Apresentar e registrar conflitos que precisem de decisão. Testar concorrência, snapshots parciais e ausência/reaparição de avaliações.
- [ ] **Segurança das telas.** Concluir a auditoria de avaliações, perfis e respostas em texto, atributos, URLs e ações em todas as páginas. Testar entradas hostis em navegador real, incluindo edição, cópia, histórico e relatórios.
- [ ] **Completude da coleta.** Propagar `complete`, `partial`, `unknown` e falha, totais, motivo e duração em todos os caminhos relevantes da API, dashboard e integrações. Validar que parcial ou desconhecida não seja apresentada nem enviada como relatório completo.

## P1 — PostgreSQL e operação

### 1. Importação e reconciliação

- [x] Preparar esquema inicial versionado e staging idempotente, com cópias verificadas por checksum, bytes originais e indicadores de ambiguidade.
- [ ] Construir importador transacional de staging para perfis, avaliações, execuções, observações e rascunhos, com identidade determinística por workspace e preservação da proveniência. Não tratar fingerprints ou IDs temporários ambíguos como prova de identidade.
- [ ] Registrar conflitos individualmente e oferecer resolução auditável; preservar originais e rascunhos não resolvidos. Definir comportamento para arquivos rejeitados, registros já existentes, dados alterados e reexecuções concorrentes.
- [ ] Produzir relatório de migração com totais de origem, importados, duplicados, rejeitados e pendentes; conferir contagens, campos, timestamps e rascunhos antes de ativar a leitura do banco.
- [ ] Testar migração e reexecução com snapshots representativos e PostgreSQL descartável; validar falha e retomada, rollback e restauração de backup. Fazer ensaio com cópia dos dados existentes antes de qualquer mudança na instalação em uso.

### 2. Integração e fluxo operacional

- [ ] Implementar repositórios e contratos de acesso ao PostgreSQL; integrar API, worker e dashboard com isolamento por workspace, consultas, ordenação, filtros e paginação no servidor.
- [ ] Manter histórico de coletas e rascunhos independentes dos snapshots; definir fonte de verdade, transição e compatibilidade com JSON, incluindo falha do banco e recuperação sem perda de edições.
- [ ] Unificar coleta síncrona e assíncrona, persistência e erros. Retirar Selenium e outras operações bloqueantes do event loop; confirmar que os resultados dos dois caminhos aparecem corretamente no dashboard.
- [ ] Distinguir data da avaliação de data da coleta na API, no banco e na interface; testar limites, fuso horário e registros sem data.
- [ ] Reavaliar a paginação real da Doctoralia e alternativas ao Selenium sem presumir API disponível. Validar totais, respostas e campos com HTML real anonimizado e nova coleta de perfil autorizado.
- [ ] Validar migrações em instalação existente e limpa, inicialização concorrente, integridade das restrições, backup/restore e a política de downgrade; manter testes de PostgreSQL e Redis em serviços descartáveis no CI.

## P2 — n8n e interface

- [ ] Inventariar workflows ativos, consumidores de webhooks e callbacks; identificar substituições necessárias antes de remover o n8n da distribuição padrão. Preservar `n8n-data` e documentar exportação e migração.
- [ ] Desacoplar a normalização compartilhada do pacote n8n e ajustar Compose, proxy, documentação e testes de compatibilidade das integrações existentes.
- [ ] Reorganizar a navegação em visão geral, avaliações, respostas, perfis/coletas e configurações, destacando pendências e ações principais.
- [ ] Melhorar carregamento, vazio, erro, progresso e coleta parcial; oferecer paginação, responsividade e acessibilidade e informar que sugestões devem ser publicadas na Doctoralia.
- [ ] Validar em navegador, em tamanhos diferentes, avaliação, edição, cópia, histórico e recuperação de falhas. Registrar o que foi testado e os limites da validação.

## P3 — Preparação e verificação do release

- [ ] Resolver ou registrar explicitamente quaisquer riscos das etapas P0–P2; atualizar README, documentação operacional, migração, API e changelog conforme o comportamento entregue.
- [ ] Executar suíte completa, verificações de estilo e tipos, CodeQL, varredura das imagens, testes de integração com bancos descartáveis e smoke tests da stack em `main`; corrigir falhas e confirmar o resultado final dos workflows.
- [ ] Sincronizar a versão do pacote, API e dashboard e preparar notas de release e tag coerentes. Publicar somente após todas as verificações acordadas passarem.
- [ ] Confirmar a publicação dos artefatos previstos, suas versões e checksums quando disponíveis; validar health/readiness, versões expostas e o fluxo principal na instalação atualizada, após backup.

## Backlog adicional — a priorizar separadamente

As próximas seções preservam ideias e necessidades anteriores. Sua inclusão no mesmo release depende de priorização; itens que se sobrepõem a P0–P3 devem ser tratados uma única vez. Os itens marcados como concluídos descrevem funcionalidades existentes, não uma validação nova.

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
