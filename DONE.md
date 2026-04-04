# DONE - Main Features

Inventário das entregas principais que já estão maduras para o escopo atual do projeto.

## Plataforma base

- Stack Docker funcional com `api`, `worker`, `dashboard`, `redis`, `selenium` e `n8n`.
- Health checks e limites de recursos definidos para os serviços principais.
- Configuração local compartilhada entre API, worker e dashboard via `config/`.
- Redis consolidado como backbone operacional para fila, métricas e notificações.

## API e processamento

- API FastAPI com execução síncrona e assíncrona.
- Jobs em Redis/RQ com persistência de snapshots em `data/`.
- Health, readiness, statistics, settings e métricas Redis-backed.
- Webhook dedicado para integrações n8n.
- Geração unitária de respostas e análise de qualidade disponíveis por endpoint.

## Dashboard workspace

- Overview operacional com saúde da stack, backlog, timeline e atalhos.
- Páginas dedicadas para perfis, respostas, histórico, relatórios, settings e área do operador.
- Autenticação real do dashboard/API para a superfície web, com login, logout, sessão Flask assinada e proteção das rotas internas.
- Bootstrap de autenticação usando a `API Key Interna` como senha inicial quando ainda não existe senha dedicada configurada.
- Endpoints de autenticação para status, validação de login e troca de senha compartilhados entre API e dashboard.
- Histórico de snapshots com prune e exclusão individual.
- Relatórios com inventário de arquivos, resumo e exportação.
- Favoritos do operador persistidos em configuração.
- Área `/me` redesenhada como perfil operacional responsivo, com favoritos persistidos imediatamente, edição inline, atalho para rodar scraping por favorito e card funcional de segurança/login com troca de senha.
- Fluxo de troca de senha com regras explícitas na UI, validação inline por campo, toast de erro e medidor visual de força da nova senha.
- Rodapé da sidebar com contexto do operador hidratado em tempo real e navegação direta para a área do usuário.
- Tela dedicada de login, redirecionamento automático para `/login` em rotas protegidas e retorno ao destino original após autenticação.

## Telegram e notificações

- Notifier funcional com teste real de conectividade.
- Página dedicada de agendamentos Telegram no dashboard.
- CRUD completo de schedules pela API e pelo dashboard.
- Execução manual de agendamento, histórico persistido e anexos em disco.
- Relatórios `simple`, `complete` e `health`, com scraping novo opcional e geração opcional de respostas.
- Disparo manual de agendamento no dashboard desacoplado em background, sem bloquear a UI com timeout síncrono.
- UX do scheduler refinada com teste rápido dobrável, criação separada da edição inline e histórico com filtros/paginação client-side.
- Formatação das mensagens Telegram alinhada ao `parse_mode`, sem escapes espúrios em textos e nomes de arquivo.

## Documentação e branding

- README refeito como landing page visual do repositório.
- Wiki organizada em `docs/` com hub, navegação e páginas temáticas.
- Assets próprios do projeto: logo, banner, social card e diagramas SVG.
- Screenshots reais do dashboard incluídos na documentação.

## Qualidade e validação

- Imports internos padronizados em formato absoluto.
- Cobertura ampliada nas áreas críticas de API, Redis, dashboard, jobs e Telegram.
- Testes automatizados cobrindo sessão, login web, endpoints de autenticação e rotação de senha do dashboard.
- Estado validado continuamente por suíte automatizada e smoke checks locais do stack Docker.

## O que este arquivo não lista

Itens ainda abertos ou evoluções futuras ficam em [TODO.md](TODO.md).
