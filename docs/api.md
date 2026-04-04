[Wiki Home](Home.md) · [Quickstart](quickstart.md) · [Telegram Notifications](telegram-notifications.md) · [n8n](n8n.md)

# 🔌 API REST v1

A API expõe scraping, jobs assíncronos, settings, métricas Redis-backed, health checks, geração de respostas, autenticação compartilhada do dashboard e o scheduler Telegram através de endpoints RESTful.

**Base URL**: `http://localhost:8000` (desenvolvimento) ou seu domínio em produção
**Versão Atual**: `1.2.0-rc.1`

## Autenticação

Todos os endpoints protegidos requerem autenticação via header:

```http
X-API-Key: <SUA_CHAVE>
```

Configure a chave no arquivo `.env`:
```bash
API_KEY=sua_chave_secreta_aqui
```

**Nota**: endpoints de saúde (`/v1/health`, `/v1/ready`) não requerem autenticação. Os endpoints públicos de auth do dashboard (`/v1/auth/status` e `/v1/auth/login`) também não usam `X-API-Key`, porque servem ao fluxo de login web.

## Convenções de Resposta

### Resposta de Sucesso (UnifiedResult)

```json
{
  "doctor": {
    "id": "12345",
    "name": "Dr. João Silva",
    "specialty": "Cardiologia",
    "location": "São Paulo, SP",
    "rating": 4.8,
    "profile_url": "https://www.doctoralia.com.br/medico/joao-silva",
    "extra": {}
  },
  "reviews": [
    {
      "id": "r1",
      "date": "2024-01-15",
      "rating": 5,
      "text": "Excelente atendimento!",
      "author": {
        "name": "Maria Santos",
        "is_verified": true
      },
      "metadata": {}
    }
  ],
  "analysis": {
    "summary": "Analyzed 10 reviews",
    "sentiments": {
      "compound": 0.82,
      "positive": 0.75,
      "neutral": 0.20,
      "negative": 0.05
    },
    "quality_score": 82.0,
    "flags": []
  },
  "generation": {
    "template_id": "professional",
    "responses": [
      {
        "review_id": "r1",
        "text": "Muito obrigado pelo feedback positivo!",
        "language": "pt"
      }
    ],
    "model": {"type": "rule-based"}
  },
  "metrics": {
    "scraped_count": 10,
    "start_ts": "2024-01-15T10:30:00Z",
    "end_ts": "2024-01-15T10:30:15Z",
    "duration_ms": 15000,
    "source": "doctoralia"
  },
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed"
}
```

### Resposta de Erro

```json
{
  "error": {
    "code": "SCRAPE_FAILED",
    "message": "Failed to scrape reviews",
    "details": "Connection timeout",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Headers de Resposta

Todas as respostas incluem:
- `X-Request-Id`: Identificador único da requisição
- `X-Response-Time-ms`: Tempo de processamento em milissegundos

## Principais Endpoints

### 1. Scraping Síncrono

Executa scraping e retorna resultados imediatamente.

**Endpoint**: `POST /v1/scrape:run`
**Autenticação**: Requerida (`X-API-Key`)
**Timeout recomendado**: 60 segundos

#### Request Body

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/joao-silva-cardiologista/12345",
  "include_analysis": true,
  "include_generation": false,
  "response_template_id": "professional",
  "language": "pt",
  "meta": {
    "source": "dashboard",
    "user_id": "123"
  }
}
```

**Parâmetros**:
- `doctor_url` (obrigatório): URL completa do perfil do médico
- `include_analysis` (opcional, padrão: `true`): Incluir análise de sentimento
- `include_generation` (opcional, padrão: `false`): Gerar respostas para reviews
- `response_template_id` (opcional): ID do template de resposta
- `language` (opcional, padrão: `"pt"`): Idioma das respostas
- `meta` (opcional): Metadados adicionais

#### Response

Retorna `UnifiedResult` (ver estrutura em "Convenções de Resposta")

**Status**: `200 OK` em caso de sucesso (mesmo com falhas parciais)

#### Exemplo com cURL

```bash
curl -X POST http://localhost:8000/v1/scrape:run \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
    "include_analysis": true,
    "include_generation": false
  }'
```

### 2. Jobs Assíncronos

Para operações longas ou integração com sistemas de filas (n8n, workflows).

#### 2.1. Criar Job Assíncrono

**Endpoint**: `POST /v1/jobs`
**Autenticação**: Requerida (`X-API-Key`)
**Status HTTP**: `202 Accepted`

