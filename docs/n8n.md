# 🪄 Integração n8n

Workflows prontos para orquestrar scraping, análise e notificações.

## Pré-Requisitos

- Stack rodando (`docker-compose up -d` ou serviços locais)
- API acessível em `http://api:8000` dentro da rede docker ou `http://localhost:8000` local
- Criar credencial Header Auth com `X-API-Key`

## Workflows Fornecidos (`examples/n8n/`)

| Arquivo | Propósito | Quando usar |
|---------|-----------|-------------|
| sync-scraping-workflow.json | Execução direta e rápida | Testes, validação inicial |
| async-webhook-workflow.json | Dispara job e recebe callback | Integrações externas |
| batch-processing-workflow.json | Processa lista de URLs com controle | Rotinas diárias/lotes |
| complete-doctoralia-workflow.json | Pipeline completo (triggers + alerts) | Produção / operação contínua |

## Padrões de Uso

1. Importar workflow
2. Ajustar URLs / parâmetros em node de configuração
3. Configurar credenciais (Header Auth, Telegram etc.)
4. Testar manualmente
5. Ativar agendamentos (Schedule / Cron)

## Modo Síncrono vs Assíncrono

| Critério | Síncrono | Assíncrono |
|----------|---------|------------|
| Latência | Resposta imediata | Retorno via polling ou callback |
| Tarefas longas | Arriscado (timeout) | Ideal |
| Orquestração complexa | Limitado | Escalável |
| Consumo de recursos | Concentrado | Distribuído |

## Polling Simples (Exemplo Node Function)

```javascript
// Recebe job_id de node anterior
const jobId = $json.data.job_id;
return [{ json: { job_id: jobId, attempt: 0 } }];
```

```javascript
// Poll (Function node c/ loop controlado)
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

## Callback (Webhook) – Validação de Assinatura

```javascript
// Function node após Webhook
const crypto = require('crypto');
const sig = $headers['x-signature'];
const ts = $headers['x-timestamp'];
const body = JSON.stringify($json);
const secret = $env.WEBHOOK_SECRET; // ou credencial

if (!sig || !ts) throw new Error('Headers ausentes');
const local = 'sha256=' + crypto.createHmac('sha256', secret).update(ts + '.' + body).digest('hex');
if (local !== sig) throw new Error('Assinatura inválida');
return items;
```

## Alertas Telegram Exemplo

```javascript
// Format (Function)
const d = $json.doctor;
const metrics = $json.analysis?.sentiments;
return [{ json: { message: `🏥 ${d.name} | ⭐ ${d.rating}\n😊 ${(metrics?.positive||0)*100}% 😐 ${(metrics?.neutral||0)*100}% 😞 ${(metrics?.negative||0)*100}%` } }];
```

## Boas Práticas

- Separar nodes: coleta / transformação / notificação
- Evitar loops infinitos em Function → usar IF + Wait
- Centralizar URLs base em variáveis de ambiente/nodes Set
- Capturar erros críticos e enviar alerta dedicado
- Usar credenciais nomeadas claramente (ex: Doctoralia API)

## Escalonamento

- Aumentar workers (containers) para jobs intensivos
- Dividir grandes listas com Split in Batches + rate limiting
- Implementar reprocessamento condicional (apenas mudanças)

## Tratamento de Falhas

| Cenário | Estratégia |
|---------|-----------|
| Timeout HTTP | Aumentar timeout node / mudar p/ async |
| Resposta parcial | Validar campos antes de seguir |
| Falha repetida | Circuit breaker no fluxo (ex: contador) |
| Bloqueio plataforma | Aumentar delays / reduzir frequência |

## Campos Úteis em Respostas

| Campo | Uso |
|-------|-----|
| doctor.name | Identificação clara no relatório |
| doctor.rating | Score atual |
| reviews[].rating | Distribuição de avaliação |
| analysis.sentiment.compound | Score de humor agregado |
| generation.responses[] | Texto de resposta proposto |

## Personalizações Comuns

- Adicionar persistência em Google Sheets / Notion / Airtable
- Construir painel sintético semanal
- Integrar com canal Slack para alertas críticos

## Segurança

- Validar assinatura de callbacks
- Sanitizar strings antes de inserir em planilhas
- Não logar tokens ou chaves
- Rodar n8n atrás de autenticação básica (já suportado)

## Fluxo Recomendo Produção (Resumo)

1. Trigger (Schedule / lista)
2. Dispara async job(s)
3. Poll controlado (ou callback)
4. Enriquecimento / agregação
5. Persistência + notificação
6. Alertas condicionais (sentimento negativo / queda de rating)

---
Exemplos práticos adicionais podem ser expandidos em futuras versões. Sugestões? Adicione issue com label `n8n`.
