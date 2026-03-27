# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue a ideia do [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e a linha de versão publicada no repositório Git.

## [Unreleased]

### Changed

- Ainda sem mudanças publicadas depois da prerelease `v1.2.0-rc.1`.

## [1.2.0-rc.1] - 2026-03-27

### Added

- Scheduler Telegram completo no dashboard, com teste manual, CRUD, disparo imediato e histórico persistido.
- Serviço `TelegramScheduleService` Redis-backed para definições, locks, histórico e anexos.
- Métricas da API persistidas em Redis para leitura consistente entre processos.
- Wiki do repositório em `docs/`, com hub central, navegação lateral, página de `about` e documentação específica do scheduler Telegram.
- Assets visuais locais do projeto: logo, banner, social card, diagramas SVG e screenshots reais do dashboard.
- `DONE.md` com o inventário das funcionalidades principais já entregues e maduras.

### Changed

- `README.md` virou uma landing page do repositório, com visual, screenshots e mapa da documentação.
- `TODO.md` foi reduzido ao backlog aberto e realista; entregas estáveis foram separadas em `DONE.md`.
- Compose local do n8n foi endurecido:
  - bind em `127.0.0.1:5678`
  - Basic Auth obrigatória
  - `N8N_ENCRYPTION_KEY` obrigatória
  - versão fixada em `n8nio/n8n:2.11.4`
- Metadados de versão foram alinhados para a prerelease `1.2.0rc1` no pacote e `1.2.0-rc.1` na API.

### Fixed

- Retry de envio de documento no Telegram agora reposiciona o ponteiro do arquivo antes do reenvio.
- Health do scheduler Telegram não depende mais de self-call frágil para a própria API em execução local.
- Workflows e checagens de GitHub Actions foram endurecidos para reduzir falsos positivos e ruído operacional.
- Documentação passou a refletir o estado real do stack, incluindo Redis, n8n e scheduler interno.

### Quality

- Cobertura automatizada expandida para fluxos de dashboard, Redis real, autenticação/HMAC, jobs e Telegram.
- Estado validado nesta linha: `250 passed` e `74%` de coverage.

### Dependencies

- `redis` atualizado para `7.4.0`
- `requests` atualizado para `2.33.0`
- `nltk` atualizado para `3.9.4`
- `attrs` atualizado para `26.1.0`
- `types-requests` atualizado para `2.32.4.20260324`

## [1.1.1] - 2026-03-26

### Changed

- Release de manutenção focada em atualizações de dependências e endurecimento de CI/security scanning.

### Fixed

- Ajustes em workflows de Actions, dependabot e verificação de segurança do repositório.

## [1.1.0] - 2026-03-14

### Added

- Workspace dashboard com páginas dedicadas para overview, perfis, respostas, histórico, relatórios, settings e área do operador.
- Pipeline assíncrono endurecido com snapshots persistidos e melhor leitura do estado lógico dos jobs.

### Changed

- Reorganização operacional do dashboard para uso contínuo em vez de monitoramento superficial.
- Ajustes de CI e formatação para manter checks verdes com a nova superfície web.

## [1.0.0] - 2025-06-05

### Added

- Primeira linha estável do projeto, com scraping, geração automática de respostas, notificações Telegram, modo daemon, logging e configuração completa de desenvolvimento.

## Links

- [Unreleased]: https://github.com/bernardopg/doctoralia-scrapper/compare/v1.2.0-rc.1...HEAD
- [1.2.0-rc.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/v1.1.1...v1.2.0-rc.1
- [1.1.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/1.1.0...v1.1.1
- [1.1.0]: https://github.com/bernardopg/doctoralia-scrapper/compare/v1.0.0...1.1.0
- [1.0.0]: https://github.com/bernardopg/doctoralia-scrapper/releases/tag/v1.0.0
