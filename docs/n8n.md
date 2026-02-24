# Integração n8n

Guia completo para integrar o Doctoralia Scraper com workflows n8n.

## Pré-Requisitos

- Stack rodando (`docker-compose up -d` ou serviços locais)
- API acessível em `http://api:8000` (rede Docker) ou `http://localhost:8000` (local)
- n8n acessível em `http://localhost:5678`

## Workflows Disponíveis (`examples/n8n/`)

| Arquivo | Propósito | Quando usar |
|---------|-----------|-------------|
| `sync-scraping-workflow.json` | Scraping síncrono, resposta imediata | Testes, validação inicial |
| `async-webhook-workflow.json` | Job assíncrono com callback HMAC | Integrações externas |
| `batch-processing-workflow.json` | Processa lista de URLs com rate limiting | Rotinas diárias/lotes |
| `complete-doctoralia-workflow.json` | Pipeline completo (triggers + alertas) | Produção / operação contínua |

### Detalhes dos Workflows

**Complete Doctoralia Workflow** — O principal, com 3 tipos de trigger (manual, webhook, schedule), processamento assíncrono com retry, análise de sentimento, múltiplos canais de notificação (Telegram, Email, Slack) e sistema de alertas para avaliações negativas.

**Batch Processing** — Otimizado para lotes: leitura de lista do Google Sheets, filtragem por última verificação, priorização (high/normal/low), rate limiting automático e relatório consolidado.

**Async Webhook** — Callbacks com assinatura HMAC-SHA256 para integração segura com sistemas externos.

## Configuração Inicial

### 1. Iniciar os Serviços

```bash
cp .env.example .env
# Edite .env com suas chaves

docker-compose up -d
docker-compose ps
```

Serviços esperados: `api` (:8000), `worker`, `redis` (:6379), `selenium` (:4444), `n8n` (:5678).

### 2. Acessar o n8n

Abra `http://localhost:5678`. Se configurou autenticação:
- Usuário: `N8N_BASIC_AUTH_USER` do `.env`
- Senha: `N8N_BASIC_AUTH_PASSWORD` do `.env`

## Importação dos Workflows

**Via interface web:**
1. No n8n, clique em **Workflows** > **Import from File**
2. Selecione o JSON do workflow desejado em `examples/n8n/`
3. Clique em **Import**

**Via API:**
```bash
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d @examples/n8n/complete-doctoralia-workflow.json
```

## Configuração de Credenciais

### Doctoralia API

No n8n: **Settings > Credentials > Create New**

- **Tipo:** Header Auth
- **Name:** `X-API-Key`
- **Value:** mesma chave definida em `API_KEY` no `.env`

### Telegram (Opcional)

- **Tipo:** Telegram
- **Token:** seu bot token
- **Chat ID:** seu chat ID

### Google Sheets (Opcional — para batch processing)

- **Tipo:** Google Sheets OAuth2 ou Service Account
- IDs necessários: `doctorsListId` (planilha com URLs) e `resultsSheetId` (resultados)

## Endpoints da API para n8n

### Scraping Síncrono

`POST /v1/scrape:run` — Resposta imediata com resultados.

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/example",
  "include_analysis": true,
  "include_generation": false,
  "language": "pt"
}
```

### Jobs Assíncronos

`POST /v1/jobs` — Cria job em background, retorna `job_id`.

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/example",
  "include_analysis": true,
  "callback_url": "https://seu-n8n/webhook/abc123",
  "mode": "async"
}
```

`GET /v1/jobs/{job_id}` — Consulta status do job.

### Webhook n8n

`POST /v1/hooks/n8n/scrape` — Endpoint dedicado para triggers n8n.

## Modo Síncrono vs Assíncrono

| Critério | Síncrono | Assíncrono |
|----------|---------|------------|
| Latência | Resposta imediata | Retorno via polling ou callback |
| Tarefas longas | Arriscado (timeout 30s) | Ideal (até 30min) |
| Orquestração | Limitado | Escalável |
| Recursos | Concentrado | Distribuído |

