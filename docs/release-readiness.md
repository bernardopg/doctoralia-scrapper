# Foto de prontidão — 5 de novembro de 2026

Consulta em 2026-11-05 03:56 UTC, repositório `bernardopg/doctoralia-scrapper`: `origin/main` em `8921cfb21b6f5c7c90b01183f514d626d0d010f7`. Esta é uma fotografia, não uma afirmação sobre mudanças posteriores. O checkout isolado partiu de `c09f013` e recebeu os nove commits remotos por fast-forward antes deste planejamento. O checkout principal `/home/bitter/development/doctoralia-scrapper` estava nove commits atrás e continha alterações locais; foi apenas consultado e suas alterações foram preservadas. Alterações locais não demonstram entrega na main.

## Entregue na main após v2.7.2

| PR | Merge na main (UTC) | Entrega |
|---|---|---|
| [#201](https://github.com/bernardopg/doctoralia-scrapper/pull/201) | 2026-11-03 19:49 | Extração de identidade e datas de avaliações |
| [#202](https://github.com/bernardopg/doctoralia-scrapper/pull/202) | 2026-11-03 20:47 | Preservação de rascunhos e proteção de snapshots |
| [#203](https://github.com/bernardopg/doctoralia-scrapper/pull/203) | 2026-11-03 20:53 | Renderização segura de dados do dashboard |
| [#204](https://github.com/bernardopg/doctoralia-scrapper/pull/204) | 2026-11-03 22:55 | Exposição de coletas incompletas |
| [#205](https://github.com/bernardopg/doctoralia-scrapper/pull/205) | 2026-11-03 23:17 | Recuperação de rascunhos em snapshots anteriores |
| [#206](https://github.com/bernardopg/doctoralia-scrapper/pull/206) | 2026-11-04 00:18 | Proteção de identidade sem ID da origem |
| [#207](https://github.com/bernardopg/doctoralia-scrapper/pull/207) | 2026-11-04 00:46 | Esquema versionado de avaliações e coletas |
| [#208](https://github.com/bernardopg/doctoralia-scrapper/pull/208) | 2026-11-04 01:26 | Staging verificável de snapshots |
| [#209](https://github.com/bernardopg/doctoralia-scrapper/pull/209) | 2026-11-04 01:38 | Estado e prioridades P0–P3 no TODO |

## Release e checks consultados

[Release v2.7.2](https://github.com/bernardopg/doctoralia-scrapper/releases/tag/v2.7.2) publicada em 2026-11-03 00:04 UTC, não draft nem prerelease; tag aponta para `c09f01302eb57abe9b37e8de8f925522b3bfee8f`, anterior a #201–#209. O GitHub lista wheel e sdist carregados e seus digests SHA-256; esta auditoria não baixou nem recalculou esses arquivos, não consultou PyPI nem executou a imagem publicada. O [workflow de release](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41549949413) para esse commit terminou com sucesso.

Para `8921cfb`, consulta aos jobs remotos: [CI](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41755476602) sucesso, incluindo testes Python 3.11–3.14, lint/formatação, segurança, build e sincronização de requirements; [Docker Build & Push](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41755476585) sucesso, incluindo integração, build/push e scans de API e worker; [CodeQL](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/41755476500) sucesso. São resultados remotos para aquele SHA, não execução local deste PR nem prova de navegador, migração de dados existentes ou runtime instalado.

## Lacunas e limites

- O staging de #208 preserva e verifica a origem; ele não comprova importação transacional, reconciliação, ativação PostgreSQL, rollback ou restore. Ver [REL-01](../tasks/REL-01.md), [REL-03](../tasks/REL-03.md), [REL-05](../tasks/REL-05.md) e [REL-09](../tasks/REL-09.md).
- As frentes [REL-01](../tasks/REL-01.md) e [REL-02](../tasks/REL-02.md) estão em andamento separadamente, sem aceite neste documento. Auditoria XSS completa em navegador e validação dos fluxos reais permanecem pendentes.
- Este PR documenta planejamento: não executou testes de código, navegador, bancos, containers, integrações externas ou deploy. Resultados de CI anterior não se tornam evidência desses ensaios. Os estados implementado, teste local, CI, navegador, runtime e publicado devem ser relatados separadamente.
- Issues estão desabilitadas no repositório; [fichas](../tasks/README.md) e PRs são a rastreabilidade. [Roadmap](../ROADMAP.md) propõe v2.8.0 apenas se o escopo entregue justificar; não muda versão.
