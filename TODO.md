# TODO - Doctoralia Scrapper

Backlog aberto e priorizado. Funcionalidades já entregues e consideradas maduras foram movidas para [DONE.md](DONE.md).

## Alta prioridade

- [ ] Persistir no backend os campos completos do perfil do operador: `email`, avatar, time, membros e plano.
- [ ] Introduzir modelo multiusuário com convite, papéis e isolamento por workspace/equipe.
- [ ] Configurar HTTPS/TLS no deploy com reverse proxy e certificados.
- [ ] Implementar limpeza e arquivamento de jobs antigos no Redis.
- [ ] Adicionar rate limiting por IP/API key nos endpoints da API.
- [ ] Adicionar CSRF protection nas ações autenticadas do dashboard (`login`, `logout`, troca de senha e futuras mutações web).
- [ ] Mascarar segredos na tela de settings sem perder rotação de chave.
- [ ] Criar testes end-to-end do fluxo completo: scrape -> analyze -> generate -> notify.
- [ ] Implementar `scripts/backup_restore.sh` de forma real, com restore validado.

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

## Referência

- Entregas maduras: [DONE.md](DONE.md)
- Histórico de releases: [CHANGELOG.md](CHANGELOG.md)
