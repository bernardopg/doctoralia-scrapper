# Fichas técnicas

Cada ID é estável; atualize estado, SHA, PR e evidências conforme o trabalho avança. Marcadores de TODO preservam o backlog existente; uma ficha planejada não significa trabalho implementado. Issues estão desabilitadas: fichas e PRs mantêm a rastreabilidade.

| ID | Prioridade | Frente | Estado | Dependências para aceite |
|---|---|---|---|---|
| [REL-01](REL-01.md) | P1 | Importação transacional | Em revisão ([#212](https://github.com/bernardopg/doctoralia-scrapper/pull/212)) | staging existente |
| [REL-02](REL-02.md) | P0/P1 | Contrato de coleta | Em revisão ([#211](https://github.com/bernardopg/doctoralia-scrapper/pull/211)) | nenhuma |
| [REL-03](REL-03.md) | P0 | Identidade, conflitos e rascunhos | Planejado | REL-01 para integração |
| [REL-04](REL-04.md) | P0 | Auditoria XSS em navegador | Em andamento | nenhuma |
| [REL-05](REL-05.md) | P1 | Repositórios PostgreSQL e transição | Planejado | REL-01, REL-02, REL-03 |
| [REL-06](REL-06.md) | P1 | Paginação e datas | Planejado | REL-02, REL-05 para integração |
| [REL-07](REL-07.md) | P2 | Inventário n8n e normalização | Planejado | nenhuma para inventário |
| [REL-08](REL-08.md) | P2 | UX acessível e estados | Planejado | REL-02, REL-03, REL-05, REL-06 para aceite integrado |
| [REL-09](REL-09.md) | P1/P3 | CI, backup/restore e instalações | Planejado | frentes incluídas no release para aceite final |
| [REL-10](REL-10.md) | P3 | Release e verificação publicada | Planejado | REL-09 e escopo aceito |

Evidência deve separar implementação, teste local, CI, navegador real, runtime e publicação, com SHA e ambiente. Ausência de evidência é **não verificado**, nunca sucesso presumido. Testes destrutivos de Redis exigem `TEST_REDIS_URL` explicitamente descartável; PostgreSQL exige `TEST_POSTGRES_URL` de serviço descartável criado para o teste. Não enviar Telegram, webhooks ou IA pagos durante os testes; usar mocks. Nunca apontar testes de restauração a dados ou volumes reais.

Planejamento e acompanhamento: [PR #210](https://github.com/bernardopg/doctoralia-scrapper/pull/210), em draft. Revisão documental realizada; aceite de código, testes e release continua nas respectivas fichas.
