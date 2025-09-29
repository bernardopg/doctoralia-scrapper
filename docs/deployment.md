# 🚀 Deployment

Guia resumido para colocar o sistema em produção com Docker.

## ✅ Requisitos (Indicativo)

| Perfil | CPU | RAM | Disco |
|--------|-----|-----|-------|
| Teste / PoC | 2 vCPU | 4GB | 20GB |
| Uso diário | 4 vCPU | 8GB | 50GB |

## 📂 Estrutura de Execução

| Item | Motivo |
|------|--------|
| API (FastAPI) | Endpoints / jobs |
| Worker (RQ) | Processa scraping pesado |
| Redis | Fila de jobs |
| Volume `data/` | Persistir extrações / respostas / logs |

## 🔐 .env Básico

```env
API_KEY=defina_forte
WEBHOOK_SECRET=defina_outro
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379/0
```

## 🐳 Docker Compose Exemplo (mínimo)

```yaml
services:
  api:
    build: .
    command: ["python", "main.py", "api"]
    env_file: .env
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"
    depends_on:
      - redis

  worker:
    build: .
    command: ["python", "main.py", "daemon"]
    env_file: .env
    volumes:
      - ./data:/app/data
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

Subir:

```bash
docker compose up -d --build
```

## 🌐 Reverse Proxy (Nginx Trecho)

```nginx
location / {
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header X-Forwarded-For $remote_addr;
  proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 🔎 Health / Smoke

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/health
```

## 🛡️ Checklist Segurança

- [ ] Rotacionar `API_KEY` periodicamente
- [ ] HTTPS ativo (Let's Encrypt / Traefik / Caddy)
- [ ] Restrição de acesso ao Redis (rede interna)
- [ ] Logs sem PII sensível
- [ ] Backup diário (`data/extractions`, `data/responses`)

## ♻️ Atualização

```bash
git pull origin main
docker compose build api worker
docker compose up -d api worker
```

## 🧯 Recuperação Rápida

| Problema | Ação |
|----------|------|
| Worker parado | `docker compose restart worker` |
| Jobs presos | Ver logs + estado Redis |
| Latência alta | Escalar worker / otimizar delays |
| Layout mudou | Rodar com debug e abrir issue |

---
Conteúdo extenso antigo foi simplificado; expandir conforme evolução.
