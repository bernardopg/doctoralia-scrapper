# TODO - Doctoralia Scrapper

Backlog aberto e priorizado. Funcionalidades já entregues e consideradas maduras foram movidas para [DONE.md](DONE.md).

## Alta prioridade

- [ ] Configurar HTTPS/TLS no deploy com reverse proxy e certificados.
- [ ] Implementar limpeza e arquivamento de jobs antigos no Redis.
- [ ] Adicionar rate limiting por IP/API key nos endpoints da API.
- [ ] Mascarar segredos na tela de settings sem perder rotação de chave.
- [ ] Criar testes end-to-end do fluxo completo: scrape -> analyze -> generate -> notify.
- [ ] Implementar `scripts/backup_restore.sh` de forma real, com restore validado.

## Prioridade média

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

## Prioridade baixa

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
