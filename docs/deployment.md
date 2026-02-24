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
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<senha_segura>
LOG_LEVEL=INFO
```

## Docker Compose (Desenvolvimento / Staging)

O `docker-compose.yml` na raiz do projeto já inclui health checks e resource limits para todos os serviços:

```bash
docker-compose up -d --build
docker-compose ps
```

## Docker Compose para Produção

Para produção, crie `docker-compose.prod.yml` com ajustes:

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - api
    restart: always
    networks:
      - doctoralia-net

  api:
    build:
      context: .
      target: api
    env_file: .env
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    restart: always
    networks:
      - doctoralia-net

  worker:
    build:
      context: .
      target: worker
    env_file: .env
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
    restart: always
    networks:
      - doctoralia-net

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    restart: always
    networks:
      - doctoralia-net

  selenium:
    image: selenium/standalone-chrome:latest
    shm_size: "2g"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    restart: always
    networks:
      - doctoralia-net

  n8n:
    image: n8nio/n8n:latest
    environment:
      - N8N_PROTOCOL=https
      - N8N_HOST=${N8N_HOST}
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
    volumes:
      - n8n-data:/home/node/.n8n
    restart: always
    networks:
      - doctoralia-net

volumes:
  redis-data:
  n8n-data:

networks:
  doctoralia-net:
    driver: bridge
```

Deploy:

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

## Reverse Proxy (Nginx)

Exemplo de configuração com SSL e rate limiting:

```nginx
upstream api_backend {
    least_conn;
    server api:8000 max_fails=3 fail_timeout=30s;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        access_log off;
        proxy_pass http://api_backend/v1/health;
    }
}
```

## Health / Smoke Test

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/health
curl http://localhost:8000/v1/ready
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
