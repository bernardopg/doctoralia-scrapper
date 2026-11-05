# Roadmap do próximo release funcional

Base auditada: [prontidão da 2.8.0](docs/release-readiness.md). A rastreabilidade é feita pelas [fichas](tasks/README.md) e pelos PRs, pois Issues está desabilitado.

## Estado

REL-01 a REL-09 foram entregues na main e ensaiados conforme a [prontidão](docs/release-readiness.md). REL-10 (tag, artefatos e verificação pós-deploy) depende da aprovação do responsável.

## Depois da 2.8.0

- Tornar `postgres` o backend padrão após uso real prolongado, com exclusão de coletas pelo banco.
- Estender os estados e a paginação de REL-08 às telas de histórico, relatórios e perfis.
- Remover o serviço n8n do Compose depois de confirmar que nenhuma outra instalação o usa.
- Resolução de conflitos de rascunho pela interface (hoje via CLI).

## Critério de release

O escopo aprovado deve ter critérios aceitos e riscos residuais explicitamente registrados; funcionalidades excluídas não devem ser anunciadas. Exigir CI final no SHA de entrega, testes com serviços descartáveis, ensaio de backup/restore e instalação limpa e existente, evidência de navegador e fluxo runtime pertinentes, documentação operacional, versões e notas consistentes, artefatos publicados e verificados e health/readiness e versão observados na instalação atualizada. Cada evidência deve identificar SHA, ambiente, comando ou procedimento e resultado. A publicação ocorre somente depois da aprovação operacional apropriada.

**Staging não é migração**: cópia com checksum e esquema versionado apenas preservam e preparam a origem. A migração requer importação transacional e repetível, reconciliação e conflitos persistidos, totais e campos conferidos incluindo rascunhos, ensaio de falha/retomada e restore, seguida de ativação opt-in e rollback comprovados numa cópia representativa. Nunca inferir isso de um teste de staging.

Estados de evidência são distintos: implementado; testado localmente; CI; navegador; runtime; publicado. Uma etapa não prova as outras. Detalhes e limites ficam na ficha e no PR de cada frente.