## Exemplos de Código

### Polling de Job (Function node)

```javascript
// Recebe job_id de node anterior
const jobId = $json.data.job_id;
return [{ json: { job_id: jobId, attempt: 0 } }];
```

```javascript
// Poll com limite de tentativas
const max = 10;
const delayMs = 5000;
let attempt = $json.attempt;
if (attempt >= max) { throw new Error('Timeout de polling'); }

const job = await this.helpers.httpRequest({
  method: 'GET',
  url: `http://api:8000/v1/jobs/${$json.job_id}`,
  headers: { 'X-API-Key': $credentials.doctoraliaApi.apiKey }
});

if (job.status === 'success' && job.data.status === 'completed') {
  return [{ json: job.data.result }];
}

await new Promise(r => setTimeout(r, delayMs));
return [{ json: { job_id: $json.job_id, attempt: attempt + 1 } }];
```

### Validação de Assinatura de Callback

```javascript
const crypto = require('crypto');
const sig = $headers['x-signature'];
const ts = $headers['x-timestamp'];
const body = JSON.stringify($json);
const secret = $env.WEBHOOK_SECRET;

if (!sig || !ts) throw new Error('Headers ausentes');
const local = 'sha256=' + crypto.createHmac('sha256', secret).update(ts + '.' + body).digest('hex');
if (local !== sig) throw new Error('Assinatura inválida');
return items;
```

### Formatação de Alerta Telegram

```javascript
const d = $json.doctor;
const metrics = $json.analysis?.sentiments;
return [{ json: { message: `${d.name} | ${d.rating}\nPositivo: ${(metrics?.positive||0)*100}% Neutro: ${(metrics?.neutral||0)*100}% Negativo: ${(metrics?.negative||0)*100}%` } }];
```

## Personalização

### Frequência de Execução

No node **Schedule**:
```javascript
// A cada 1 hora
"interval": [{ "field": "hours", "hoursInterval": 1 }]

// Horários específicos
"cronExpression": "0 9,15,21 * * *"  // 9h, 15h e 21h
```

### Condições de Alerta

No node **Check Alert Condition**:
```javascript
"conditions": {
  "number": [{
    "value1": "={{$json.metrics.sentiment_compound}}",
    "operation": "smaller",
    "value2": -0.5
  }]
}
```

## Boas Práticas

- Separar nodes: coleta / transformação / notificação
- Evitar loops infinitos em Function — usar IF + Wait
- Centralizar URLs base em variáveis de ambiente
- Capturar erros críticos e enviar alerta dedicado
- Usar credenciais nomeadas claramente
- Sempre testar em modo manual antes de agendar
- Fazer backup dos workflows regularmente

## Tratamento de Falhas

| Cenário | Estratégia |
|---------|-----------|
| Timeout HTTP | Aumentar timeout no node / usar async |
| Resposta parcial | Validar campos antes de seguir |
| Falha repetida | Circuit breaker no fluxo (contador) |
| Rate limiting | Aumentar delay no node Wait / reduzir batchSize |
| Connection refused | Verificar `docker-compose ps` e logs |
| Invalid API key | Verificar `.env` e recriar credencial no n8n |

## Fluxo Recomendado para Produção

1. Trigger (Schedule / lista)
2. Dispara async job(s)
3. Poll controlado (ou callback)
4. Enriquecimento / agregação
5. Persistência + notificação
6. Alertas condicionais (sentimento negativo / queda de rating)

## Campos Úteis em Respostas

| Campo | Uso |
|-------|-----|
| `doctor.name` | Identificação no relatório |
| `doctor.rating` | Score atual |
| `reviews[].rating` | Distribuição de avaliação |
| `analysis.sentiment.compound` | Score de humor agregado |
| `generation.responses[]` | Texto de resposta proposto |

---

Exemplos de workflows JSON completos em `examples/n8n/`. Sugestões? Abra issue com label `n8n`.
