# Roadmap do próximo release funcional

Base auditada: [release-readiness](docs/release-readiness.md). **v2.8.0 é apenas candidata**, sujeita ao escopo efetivamente entregue; não há bump de versão neste planejamento. A rastreabilidade é feita pelas [fichas](tasks/README.md) e pelos PRs, pois Issues está desabilitado.

## Ondas e caminho crítico

1. **P0/P1 — contratos e preservação**: [REL-01](tasks/REL-01.md) e [REL-02](tasks/REL-02.md) estão em andamento em frentes separadas. [REL-03](tasks/REL-03.md) depende da importação e dos conflitos de REL-01 para o fluxo completo; análise de identidade pode começar antes. [REL-04](tasks/REL-04.md) é independente e está em andamento.
2. **P1 — operação com banco**: [REL-05](tasks/REL-05.md) depende de REL-01 e REL-03 para ativação segura; integra REL-02 no caminho de coleta. [REL-06](tasks/REL-06.md) pode iniciar independente, mas sua integração e aceite de persistência dependem de REL-02 e REL-05.
3. **P2 — integrações e experiência**: inventário de [REL-07](tasks/REL-07.md) e análise de [REL-08](tasks/REL-08.md) podem começar agora; aceite integrado de REL-08 depende de REL-02, REL-03, REL-05 e REL-06. Remoção do n8n depende de inventário e migração comprovados.
4. **P1/P3 — ensaio e entrega**: [REL-09](tasks/REL-09.md) pode preparar CI e ensaios desde já; validação final depende das frentes anteriores incluídas no escopo. [REL-10](tasks/REL-10.md) fecha o release somente após REL-09 e aceite das tarefas incluídas.

## Critério de release

O escopo aprovado deve ter critérios aceitos e riscos residuais explicitamente registrados; funcionalidades excluídas não devem ser anunciadas. Exigir CI final no SHA de entrega, testes com serviços descartáveis, ensaio de backup/restore e instalação limpa e existente, evidência de navegador e fluxo runtime pertinentes, documentação operacional, versões e notas consistentes, artefatos publicados e verificados e health/readiness e versão observados na instalação atualizada. Cada evidência deve identificar SHA, ambiente, comando ou procedimento e resultado. A publicação ocorre somente depois da aprovação operacional apropriada.

**Staging não é migração**: cópia com checksum e esquema versionado apenas preservam e preparam a origem. A migração requer importação transacional e repetível, reconciliação e conflitos persistidos, totais e campos conferidos incluindo rascunhos, ensaio de falha/retomada e restore, seguida de ativação opt-in e rollback comprovados numa cópia representativa. Nunca inferir isso de um teste de staging.

Estados de evidência são distintos: implementado; testado localmente; CI; navegador; runtime; publicado. Uma etapa não prova as outras. Detalhes e limites ficam na ficha e no PR de cada frente.