##### Request Body

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
  "include_analysis": true,
  "include_generation": true,
  "response_template_id": "professional",
  "language": "pt",
  "mode": "async",
  "callback_url": "https://seu-servidor.com/webhook/callback",
  "idempotency_key": "unique-key-123",
  "meta": {}
}
```

**Parâmetros**:
- Mesmos parâmetros do endpoint síncrono, mais:
- `mode` (obrigatório): Deve ser `"async"`
- `callback_url` (opcional): URL para receber resultado via webhook
- `idempotency_key` (opcional): Chave para evitar duplicação de jobs

##### Response

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job created successfully"
}
```

**Idempotência**: Se enviar o mesmo `idempotency_key` dentro de 1 hora, retorna o job existente.

##### Exemplo com cURL

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
    "include_analysis": true,
    "mode": "async",
    "callback_url": "https://meu-servidor.com/callback"
  }'
```

#### 2.2. Consultar Status do Job

**Endpoint**: `GET /v1/jobs/{job_id}`
**Autenticação**: Requerida (`X-API-Key`)

##### Response

Se o job ainda está em execução:
```json
{
  "doctor": {"name": "Processing", "url": ""},
  "reviews": [],
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  ...
}
```

Se o job foi concluído, retorna `UnifiedResult` completo.

**Possíveis valores de `status`**:
- `running`: Job em execução
- `completed`: Job concluído com sucesso
- `failed`: Job falhou

##### Exemplo com cURL

```bash
curl -X GET http://localhost:8000/v1/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: $API_KEY"
```

### 3. Webhook n8n

Endpoint dedicado para triggers n8n. Cria um job assíncrono e retorna confirmação imediata.

**Endpoint**: `POST /v1/hooks/n8n/scrape`
**Autenticação**: Webhook Signature (ver seção "Segurança de Webhooks")

#### Request Body

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
  "callback_url": "https://n8n.meudominio.com/webhook/resultado",
  "include_analysis": true,
  "include_generation": false,
  "response_template_id": "professional",
  "language": "pt"
}
```

**Parâmetros**:
- `doctor_url` (obrigatório): URL do perfil do médico
- `callback_url` (opcional): URL para callback com resultado
- Demais parâmetros opcionais iguais ao endpoint de scraping

#### Response

```json
{
  "received": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

#### Segurança de Webhooks

O endpoint valida assinatura HMAC-SHA256 no header:

```http
X-Webhook-Signature: sha256=<hex_digest>
```

**Cálculo da assinatura**:
```python
import hmac
import hashlib

signature = hmac.new(
    WEBHOOK_SIGNING_SECRET.encode(),
    request_body.encode(),
    hashlib.sha256
).hexdigest()
```

Configure o secret no `.env`:
```bash
WEBHOOK_SIGNING_SECRET=seu_secret_compartilhado
```

### 4. Autenticação do Dashboard

Esses endpoints expõem o estado de autenticação usado pela superfície web em `http://localhost:5000`.

#### 4.1. Estado da autenticação

**Endpoint**: `GET /v1/auth/status`

##### Response

```json
{
  "auth_enabled": true,
  "password_configured": true,
  "bootstrap_password_enabled": false,
  "session_ttl_minutes": 480,
  "user": {
    "username": "admin"
  },
  "message": null
}
```

#### 4.2. Validar login do dashboard

**Endpoint**: `POST /v1/auth/login`

##### Request Body

```json
{
  "username": "admin",
  "password": "sua_senha"
}
```

##### Response

```json
{
  "success": true,
  "message": "Dashboard login successful",
  "user": {
    "username": "admin"
  }
}
```

#### 4.3. Trocar senha do dashboard

**Endpoint**: `POST /v1/auth/change-password`
**Autenticação**: Requerida (`X-API-Key`)

##### Request Body

```json
{
  "current_password": "senha_atual",
  "new_password": "senha_nova_com_8_ou_mais_caracteres"
}
```

##### Regras atuais

- a nova senha precisa ter pelo menos `8` caracteres
- a senha atual precisa coincidir com a senha dedicada já configurada ou, no bootstrap inicial, com a `API_KEY`

### 5. Monitoramento e Saúde

Endpoints para monitoramento da aplicação (não requerem autenticação).

#### 5.1. Health Check

**Endpoint**: `GET /v1/health`

Verifica saúde básica da API.

##### Response

```json
{
  "status": "ok",
  "version": "1.2.0-rc.1",
  "uptime_s": 3600
}
```

#### 5.2. Readiness Check

**Endpoint**: `GET /v1/ready`

Verifica disponibilidade de todas as dependências.

##### Response (200 OK se pronto)

