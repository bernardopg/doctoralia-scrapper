# Prontidão do release 2.8.0 — 5 de novembro de 2026

Fotografia do estado em que a 2.8.0 foi preparada. Cada evidência indica onde e como foi obtida; o que não está listado não foi verificado.

## Escopo entregue

| Frente | PRs | Estado |
| --- | --- | --- |
| REL-01 importação transacional | [#207](https://github.com/bernardopg/doctoralia-scrapper/pull/207), [#208](https://github.com/bernardopg/doctoralia-scrapper/pull/208), [#212](https://github.com/bernardopg/doctoralia-scrapper/pull/212) | na main |
| REL-02 contrato de coleta | [#204](https://github.com/bernardopg/doctoralia-scrapper/pull/204), [#211](https://github.com/bernardopg/doctoralia-scrapper/pull/211) | na main |
| REL-03 identidade, conflitos e rascunhos | [#201](https://github.com/bernardopg/doctoralia-scrapper/pull/201), [#202](https://github.com/bernardopg/doctoralia-scrapper/pull/202), [#205](https://github.com/bernardopg/doctoralia-scrapper/pull/205), [#206](https://github.com/bernardopg/doctoralia-scrapper/pull/206), [#218](https://github.com/bernardopg/doctoralia-scrapper/pull/218) | na main |
| REL-04 XSS em navegador | [#203](https://github.com/bernardopg/doctoralia-scrapper/pull/203), [#213](https://github.com/bernardopg/doctoralia-scrapper/pull/213) | na main |
| REL-05 backend PostgreSQL opt-in | [#220](https://github.com/bernardopg/doctoralia-scrapper/pull/220) | na main; padrão continua `json` |
| REL-06 datas e paginação da fila | [#217](https://github.com/bernardopg/doctoralia-scrapper/pull/217) | na main |
| REL-07 normalização e n8n opcional | [#214](https://github.com/bernardopg/doctoralia-scrapper/pull/214), [#220](https://github.com/bernardopg/doctoralia-scrapper/pull/220) | na main |
| REL-08 estados e acessibilidade | [#219](https://github.com/bernardopg/doctoralia-scrapper/pull/219) | na main (fila de respostas e base) |
| REL-09 ensaio | este documento | executado |

## Testes

- Suíte completa com PostgreSQL 17 e Redis 8 descartáveis e compartilhados, como no CI: 646 passed, nenhum ignorado. black, isort, flake8 e mypy sem achados. CI do GitHub (Python 3.11–3.14, Docker, CodeQL) verde em cada PR mesclado.
- Navegador (Chromium 156 headless, dados sintéticos, rede externa bloqueada): `scripts/test_dashboard_browser.py` e `scripts/test_dashboard_ux.py` sem falhas; sem rolagem horizontal em 375, 768 e 1280 px nas seis telas principais.

## Ensaio de atualização, backup e restore (REL-09)

Executado num projeto Compose isolado (`dsr-rehearsal`, sem portas no host), com cópia do backup da instalação e tokens externos (Telegram, OpenAI, webhook) removidos do `.env`. A stack real não foi alterada.

1. Backup da instalação 2.7.2 em uso (`scripts/backup_restore.sh backup` + `verify`): arquivo de 900 KB, SHA-256 `190bbd20…02bb`; dump PostgreSQL, RDB do Redis, `data/`, config e `.env`.
2. Instalação limpa da tag `v2.7.2` + restore do dump: `users`/`workspaces`/`memberships` = 1/1/1, como na origem; stack saudável, `/v1/version` = 2.7.2.
3. Atualização para o código da 2.8.0: `db-init` aplicou `0001`→`0007` sobre o esquema pré-Alembic; dados preservados; todos os serviços saudáveis.
4. Os 32 snapshots da 2.7.2 (4985 avaliações) usam IDs posicionais e foram todos rejeitados pela importação, como esperado. O ensaio revelou que coletas novas gravavam o horário sem fuso e também eram rejeitadas; corrigido em #220 antes do release.
5. Coleta real autorizada de `https://www.doctoralia.com.br/bruna-pinto-gomes` com `STORAGE_BACKEND=postgres`: síncrona e assíncrona (worker), 164/164 avaliações, status `complete`, ~240 s cada; 164 importadas, 0 rejeitadas.
6. Leitura do dashboard pelo banco idêntica à leitura JSON (3 pendentes, 164 avaliações); edição de rascunho gravada no JSON e no banco; nova coleta reconheceu 164 duplicatas, 0 conflitos, edição preservada.
7. Rollback: `review_store export-drafts` e `STORAGE_BACKEND=json`; a edição permaneceu na fila.
8. Backup da instalação atualizada, destruição dos volumes e dos snapshots, restore: contagens do banco (`users`, `workspaces`, `reviews`, `review_observations`, `scrape_runs`, `review_drafts`, `snapshot_imports`, texto dos rascunhos) e SHA-256 dos 3 snapshots idênticos; `/v1/ready` com todos os componentes OK.

## Inventário do n8n

O banco do n8n da instalação tinha 0 workflows, 0 credenciais, 0 webhooks e 0 execuções ([inventário](integration-inventory.md)). O serviço passou a ser opcional; volume, endpoints e exemplos foram mantidos.

## Limites conhecidos

- O backend PostgreSQL é opt-in e só lê avaliações com identidade `doctoralia:<n>`; histórico anterior à 2.8.0 permanece apenas em JSON.
- Exclusão de snapshots pela interface opera sobre JSON; coletas no banco não são apagadas pela interface.
- A paginação real da Doctoralia não foi alterada: a coleta atual carrega todas as avaliações (164/164 no perfil testado). Outros perfis e mudanças futuras do site não foram verificados.
- Melhorias de REL-08 cobrem a fila de respostas e a base; as demais telas mantêm o layout anterior com as correções de segurança. Sem teste com leitor de tela, Firefox ou Safari.
- Tags, imagens GHCR e pacotes PyPI da 2.8.x estão publicados (ver abaixo). Health, readiness e versão na instalação em uso ainda não foram conferidos após atualização: isso depende do deploy pelo responsável.

## Patches 2.8.1–2.8.3 — 16 de novembro de 2026

Nenhum patch altera esquema, migrações ou formato dos snapshots. A atualização é a troca de imagem ou pacote; o backup antes continua recomendado.

| Versão | PR | Commit da tag | Conteúdo |
| --- | --- | --- | --- |
| 2.8.1 | [#228](https://github.com/bernardopg/doctoralia-scrapper/pull/228) | `afe9b31` | Dependências na versão mais recente (consolida os PRs do Dependabot #223–#227 e o que ele não rastreava), Python 3.15 na imagem e no CI, mínimo 3.11.5 |
| 2.8.2 | [#229](https://github.com/bernardopg/doctoralia-scrapper/pull/229) | `4699466` | Geração agendada do Telegram sem sobrescrever rascunhos, respeito a conflitos no PostgreSQL, escape de Markdown corrigido |
| 2.8.3 | [#230](https://github.com/bernardopg/doctoralia-scrapper/pull/230) e o PR deste registro | — | Teste ponta a ponta da geração agendada e esta documentação; sem mudança de comportamento |

### Verificações

- CI do GitHub verde em cada PR: Python 3.11–3.15, lint, segurança, Docker (build, varredura de vulnerabilidades e testes de integração), CodeQL e revisão de dependências. Exceção: no #229 o `codecov/patch` (não obrigatório) falhou com 56% de cobertura nas linhas novas; o #230 cobriu essas linhas e o check passou.
- Suíte local completa em Python 3.15 com PostgreSQL e Redis descartáveis: 656 testes no #229 e 657 no #230, sem falhas nem ignorados.
- Workflow de release concluído com sucesso: [v2.8.1](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/43999907978) e [v2.8.2](https://github.com/bernardopg/doctoralia-scrapper/actions/runs/44005466897). Os checksums da 2.8.3 ficam nas notas da sua release.

### Artefatos publicados

Os SHA-256 dos pacotes no PyPI coincidem com os anexos da GitHub Release. Digests das imagens obtidos com `docker buildx imagetools inspect`.

| Artefato | SHA-256 |
| --- | --- |
| `doctoralia_scrapper-2.8.1-py3-none-any.whl` | `fc4f1292a011343c9e44526063360901cc055c434b720cdcb63007a5ca816507` |
| `doctoralia_scrapper-2.8.1.tar.gz` | `38e901e4035ba5a2f1be946a70eabf2d8abb6ad271d76de86535fce40a1f1ee5` |
| `ghcr.io/bernardopg/doctoralia-scrapper/api:2.8.1` | `7c3dcc9361811bbd0990222ea29d9c5e58d499c48f2ea40f8afbe8dd687e5c47` |
| `ghcr.io/bernardopg/doctoralia-scrapper/worker:2.8.1` | `415980f799051c55dec3da7ae9c465cff2f89d1910b8b33be465e584b6d943c4` |
| `doctoralia_scrapper-2.8.2-py3-none-any.whl` | `243def58eecc994bdc97c52078d6851ac62f1423a17e55ee48b498c9131705bb` |
| `doctoralia_scrapper-2.8.2.tar.gz` | `3be016314b1a33458c8c694c1721381980e783bb232cf8cb39c9ae8e4bbcf5ea` |
| `ghcr.io/bernardopg/doctoralia-scrapper/api:2.8.2` | `92728eaef2d62f477507df989d4a8f55c8ba032e3d8b842a38632399e7c4830a` |
| `ghcr.io/bernardopg/doctoralia-scrapper/worker:2.8.2` | `b363fafd37b34434beee4d9345d2a66868bae8cef8f1562507f424457c1fc9f1` |

### Pendente

- Atualizar a instalação em uso (com backup antes) e conferir `/v1/health`, `/v1/ready` e `/v1/version`. Não foi feito nestes patches.
