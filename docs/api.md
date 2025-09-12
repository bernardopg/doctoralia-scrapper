# 🔌 API REST v1

A API expõe operações de scraping, análise, geração e monitoramento.

## Autenticação

Enviar header:

```api
X-API-Key: <SUA_CHAVE>
```

(Planejado: suporte opcional a Bearer / JWT)

## Convenções de Resposta

```json
{
  "status": "success|error",
  "data": { ... },
  "error": {
    "code": "STRING",
    "message": "Descrição humana",
    "details": { }
  },
  "meta": {"request_id": "...", "duration_ms": 123}
}
```

## Principais Endpoints

### Scraping Síncrono

```text
POST /v1/scrape:run
```

Request:

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
  "include_analysis": true,
  "include_generation": false,
  "language": "pt"
}
```

Resposta (exemplo reduzido):

```json
{
  "status": "success",
  "data": {
    "doctor": {"name": "Dr. Exemplo", "rating": 4.7},
    "reviews": [{"id": "r1", "rating": 5, "text": "Ótimo"}],
    "analysis": {"sentiment": {"compound": 0.82}},
    "generation": null
  },
  "meta": {"duration_ms": 5423}
}
```

### Jobs Assíncronos

Criar job:

```text
POST /v1/jobs
```

```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
  "include_analysis": true,
  "include_generation": true,
  "mode": "async",
  "callback_url": "https://seu-servidor/webhook/retorno",
  "idempotency_key": "abc-123-opcional"
}
```

Status:

```text
GET /v1/jobs/{job_id}
```

Cancelamento (se suportado futuramente):

```text
DELETE /v1/jobs/{job_id}
```

### Webhook Dedicado n8n

```txt
POST /v1/hooks/n8n/scrape
```

Aceita payload mínimo:

```json
{"doctor_url": "https://www.doctoralia.com.br/medico/exemplo"}
```

### Análise de Qualidade Isolada

```text
POST /v1/analyze/quality
```

```json
{"response_text": "Obrigado!", "original_review": "Excelente atendimento"}
```

### Batch de Análise

```text
POST /v1/analyze/quality/batch
```

```json
{"analyses": [{"response_text": "Ok", "original_review": "Bom"}]}
```

### Monitoramento

```text
GET /v1/health      # Saúde básica
GET /v1/ready       # Pronto (dependências ok)
GET /v1/statistics  # Métricas agregadas
GET /v1/performance # Performance recente
GET /v1/platforms   # Plataformas suportadas
```

## Erros Comuns

| Código | Situação | Mitigação |
|--------|----------|-----------|
| INVALID_URL | URL inválida/não suportada | Validar antes de enviar |
| RATE_LIMIT | Muitas requisições | Aguardar e aplicar backoff |
| SCRAPE_FAILED | Estrutura mudou/bloqueio | Reexecutar com debug, revisar seletor |
| TIMEOUT | Página lenta | Aumentar timeout config |
| UNAUTHORIZED | API key ausente/errada | Revisar header |

## Webhooks (Callback) – Assinatura

Cabeçalhos enviados:

```text
X-Signature: sha256=<hex>
X-Timestamp: <epoch>
```

Assinatura:

```text
HMAC_SHA256( WEBHOOK_SECRET,  timestamp + "." + raw_body )
```

Valide diferença de tempo (<5m) + comparação constante.

## Idempotência

Enviar `Idempotency-Key` em headers (ou campo `idempotency_key`). Servidor retorna mesmo job se chave já usada com mesmo payload.

## Versionamento

- Prefixo atual: `/v1/`
- Mudanças compatíveis: adicionadas sem quebrar contratos
- Futuro `/v2/` se formato de campos/chaves mudar

## Paginação (Planejado)

Endpoints agregadores retornarão:

```json
{"data": [...], "pagination": {"next_cursor": "..."}}
```

## Exemplo Curl Completo (Async + Polling)

```bash
JOB=$(curl -s -X POST http://localhost:8000/v1/jobs \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"doctor_url": "https://www.doctoralia.com.br/medico/exemplo", "include_analysis": true, "mode": "async"}' | jq -r '.data.job_id')

watch -n 3 curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/v1/jobs/$JOB | head
```

## Boas Práticas Cliente

- Reutilizar conexões HTTP (keep-alive)
- Aplicar timeout > maior que o esperado do servidor (sync) ~ 35s
- Usar modo async para fluxos orquestrados/n8n
- Implementar retries somente para códigos transitórios (429 / 5xx)

---
Mais exemplos aplicados em `docs/n8n.md`.
