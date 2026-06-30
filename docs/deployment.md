[Wiki Home](Home.md) · [Operations](operations.md) · [Development](development.md) · [API REST](api.md)

# Deployment

Guia para deploy do sistema em produção com Docker.

## Requisitos

| Perfil | CPU | RAM | Disco |
|--------|-----|-----|-------|
| Teste / PoC | 2 vCPU | 4 GB | 20 GB |
| Uso diário (< 100 req/min) | 4 vCPU | 8 GB | 50 GB SSD |
| Alta carga (< 1000 req/min) | 8 vCPU | 16 GB | 100 GB SSD |

### Checklist Pré-Deploy

- [ ] Docker 20.10+ e Docker Compose 2.0+
- [ ] Domínio configurado com DNS (se expor publicamente)
- [ ] Certificado SSL (Let's Encrypt recomendado)
- [ ] Firewall configurado
- [ ] Sistema de backup configurado

## Serviços

| Serviço | Função | Porta |
|---------|--------|-------|
| API (FastAPI) | Endpoints REST / jobs | 8000 |
| Dashboard (Flask) | Workspace web autenticado | 5000 |
| Worker (RQ) | Processa scraping em background | — |
| Redis | Fila de jobs | 6379 |
| Selenium | Browser para scraping | 4444 |
| n8n | Orquestração de workflows | 5678 |

## Variáveis de Ambiente

Crie `.env` a partir do template:

```bash
cp .env.example .env
```

Variáveis obrigatórias:

```env
API_KEY=<chave_forte_gerada_com_openssl_rand_hex_32>
WEBHOOK_SIGNING_SECRET=<segredo_para_hmac>
REDIS_URL=redis://redis:6379/0
SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
```

Variáveis opcionais:

```env
TELEGRAM_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>
OPENAI_API_KEY=<chave_openai>
DASHBOARD_AUTH_ENABLED=true
DASHBOARD_PASSWORD_HASH=<hash_werkzeug_opcional>
DASHBOARD_SESSION_SECRET=<segredo_para_cookie_de_sessao>
DASHBOARD_SESSION_TTL_MINUTES=480
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<senha_segura>
N8N_ENCRYPTION_KEY=<64_hex_chars>
N8N_EDITOR_BASE_URL=https://automations.seudominio.com
WEBHOOK_URL=https://automations.seudominio.com/
LOG_LEVEL=INFO
```

No compose local atual, o n8n também fica preso em `127.0.0.1:5678` e exige auth básica.

### Bootstrap de autenticação do dashboard

Sem `DASHBOARD_PASSWORD_HASH`, o dashboard ainda pode subir autenticado usando este comportamento:

- o usuário esperado vem de `user_profile.username`
- a senha inicial é a `API_KEY`
- a primeira rotação em `/me` grava uma senha dedicada e desativa o bootstrap

Para produção, prefira definir também:

- `DASHBOARD_SESSION_SECRET` com um segredo próprio, sem reaproveitar outros segredos
- `DASHBOARD_PASSWORD_HASH` já provisionado, para não depender da `API_KEY` como senha inicial

## Docker Compose (Desenvolvimento / Staging)

O `docker-compose.yml` na raiz do projeto já inclui health checks e limites para os serviços principais:

```bash
docker compose up -d --build
docker compose ps
```

## Docker Compose para Produção

O projeto já inclui um overlay de produção (`docker-compose.prod.yml`) que
adiciona **Caddy** como reverse proxy com **TLS automático** na frente de
`api`, `dashboard` e `n8n`. O overlay também:

- remove a publicação direta das portas internas (só o Caddy expõe 80/443);
- exige senha no Redis (`REDIS_PASSWORD`) e injeta a URL autenticada na API/worker;
- aplica `restart: always` em todos os serviços.

### Subir em produção

```bash
# Defina no .env: APP_DOMAIN, N8N_DOMAIN, REDIS_PASSWORD
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### TLS automático (Caddy)

O `caddy/Caddyfile` decide o certificado pelo domínio configurado:

| Cenário | `APP_DOMAIN` | Certificado |
|---------|--------------|-------------|
| Local / staging | `localhost` (default) | self-signed da CA interna do Caddy (sem rede) |
| Produção | domínio real (DNS apontando para o host) | Let's Encrypt automático |

Para produção, basta apontar o DNS do domínio para o host e definir
`APP_DOMAIN`/`N8N_DOMAIN`; o Caddy provisiona e renova os certificados sozinho.

Variáveis relevantes no `.env`:

```env
APP_DOMAIN=app.seudominio.com      # dashboard + API
N8N_DOMAIN=n8n.seudominio.com      # editor n8n
REDIS_PASSWORD=<openssl rand -hex 24>
# Opcional: se a porta 443 do host já estiver em uso (teste local)
CADDY_HTTP_PORT=8080
CADDY_HTTPS_PORT=8443
```

### Roteamento e segurança

O Caddy aplica os cabeçalhos `Strict-Transport-Security` (HSTS),
`X-Frame-Options`, `X-Content-Type-Options` e `Referrer-Policy` em todas as
respostas, redireciona HTTP→HTTPS automaticamente e roteia:

| Caminho | Destino |
|---------|---------|
| `/v1/*`, `/docs`, `/openapi.json` | API (`api:8000`) |
| `/` e demais rotas | Dashboard (`dashboard:5000`) |
| `{N8N_DOMAIN}` | n8n (`n8n:5678`) |

## Health / Smoke Test

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/health
curl http://localhost:8000/v1/ready
curl http://localhost:8000/v1/auth/status
```

## Firewall

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Checklist de Segurança

- [ ] `API_KEY` forte (gerada com `openssl rand -hex 32`)
- [ ] `DASHBOARD_SESSION_SECRET` próprio e forte
- [ ] `DASHBOARD_PASSWORD_HASH` provisionado antes de expor o dashboard publicamente
- [ ] HTTPS ativo (Let's Encrypt / Traefik / Caddy)
- [ ] Redis acessível apenas na rede interna
- [ ] Logs sem PII sensível (`MASK_PII=true`)
- [ ] Rotacionar `API_KEY` periodicamente

## Backup e Recuperação

### Backup Automático

```bash
#!/bin/bash
BACKUP_DIR="/backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup Redis
docker exec redis redis-cli --rdb /data/dump.rdb
docker cp redis:/data/dump.rdb $BACKUP_DIR/redis.rdb

# Backup dados de scraping
tar -czf $BACKUP_DIR/data.tgz data/

# Backup n8n workflows
docker exec n8n n8n export:workflow --all --output=/tmp/workflows.json
docker cp n8n:/tmp/workflows.json $BACKUP_DIR/

# Backup configs
cp .env $BACKUP_DIR/
cp config/config.json $BACKUP_DIR/

# Limpar backups antigos (>30 dias)
find /backup -type d -mtime +30 -exec rm -rf {} \;
```

### Restore

```bash
# Restore Redis
docker cp backup/redis.rdb redis:/data/dump.rdb
docker restart redis

# Restore n8n
docker cp backup/workflows.json n8n:/tmp/
docker exec n8n n8n import:workflow --input=/tmp/workflows.json
```

### Cron de Backup

```bash
# Adicionar ao crontab
0 2 * * * /path/to/backup.sh >> /var/log/backup.log 2>&1
```

## Escalabilidade

```bash
# Escalar API
docker-compose -f docker-compose.prod.yml up -d --scale api=5

# Escalar workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=10
```

## Atualização

```bash
git pull origin main
docker-compose build api worker
docker-compose up -d api worker
```

## Troubleshooting

| Problema | Ação |
|----------|------|
| Worker parado | `docker-compose restart worker` |
| Jobs presos | Ver logs + estado Redis (`docker-compose logs worker`) |
| Latência alta | Escalar workers / ajustar delays no config.json |
| High CPU | `docker stats` para identificar container, escalar horizontalmente |
| Memory leak | `docker update --memory="2g" container_id`, reiniciar |

## Deploy em Kubernetes (Avançado)

Para deploy em K8s, crie manifests com:

- Deployment para `api` e `worker` (replicas, resource limits, probes)
- Service LoadBalancer para expor a API
- HorizontalPodAutoscaler (CPU/memory targets)
- Secrets para `API_KEY`, `WEBHOOK_SIGNING_SECRET`

Health probes recomendados:
- Liveness: `GET /v1/health` (interval: 10s)
- Readiness: `GET /v1/ready` (interval: 5s)

---

Para operações do dia-a-dia, consulte `docs/operations.md`.
