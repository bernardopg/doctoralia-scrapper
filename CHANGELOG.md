# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue a ideia do [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e a linha de versão publicada no repositório Git.

## [Unreleased]

### Added

- **[tests]** Testes end-to-end do pipeline completo em `tests/test_e2e_flow.py`: `scrape -> generate -> analyze -> notify`, mockando apenas as fronteiras de I/O (rede do Selenium e HTTP do Telegram) e exercitando a orquestração real. Inclui caso de aborto quando o scrape não retorna dados.
- **[deploy]** Overlay de produção `docker-compose.prod.yml` com **Caddy** como reverse proxy e **TLS automático** (Let's Encrypt em produção, certificado self-signed da CA interna em local/staging). Roteia `/v1/*`, `/docs` e `/openapi.json` para a API e o restante para o dashboard; n8n em subdomínio dedicado. Aplica HSTS + `X-Frame-Options` + `X-Content-Type-Options` + `Referrer-Policy`, redirect HTTP→HTTPS e remove o header `Server`. Portas do Caddy configuráveis via `CADDY_HTTP_PORT`/`CADDY_HTTPS_PORT`.
- **[security]** O overlay de produção passa a exigir senha no Redis (`REDIS_PASSWORD`), injeta a `REDIS_URL` autenticada em `api`/`worker` e deixa de publicar as portas internas (Redis/API/dashboard/n8n/selenium) no host — só o Caddy expõe 80/443.

### Changed

- **[docs]** `docs/deployment.md`: seção de reverse proxy reescrita de Nginx manual para o fluxo real com Caddy e o overlay `docker-compose.prod.yml`.
- **[config]** `.env.example`: adicionadas `APP_DOMAIN`, `N8N_DOMAIN`, `REDIS_PASSWORD`, `CADDY_HTTP_PORT` e `CADDY_HTTPS_PORT`.

## [2.3.1] - 2026-06-16

### Fixed

- **[docker]** Corrigido o estágio final do build multi-stage para instalar diretamente as wheels já construídas em `/wheels`, evitando que `pip install --no-index --find-links=/wheels -r requirements.txt` tente resolver novamente dependências VCS e chame `git` em imagens runtime sem Git instalado.

## [2.2.0] - 2026-06-11

### Security

- **[CodeQL fix]** Endurecida a validação de open-redirect em `src/dashboard/auth.py` (`_validate_redirect_target`), eliminando os alertas `py/url-redirection-from-remote-source` #1416 (`:50`) e #1417 (`:63`). Agora rejeita URLs protocol-relative (`//host`), truques de backslash (`/\host` que o browser normaliza para `//host`), caracteres de controle/whitespace (CR/LF/NUL/tab) e exige path enraizado em um único `/`. `src/dashboard/app.py::_safe_next_url` passou a delegar ao mesmo validador, evitando divergência entre os dois guards.
- **[CVE fix]** Atualizado `starlette` de `0.52.1` para `1.2.1`, corrigindo a falta de validação do header `Host` que envenena `request.url.path` e pode burlar checagens de segurança baseadas em path (Dependabot, 2x medium). Compatível com FastAPI 0.136 (`starlette>=0.46.0`, sem teto).

### Changed

- **[deps]** Atualizado `redis` de `7.4.0` para `8.0.0` (constraint `<8.0` → `<9.0`); compatível com `rq>=2.7` (`redis>6`) e com os comandos usados (`hincrby`, `pipeline`, `zremrangebyscore`, `hgetall`, `lrange`, `zcard`, `get`, `setex`, `incr`). (Dependabot #131)
- **[deps]** Atualizado o grupo `python-minor-and-patch` (Dependabot #130) e demais dependências de desenvolvimento/transitivas: `cryptography`, `click`, `coverage`, `croniter`, `ipython`, `jedi`, `regex`, `rich`, `tomlkit`, `tqdm`, `virtualenv`, `watchfiles`, `filelock`, `identify`, `markdown-it-py`, entre outras.
- **[ci]** Substituído `safety check` (deprecated desde 2024-06-01, exige autenticação) por `pip-audit` no scan de vulnerabilidades de dependências (CI + Makefile).
- **[ci]** Adicionado Python 3.13 à matriz de testes; `black` `target-version` ampliado para `py310`–`py314`.
- **[ci]** Novo workflow `auto-merge.yml`: habilita squash auto-merge em todo PR não-draft do próprio repositório direcionado a `main`. Branch protection na `main` agora exige `All Checks Passed`, `All Docker Checks Passed` e `Analyze Python` antes do merge.
- **[deps]** `flask-cors` fixado em `^6.0.5` (6.0.4 foi *yanked* por quebrar mypy em blueprints).
- **[refactor]** Layout consolidado sob `src/`: `config/` movido para `src/config/` e `static/` para `src/static/`.
- **[refactor]** `src/dashboard.py` (monólito de ~1647 linhas) dividido no pacote `src/dashboard/` com módulos focados (`app`, `auth`, `pages`, `reports`, `notifications`, `services`, `workspace`, `api_proxy`, `user_profile`); adicionado `__main__.py` para `python -m src.dashboard`.
- **[chore]** Removido código morto legado (`src/dashboard.py` e `config/` raiz) e padronizada a qualidade: isort, black, flake8 (ignora `E203`), mypy limpo e `nosec B104` nos binds `0.0.0.0` intencionais.

### Fixed

- **[docker]** Corrigido o build Docker que falhava com `"/static": not found`: removido o `COPY static ./static` quebrado (assets já chegam via `COPY src ./src`) e ajustado `static_folder` do dashboard para `src/static/`.
- **[ci]** Removido o campo inválido `exclude-paths` de `.github/dependabot.yml` (não existe no schema v2, fazia o bloco `pip` ser ignorado).
- **[build]** `make install-dev` não tenta mais instalar o inexistente `requirements-dev.txt`.

## [2.1.1] - 2026-05-19

### Security

- **[CVE fix]** Eliminado taint path CodeQL `py/stack-trace-exposure` em `src/api/v1/main.py`: `_sanitize_schedule_run_response` agora retorna apenas constantes fixas (`SCHEDULE_RUN_SUCCESS_MESSAGE` / `SCHEDULE_RUN_FAILURE_MESSAGE`) na chave `message`, impedindo que dados derivados de exceções fluam para respostas HTTP externas. (CodeQL alert #1394)
- **[Docker]** Adicionado `apt-get upgrade` na camada `base` do Dockerfile para aplicar patches de segurança do OS Debian 13.4: corrige `libcap2` (CVE-2026-4878) e `libsystemd0`/`libudev1` (CVE-2026-29111).

### Changed

- **[deps]** Atualizado `idna` de `3.14` para `3.15` (CVE-2026-45409: validação de labels DNS).
- **[deps]** Atualizado `requests` de `2.33.1` para `2.34.2`.
- **[deps]** Atualizado `lxml` de `6.1.0` para `6.1.1`.
- **[deps]** Atualizado `selenium` de `4.43.0` para `4.44.0`.
- **[deps]** Atualizado `webdriver-manager` de `4.0.2` para `4.1.1`.
- **[deps]** Atualizado `uvicorn` de `0.46.0` para `0.47.0` (constraint relaxada de `<0.47` para `<0.48`).
- **[deps]** Atualizado `black` de `26.3.1` para `26.5.1`.
- **[deps]** Atualizado `authlib` de `1.6.11` para `1.7.2`.
- **[deps]** Atualizado `types-psutil` de `7.2.2.20260508` para `7.2.2.20260518`.
- **[deps]** Atualizado `types-requests` de `2.33.0.20260508` para `2.33.0.20260518`.
- **[deps]** Atualizado `urllib3` de `2.6.3` para `2.7.0` (transitivo via `requests`).
- **[deps]** Atualizado `cryptography` de `47.0.0` para `48.0.0` (transitivo).
- **[deps]** Atualizado `pydantic` de `2.13.3` para `2.13.4` + `pydantic-core` de `2.46.3` para `2.46.4`.
- **[deps]** Atualizado `mypy` de `1.20.2` para `2.1.0`.
- **[actions]** Atualizado `codecov/codecov-action` de `v6.0.0` para `v6.0.1` (SHA: `e79a6962`) — corrige template injection (VULN-1652).
- **[actions]** Atualizado `github/codeql-action` (`init`, `analyze`, `upload-sarif`) de SHA `68bde559` para `9e0d7b8d`.

### Fixed

- Testes `test_run_telegram_notification_schedule_sanitizes_success_result_with_custom_message` e `test_run_telegram_notification_schedule_handles_unexpected_result_shapes` atualizados para refletir o novo comportamento seguro da resposta `message`.

## [2.1.0] - 2026-04-24

### Added

- Rate limiting por IP/API key nos endpoints da API (`X-RateLimit-Remaining` por janela deslizante via Redis).
- CSRF protection nas ações autenticadas do dashboard (`login`, `logout`, troca de senha e futuras mutações web).
- Mascaramento de segredos na tela de settings sem perder a capacidade de rotação de chave (`_mask_secret` / `_is_masked_secret`).
- Serviço de limpeza de jobs antigos do Redis (`scripts/cleanup_redis_jobs.py`).
- Target `test` no Dockerfile com `requirements-dev.txt` para execução de testes isolados em container.
- Serviço `test` no `docker-compose.yml` (ativado via profile `test`).
- Cabeçalho de navegação responsivo no template base do dashboard.
- Helper `_config_to_settings_model` e `_preserve_masked_settings` para serialização e atualização segura de settings.

### Fixed

- Corrigida formatação de código (Black/isort) em `src/api/v1/main.py`, `src/scraper.py` e `src/dashboard.py`.
- Corrigidos erros de tipo mypy em `src/api/v1/main.py`: tipagem do retorno de `redis.incr` e coerção de `id_salt` opcional.

## [2.0.1] - 2026-04-22

### Changed

- Dependências Python atualizadas via Dependabot: `lxml` `6.1.0`, `packaging` `26.1`, `fastapi` `0.136.0`, `pydantic` `2.13.2`, `rq` `2.8.0` e `authlib` `1.6.11`.
- GitHub Actions atualizadas via Dependabot: `actions/cache` `5.0.5`, `github/codeql-action` `4.35.2`, `trufflesecurity/trufflehog` `3.95.2` e `aquasecurity/trivy-action` `0.36.0`.
- Metadados de versão do pacote, API e dashboard alinhados para `2.0.1`.

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

- [Unreleased]: https://github.com/bernardopg/doctoralia-scrapper/compare/v2.3.1...HEAD
- [2.3.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/v2.3.0...v2.3.1
- [2.2.0]: https://github.com/bernardopg/doctoralia-scrapper/compare/v2.1.1...v2.2.0
- [2.1.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/v2.1.0...v2.1.1
- [2.1.0]: https://github.com/bernardopg/doctoralia-scrapper/compare/v2.0.1...v2.1.0
- [2.0.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/2.0.0...v2.0.1
- [1.2.0-rc.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/v1.1.1...v1.2.0-rc.1
- [1.1.1]: https://github.com/bernardopg/doctoralia-scrapper/compare/1.1.0...v1.1.1
- [1.1.0]: https://github.com/bernardopg/doctoralia-scrapper/compare/v1.0.0...1.1.0
- [1.0.0]: https://github.com/bernardopg/doctoralia-scrapper/releases/tag/v1.0.0