```json
{
  "ready": true,
  "checks": {
    "redis": true,
    "queue": true,
    "templates": true,
    "nltk_vader": true,
    "selenium": true
  },
  "components": {
    "redis": {
      "status": true,
      "latency_ms": 5,
      "error": null
    },
    "queue": {
      "status": true,
      "latency_ms": 12,
      "error": null,
      "details": {
        "depth": 3,
        "failed": 0
      }
    },
    ...
  }
}
```

**Status HTTP**: `200 OK` se pronto, `503 Service Unavailable` se algum componente falhou.

#### 5.3. Versão da API

**Endpoint**: `GET /v1/version`

##### Response

```json
{
  "version": "1.2.0-rc.1",
  "start_time": "2024-01-15T10:00:00.000000"
}
```

#### 5.4. Métricas

**Endpoint**: `GET /v1/metrics`

Métricas de performance e uso da API persistidas em Redis para leitura consistente entre processos.

##### Response

```json
{
  "version": "1.2.0-rc.1",
  "uptime_s": 3600,
  "requests": {
    "total": 1523,
    "in_progress": 2,
    "failed": 15,
    "p50_ms": 234,
    "p95_ms": 1205,
    "p99_ms": 3421,
    "latest_ms": 456,
    "sample_size": 500
  },
  "scraping": {
    "scrapes_total": 342,
    "scrapes_failed_total": 12,
    "analysis_total": 298,
    "generation_total": 156
  }
}
```

#### 5.5. Notificações Telegram

**Base**: `/v1/notifications/telegram`

Principais rotas:

| Método | Endpoint | Uso |
|---|---|---|
| `GET` | `/schedules` | Lista agendamentos e resumo |
| `POST` | `/schedules` | Cria novo agendamento |
| `PUT` | `/schedules/{schedule_id}` | Atualiza um agendamento |
| `DELETE` | `/schedules/{schedule_id}` | Remove um agendamento |
| `POST` | `/schedules/{schedule_id}/run` | Executa manualmente |
| `GET` | `/history` | Histórico persistido das execuções |
| `POST` | `/test` | Envio real de teste para validar bot e chat |

Use [Telegram Notifications](telegram-notifications.md) para o fluxo operacional completo e os detalhes de payload.

### 6. Endpoint Raiz

**Endpoint**: `GET /`

Retorna informações básicas e link para documentação.

```json
{
  "message": "Doctoralia Scrapper API",
  "docs": "/docs"
}
```

## Códigos de Erro

A API utiliza códigos HTTP padrão e retorna detalhes estruturados:

### Códigos HTTP

| Código | Significado | Quando ocorre |
|--------|-------------|---------------|
| `200` | OK | Requisição bem-sucedida |
| `202` | Accepted | Job assíncrono criado |
| `400` | Bad Request | Parâmetros inválidos |
| `401` | Unauthorized | API Key ausente ou inválida |
| `404` | Not Found | Recurso não encontrado (ex: job_id) |
| `500` | Internal Server Error | Erro interno do servidor |
| `503` | Service Unavailable | Dependências indisponíveis |

### Códigos de Erro Personalizados

| Código | Descrição | Ação Recomendada |
|--------|-----------|------------------|
| `BAD_REQUEST` | Requisição malformada | Verificar formato do JSON e parâmetros |
| `UNAUTHORIZED` | Autenticação falhou | Verificar header X-API-Key |
| `NOT_FOUND` | Recurso não encontrado | Verificar job_id ou URL |
| `INTERNAL_ERROR` | Erro interno | Verificar logs, reportar se persistir |
| `SCRAPE_FAILED` | Falha no scraping | Verificar URL, site pode estar fora do ar |
| `RATE_LIMIT` | Limite de taxa excedido | Aguardar e aplicar backoff exponencial |

### Exemplo de Resposta de Erro

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "API key is missing or invalid",
    "details": null,
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

## Callbacks (Webhooks)

Quando você fornece `callback_url` em um job assíncrono, a API envia o resultado via POST.

### Request Enviado para Callback

```http
POST {callback_url}
Content-Type: application/json
X-Webhook-Signature: sha256=<hmac_hex_digest>

{
  "doctor": {...},
  "reviews": [...],
  "analysis": {...},
  ...
}
```

### Validando Assinatura do Callback

```python
import hmac
import hashlib

def verify_webhook(request):
    signature_header = request.headers.get('X-Webhook-Signature', '')
    expected_signature = signature_header.replace('sha256=', '')

    computed = hmac.new(
        WEBHOOK_SIGNING_SECRET.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, computed)
```

## Idempotência

Para evitar duplicação de jobs, use `idempotency_key`:

```json
{
  "doctor_url": "https://...",
  "mode": "async",
  "idempotency_key": "order-12345-retry-1"
}
```

