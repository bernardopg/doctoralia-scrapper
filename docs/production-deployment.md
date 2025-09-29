# 🏭 Guia de Deploy em Produção - Doctoralia Scrapper

## Índice

1. [Preparação do Ambiente](#preparação-do-ambiente)
2. [Configuração de Segurança](#configuração-de-segurança)
3. [Deploy com Docker](#deploy-com-docker)
4. [Deploy em Kubernetes](#deploy-em-kubernetes)
5. [Configuração de Proxy Reverso](#configuração-de-proxy-reverso)
6. [Monitoramento](#monitoramento)
7. [Backup e Recuperação](#backup-e-recuperação)
8. [Escalabilidade](#escalabilidade)

## Preparação do Ambiente

### Requisitos Mínimos

**Para até 100 requisições/minuto:**

- CPU: 4 cores
- RAM: 8GB
- Disco: 50GB SSD
- Rede: 100Mbps

**Para até 1000 requisições/minuto:**

- CPU: 8 cores
- RAM: 16GB
- Disco: 100GB SSD
- Rede: 1Gbps

### Checklist Pré-Deploy

- [ ] Servidor com Ubuntu 20.04+ ou RHEL 8+
- [ ] Docker 20.10+ e Docker Compose 2.0+
- [ ] Domínio configurado com DNS
- [ ] Certificado SSL (Let's Encrypt recomendado)
- [ ] Firewall configurado
- [ ] Sistema de backup configurado

## Configuração de Segurança

### 1. Variáveis de Ambiente Seguras

Crie um arquivo `.env.production`:

```bash
# API Security
API_KEY=$(openssl rand -hex 32)
WEBHOOK_SECRET=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Database
DATABASE_URL=postgresql://user:pass@db:5432/doctoralia_prod
REDIS_URL=redis://:password@redis:6379/0

# n8n Security
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=$(openssl rand -base64 32)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
PROMETHEUS_ENABLED=true

# Selenium Grid (para escalabilidade)
SELENIUM_HUB_URL=http://selenium-hub:4444
SELENIUM_MAX_SESSIONS=10

# SSL
SSL_CERT_PATH=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### 2. Configuração de Firewall

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# iptables alternativo
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -j DROP
```

### 3. Secrets Management

```bash
# Usando Docker Secrets
echo "your-api-key" | docker secret create api_key -
echo "your-webhook-secret" | docker secret create webhook_secret -

# Ou usando HashiCorp Vault
vault kv put secret/doctoralia api_key="..." webhook_secret="..."
```

## Deploy com Docker

### 1. Docker Compose para Produção

Crie `docker-compose.prod.yml`:

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
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - api
      - n8n
    restart: always
    networks:
      - doctoralia-network

  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    environment:
      - NODE_ENV=production
    env_file:
      - .env.production
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always
    networks:
      - doctoralia-network

  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: worker
    env_file:
      - .env.production
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '1'
          memory: 1G
    restart: always
    networks:
      - doctoralia-network

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    restart: always
    networks:
      - doctoralia-network

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: doctoralia_prod
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./backup:/backup
    restart: always
    networks:
      - doctoralia-network

  selenium-hub:
    image: selenium/hub:4.15.0
    environment:
      - SE_NODE_MAX_SESSIONS=5
      - SE_NODE_SESSION_TIMEOUT=300
    restart: always
    networks:
      - doctoralia-network

  selenium-chrome:
    image: selenium/node-chrome:4.15.0
    deploy:
      replicas: 3
    environment:
      - SE_EVENT_BUS_HOST=selenium-hub
      - SE_NODE_MAX_SESSIONS=2
    depends_on:
      - selenium-hub
    restart: always
    networks:
      - doctoralia-network

  n8n:
    image: n8nio/n8n:latest
    environment:
      - N8N_PROTOCOL=https
      - N8N_HOST=${N8N_HOST}
      - N8N_PORT=5678
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_USER=${DB_USER}
      - DB_POSTGRESDB_PASSWORD=${DB_PASSWORD}
    volumes:
      - n8n-data:/home/node/.n8n
    restart: always
    networks:
      - doctoralia-network

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: always
    networks:
      - doctoralia-network

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=redis-datasource
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    restart: always
    networks:
      - doctoralia-network

volumes:
  redis-data:
  postgres-data:
  n8n-data:
  prometheus-data:
  grafana-data:

networks:
  doctoralia-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 2. Deploy Script

```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Starting Production Deployment..."

# Load environment
export $(cat .env.production | xargs)

# Pull latest code
git pull origin main

# Build images
docker-compose -f docker-compose.prod.yml build

# Run database migrations
docker-compose -f docker-compose.prod.yml run --rm api python manage.py migrate

# Start services with zero-downtime
docker-compose -f docker-compose.prod.yml up -d --scale api=3 --scale worker=5

# Health check
sleep 10
curl -f https://yourdomain.com/health || exit 1

echo "✅ Deployment Complete!"
```

## Deploy em Kubernetes

### 1. Configuração Kubernetes

`k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: doctoralia-api
  namespace: doctoralia
spec:
  replicas: 3
  selector:
    matchLabels:
      app: doctoralia-api
  template:
    metadata:
      labels:
        app: doctoralia-api
    spec:
      containers:
      - name: api
        image: yourdocker.io/doctoralia-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: doctoralia-secrets
              key: api-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: doctoralia-api-service
  namespace: doctoralia
spec:
  selector:
    app: doctoralia-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: doctoralia-api-hpa
  namespace: doctoralia
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: doctoralia-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 2. Helm Chart

`helm/values.yaml`:

```yaml
replicaCount: 3

image:
  repository: yourdocker.io/doctoralia-api
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: LoadBalancer
  port: 80

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: api.yourdomain.com
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls:
    - secretName: doctoralia-tls
      hosts:
        - api.yourdomain.com

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

redis:
  enabled: true
  auth:
    enabled: true
    password: "your-redis-password"

postgresql:
  enabled: true
  auth:
    postgresPassword: "your-postgres-password"
    database: doctoralia_prod
```

## Configuração de Proxy Reverso

### Nginx Configuration

`nginx/nginx.conf`:

```nginx
upstream api_backend {
    least_conn;
    server api:8000 max_fails=3 fail_timeout=30s;
}

upstream n8n_backend {
    server n8n:5678;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=n8n_limit:10m rate=5r/s;

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
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # API endpoints
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }

    # n8n interface
    location /n8n/ {
        limit_req zone=n8n_limit burst=10 nodelay;

        auth_basic "n8n Admin";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://n8n_backend/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Monitoring endpoints (internal only)
    location /metrics {
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://api_backend/metrics;
    }

    # Health checks
    location /health {
        access_log off;
        proxy_pass http://api_backend/health;
    }
}
```

## Monitoramento

### 1. Prometheus Configuration

`monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'doctoralia-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - '/etc/prometheus/alerts.yml'
```

### 2. Alerting Rules

`monitoring/alerts.yml`:

```yaml
groups:
  - name: doctoralia_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is above 5% for 5 minutes"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is above 90%"

      - alert: APIDown
        expr: up{job="doctoralia-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API is down"
          description: "API has been down for more than 1 minute"
```

### 3. Grafana Dashboard

Importe o dashboard JSON em `monitoring/grafana/dashboards/`.

## Backup e Recuperação

### 1. Backup Automático

`scripts/backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec postgres pg_dump -U $DB_USER doctoralia_prod | gzip > $BACKUP_DIR/postgres.sql.gz

# Backup Redis
docker exec redis redis-cli --rdb $BACKUP_DIR/redis.rdb

# Backup n8n workflows
docker exec n8n n8n export:workflow --all --output=$BACKUP_DIR/workflows.json

# Backup environment files
cp .env.production $BACKUP_DIR/

# Upload to S3
aws s3 sync $BACKUP_DIR s3://your-backup-bucket/doctoralia/$BACKUP_DIR/

# Clean old backups (keep last 30 days)
find /backup -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_DIR"
```

### 2. Restore Script

`scripts/restore.sh`:

```bash
#!/bin/bash

BACKUP_DATE=$1

if [ -z "$BACKUP_DATE" ]; then
    echo "Usage: ./restore.sh YYYYMMDD_HHMMSS"
    exit 1
fi

# Download from S3
aws s3 sync s3://your-backup-bucket/doctoralia/$BACKUP_DATE /tmp/restore/

# Restore PostgreSQL
gunzip < /tmp/restore/postgres.sql.gz | docker exec -i postgres psql -U $DB_USER doctoralia_prod

# Restore Redis
docker cp /tmp/restore/redis.rdb redis:/data/dump.rdb
docker restart redis

# Restore n8n workflows
docker cp /tmp/restore/workflows.json n8n:/tmp/
docker exec n8n n8n import:workflow --input=/tmp/workflows.json

echo "Restore completed from: $BACKUP_DATE"
```

### 3. Cron Jobs

```bash
# Add to crontab
0 2 * * * /path/to/backup.sh >> /var/log/backup.log 2>&1
0 */6 * * * /path/to/health-check.sh >> /var/log/health.log 2>&1
```

## Escalabilidade

### 1. Horizontal Scaling

```bash
# Scale API
docker-compose -f docker-compose.prod.yml up -d --scale api=5

# Scale Workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=10

# Scale Selenium nodes
docker-compose -f docker-compose.prod.yml up -d --scale selenium-chrome=5
```

### 2. Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_scrape_jobs_status ON scrape_jobs(status);
CREATE INDEX idx_scrape_jobs_created ON scrape_jobs(created_at);
CREATE INDEX idx_doctor_data_url ON doctor_data(doctor_url);

-- Partitioning for large tables
CREATE TABLE scrape_jobs_2024_01 PARTITION OF scrape_jobs
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 3. Redis Clustering

```yaml
# Redis Cluster configuration
redis-master:
  image: redis:7-alpine
  command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf

redis-slave1:
  image: redis:7-alpine
  command: redis-server --slaveof redis-master 6379
```

### 4. CDN Integration

```nginx
# CloudFlare or AWS CloudFront
location /static/ {
    proxy_pass https://cdn.yourdomain.com/;
    proxy_cache_valid 200 1d;
    expires 1d;
    add_header Cache-Control "public, immutable";
}
```

## Checklist de Deploy

### Pre-Deploy

- [ ] Backup do ambiente atual
- [ ] Teste em staging
- [ ] Verificação de segurança
- [ ] Documentação atualizada

### Deploy

- [ ] Deploy da infraestrutura
- [ ] Deploy da aplicação
- [ ] Migração de dados
- [ ] Verificação de saúde

### Post-Deploy

- [ ] Monitoramento ativo
- [ ] Teste de funcionalidades
- [ ] Verificação de logs
- [ ] Comunicação com stakeholders

## Troubleshooting Produção

### High CPU Usage

```bash
# Identify process
docker stats
htop

# Scale horizontally
docker-compose scale api=5
```

### Memory Leaks

```bash
# Monitor memory
docker exec api cat /proc/meminfo
docker exec api ps aux --sort=-%mem | head

# Restart with memory limit
docker update --memory="2g" --memory-swap="2g" container_id
```

### Slow Queries

```sql
-- PostgreSQL slow query log
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

-- Analyze queries
EXPLAIN ANALYZE SELECT ...;
```

## Conclusão

Este guia cobre os aspectos essenciais para deploy em produção. Ajuste conforme suas necessidades específicas e sempre teste em ambiente de staging antes de aplicar em produção.

**Suporte:** Para questões específicas de produção, abra uma issue com a tag `production`.