- Chaves são armazenadas por **1 hora**
- Requisições com mesma chave retornam o job existente
- Use chaves únicas por operação (ex: combine ID da ordem + timestamp)

## Rate Limiting

**Limites atuais**: Não há rate limiting explícito implementado, mas recomenda-se:
- Máximo 10 requisições síncronas por minuto
- Use jobs assíncronos para operações em lote

**Boas práticas**:
- Implemente backoff exponencial em caso de erros `429` ou `5xx`
- Use jobs assíncronos para operações que não precisam de resposta imediata

## Versionamento

- **Versão atual**: `v1` (prefixo `/v1/` em todos os endpoints)
- Mudanças compatíveis (novos campos opcionais) serão adicionadas sem incrementar versão
- Mudanças incompatíveis (remoção de campos, mudança de tipos) resultarão em `/v2/`

## Exemplos Práticos

### Exemplo 1: Scraping Síncrono Completo

```bash
curl -X POST http://localhost:8000/v1/scrape:run \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/joao-silva-cardiologista/12345",
    "include_analysis": true,
    "include_generation": true,
    "language": "pt"
  }' | jq '.'
```

### Exemplo 2: Job Assíncrono com Polling

```bash
# Criar job
JOB_ID=$(curl -s -X POST http://localhost:8000/v1/jobs \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
    "include_analysis": true,
    "mode": "async"
  }' | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# Polling (verificar a cada 5 segundos)
while true; do
  STATUS=$(curl -s -H "X-API-Key: $API_KEY" \
    http://localhost:8000/v1/jobs/$JOB_ID | jq -r '.status')

  echo "Status: $STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    curl -s -H "X-API-Key: $API_KEY" \
      http://localhost:8000/v1/jobs/$JOB_ID | jq '.'
    break
  fi

  sleep 5
done
```

### Exemplo 3: Webhook n8n com Callback

```bash
curl -X POST http://localhost:8000/v1/hooks/n8n/scrape \
  -H "X-Webhook-Signature: sha256=$(echo -n '{"doctor_url":"..."}' | \
    openssl dgst -sha256 -hmac "$WEBHOOK_SIGNING_SECRET" | cut -d' ' -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
    "callback_url": "https://n8n.meudominio.com/webhook/resultado",
    "include_analysis": true
  }'
```

### Exemplo 4: Monitoramento de Saúde

```bash
# Health check simples
curl http://localhost:8000/v1/health

# Readiness com detalhes
curl http://localhost:8000/v1/ready | jq '.'

# Métricas de performance
curl http://localhost:8000/v1/metrics | jq '.requests'
```

## Boas Práticas

### Para Clientes da API

1. **Timeouts apropriados**:
   - Scraping síncrono: 60-90 segundos
   - Jobs e webhooks: 10 segundos
   - Health checks: 5 segundos

2. **Retry com Backoff**:
   ```python
   import time
   import requests

   def call_api_with_retry(url, max_retries=3):
       for attempt in range(max_retries):
           try:
               response = requests.post(url, timeout=60)
               response.raise_for_status()
               return response.json()
           except requests.exceptions.RequestException as e:
               if attempt == max_retries - 1:
                   raise
               wait_time = 2 ** attempt  # 1s, 2s, 4s
               time.sleep(wait_time)
   ```

3. **Usar modo assíncrono**:
   - Para scraping de múltiplos perfis
   - Em workflows n8n
   - Quando integrado com sistemas de filas

4. **Reutilizar conexões HTTP**:
   ```python
   session = requests.Session()
   session.headers.update({'X-API-Key': API_KEY})
   # Usar session.post() para todas as requisições
   ```

5. **Validar webhooks**:
   - Sempre valide a assinatura HMAC
   - Implemente timeout para processar callbacks
   - Retorne `200 OK` rapidamente

### Para Desenvolvedores

1. **Documentação interativa**: Acesse `/docs` para Swagger UI
2. **ReDoc**: Acesse `/redoc` para documentação alternativa
3. **OpenAPI spec**: Disponível em `/openapi.json`

## Documentação Adicional

- **Wiki Home**: ver `docs/Home.md`
- **Telegram Notifications**: ver `docs/telegram-notifications.md`
- **n8n Integration**: ver `docs/n8n.md`
- **Deployment**: ver `docs/deployment.md`
- **Operations**: ver `docs/operations.md`
- **Development**: ver `docs/development.md`

## Suporte

- **API Docs**: `/docs` (Swagger UI)
- **Health Status**: `/v1/health` e `/v1/ready`
- **Wiki**: `docs/Home.md`
