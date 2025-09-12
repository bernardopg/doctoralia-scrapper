# 📚 Guia Completo de Workflows n8n para Doctoralia Scrapper

## Índice

1. [Visão Geral](#visão-geral)
2. [Workflows Disponíveis](#workflows-disponíveis)
3. [Configuração Inicial](#configuração-inicial)
4. [Importação dos Workflows](#importação-dos-workflows)
5. [Configuração de Credenciais](#configuração-de-credenciais)
6. [Personalização](#personalização)
7. [Monitoramento e Alertas](#monitoramento-e-alertas)
8. [Solução de Problemas](#solução-de-problemas)

## Visão Geral

O Doctoralia Scrapper oferece um conjunto completo de workflows n8n para automatizar o monitoramento e análise de perfis médicos. Os workflows são projetados para trabalhar em conjunto, oferecendo desde processamento simples até operações em lote complexas.

## Workflows Disponíveis

### 1. 🏥 Complete Doctoralia Workflow

**Arquivo:** `complete-doctoralia-workflow.json`

O workflow principal e mais completo, oferecendo:

- **3 tipos de triggers:** Manual, Webhook, Schedule (6h)
- **Processamento assíncrono** com retry automático
- **Análise de sentimento** com VADER
- **Múltiplos canais de notificação:** Telegram, Email, Slack
- **Armazenamento de dados:** Google Sheets, Notion
- **Sistema de alertas** para avaliações negativas
- **Tratamento de erros** robusto

**Casos de Uso:**

- Monitoramento contínuo de múltiplos médicos
- Análise detalhada de reputação
- Alertas em tempo real para problemas

### 2. 📦 Batch Processing Workflow

**Arquivo:** `batch-processing-workflow.json`

Workflow otimizado para processamento em lote:

- **Leitura de lista** do Google Sheets
- **Filtragem inteligente** por última verificação
- **Priorização** de médicos (high/normal/low)
- **Rate limiting** automático
- **Relatório consolidado** ao final

**Casos de Uso:**

- Processamento diário de grandes listas
- Atualização periódica de banco de dados
- Relatórios gerenciais

### 3. 🔄 Sync Scraping Workflow

**Arquivo:** `sync-scraping-workflow.json`

Workflow simples e direto:

- **Processamento síncrono** rápido
- **Resposta imediata**
- **Ideal para testes**

**Casos de Uso:**

- Verificações pontuais
- Testes de integração
- Demonstrações

### 4. 🪝 Async Webhook Workflow

**Arquivo:** `async-webhook-workflow.json`

Workflow avançado com callbacks:

- **Processamento assíncrono**
- **Callbacks com assinatura HMAC**
- **Verificação de segurança**

**Casos de Uso:**

- Integração com sistemas externos
- APIs de terceiros
- Processamento em background

## Configuração Inicial

### 1. Iniciar os Serviços

```bash
# Clone o repositório
git clone <repo-url>
cd doctoralia-scrapper

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves

# Inicie os containers
docker-compose up -d

# Verifique se tudo está rodando
docker-compose ps
```

### 2. Acessar o n8n

Abra seu navegador e acesse: `http://localhost:5678`

Se configurou autenticação:

- **Usuário:** definido em N8N_BASIC_AUTH_USER
- **Senha:** definida em N8N_BASIC_AUTH_PASSWORD

## Importação dos Workflows

### Método 1: Interface Web

1. No n8n, clique em **"Workflows"** no menu lateral
2. Clique em **"Import from File"**
3. Selecione o arquivo JSON do workflow desejado
4. Clique em **"Import"**
5. O workflow será aberto automaticamente

### Método 2: Copiar e Colar

1. Abra o arquivo JSON do workflow
2. Copie todo o conteúdo
3. No n8n, crie um novo workflow
4. Pressione `Ctrl+A` e depois `Ctrl+V`
5. Os nodes serão criados automaticamente

### Método 3: API

```bash
# Importar via API
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d @examples/n8n/complete-doctoralia-workflow.json
```

## Configuração de Credenciais

### 1. Doctoralia API

No n8n, vá para **Settings > Credentials** e crie:

**Nome:** Doctoralia API
**Tipo:** Header Auth

```json
{
  "name": "X-API-Key",
  "value": "sua-api-key-aqui"
}
```

### 2. Google Sheets

**Nome:** Google Sheets
**Tipo:** Google Sheets OAuth2

- Siga o processo de autenticação OAuth2
- Ou use Service Account (recomendado para produção)

**IDs necessários:**

- `doctorsListId`: ID da planilha com lista de médicos
- `resultsSheetId`: ID da planilha para resultados

### 3. Telegram

**Nome:** Telegram Bot
**Tipo:** Telegram

```json
{
  "accessToken": "seu-bot-token",
  "chatId": "seu-chat-id",
  "alertChatId": "chat-id-para-alertas"
}
```

### 4. Email

**Nome:** Email SMTP
**Tipo:** SMTP

```json
{
  "host": "smtp.gmail.com",
  "port": 587,
  "user": "seu-email@gmail.com",
  "password": "senha-de-app",
  "from": "seu-email@gmail.com",
  "to": "destinatario@email.com"
}
```

### 5. Notion

**Nome:** Notion Integration
**Tipo:** Notion

- Crie uma integração no Notion
- Copie o token de integração
- Configure o `databaseId` do banco de dados

### 6. Slack

**Nome:** Slack Workspace
**Tipo:** Slack OAuth2

- Configure OAuth2 ou use Webhook URL
- Defina o `channel` padrão

## Personalização

### Ajustar Frequência de Execução

No node **"Schedule 6h"**:

```javascript
// Alterar para executar a cada 1 hora
"interval": [
  {
    "field": "hours",
    "hoursInterval": 1
  }
]

// Ou para horários específicos
"cronExpression": "0 9,15,21 * * *"  // 9h, 15h e 21h
```

### Modificar Lista de URLs

No node **"Configuration"**:

```javascript
"doctor_urls": [
  "https://www.doctoralia.com.br/medico/seu-medico-1",
  "https://www.doctoralia.com.br/medico/seu-medico-2"
]
```

### Personalizar Mensagens

No node **"Format Telegram Report"**:

```javascript
// Adicione emojis e formatação personalizada
let report = `🏥 *Clínica XYZ - Relatório*\n`;
report += `📅 Data: ${new Date().toLocaleDateString('pt-BR')}\n`;
// ... resto do relatório
```

### Ajustar Condições de Alerta

No node **"Check Alert Condition"**:

```javascript
// Modificar limites de alerta
"conditions": {
  "number": [
    {
      "value1": "={{$json.metrics.sentiment_compound}}",
      "operation": "smaller",
      "value2": -0.5  // Mais restritivo
    }
  ],
  "boolean": [
    {
      "value1": "={{$json.metrics.doctor_rating < 2.5}}",  // Ajustado
      "value2": true
    }
  ]
}
```

### Adicionar Novos Destinos

Para adicionar um novo destino de dados:

1. Adicione um novo node após **"Process Results"**
2. Configure as credenciais necessárias
3. Conecte ao node **"Continue"**

Exemplo para Airtable:

```javascript
{
  "type": "n8n-nodes-base.airtable",
  "operation": "append",
  "baseId": "seu-base-id",
  "tableId": "seu-table-id"
}
```

## Monitoramento e Alertas

### Dashboard de Monitoramento

Crie um dashboard usando os dados salvos:

1. **Google Data Studio**: Conecte ao Google Sheets
2. **Metabase**: Conecte ao banco de dados
3. **Grafana**: Use o plugin JSON para API

### Configurar Alertas Avançados

```javascript
// Node Function para alertas customizados
const metrics = $json.metrics;

// Alerta para queda brusca de avaliação
if (metrics.rating_change < -1.0) {
  $node.send('urgent-alert-channel', {
    severity: 'high',
    message: `⚠️ Queda brusca na avaliação: ${metrics.rating_change}`
  });
}

// Alerta para volume anormal de reviews negativos
if (metrics.negative_reviews_ratio > 0.3) {
  $node.send('manager-notification', {
    action_required: true,
    doctor: metrics.doctor_name
  });
}
```

### Integração com PagerDuty/Opsgenie

Para alertas críticos, adicione integração:

```javascript
{
  "type": "n8n-nodes-base.httpRequest",
  "method": "POST",
  "url": "https://api.pagerduty.com/incidents",
  "headers": {
    "Authorization": "Token token={{$credentials.pagerduty.token}}"
  },
  "body": {
    "incident": {
      "type": "incident",
      "title": "Alerta Crítico Doctoralia",
      "service": {
        "id": "service-id",
        "type": "service_reference"
      },
      "body": {
        "type": "incident_body",
        "details": "{{$json.alert_details}}"
      }
    }
  }
}
```

## Solução de Problemas

### Erro: "Connection Refused"

**Causa:** Serviços não estão rodando
**Solução:**

```bash
docker-compose up -d
docker-compose ps
docker-compose logs api
```

### Erro: "Rate Limit Exceeded"

**Causa:** Muitas requisições em pouco tempo
**Solução:**

- Aumente o delay no node **"Wait"**
- Reduza o `batchSize` no **"Split in Batches"**
- Configure rate limiting no API

### Erro: "Timeout"

**Causa:** Processamento demorado
**Solução:**

```javascript
// Aumente o timeout no HTTP Request
"options": {
  "timeout": 60000  // 60 segundos
}
```

### Erro: "Invalid API Key"

**Causa:** Credenciais incorretas
**Solução:**

1. Verifique o valor em `.env`
2. Recrie a credencial no n8n
3. Teste com `curl` direto

### Workflow Não Executa

**Checklist:**

- [ ] Workflow está ativo (toggle no canto superior direito)
- [ ] Triggers estão configurados corretamente
- [ ] Credenciais estão válidas
- [ ] Não há erros nos nodes Function
- [ ] Logs do n8n: `docker-compose logs n8n`

### Debug de Dados

Para debugar o fluxo de dados:

1. Adicione nodes **"Set"** entre os steps
2. Use `console.log()` nos Function nodes
3. Ative **"Save Execution Data"** nas settings
4. Use o modo **"Test Workflow"**

### Performance

Para melhorar a performance:

1. **Use cache:** Adicione Redis cache
2. **Paralelização:** Use múltiplos workers
3. **Batch otimizado:** Ajuste `batchSize` baseado em testes
4. **Async sempre que possível:** Prefira jobs assíncronos

## Exemplos de Uso Avançado

### 1. Comparação Temporal

```javascript
// Compare com dados históricos
const current = $json;
const historical = await $node.getHistoricalData(doctor_id, 30); // últimos 30 dias

const trend = {
  rating_trend: current.rating - historical.avg_rating,
  sentiment_trend: current.sentiment - historical.avg_sentiment,
  review_velocity: current.review_count / historical.days
};

return { json: { ...current, trend } };
```

### 2. Análise Competitiva

```javascript
// Compare múltiplos médicos da mesma especialidade
const doctors = $items();
const specialty = doctors[0].json.specialty;

const benchmark = {
  avg_rating: doctors.reduce((sum, d) => sum + d.json.rating, 0) / doctors.length,
  best_performer: doctors.sort((a, b) => b.json.rating - a.json.rating)[0],
  market_position: doctors.findIndex(d => d.json.id === target_id) + 1
};
```

### 3. Predição com ML

```javascript
// Integre com serviço de ML para predições
const prediction = await $http.post('https://ml-api/predict', {
  historical_data: $json.historical,
  current_metrics: $json.metrics
});

if (prediction.churn_risk > 0.7) {
  // Trigger ação preventiva
  $node.send('retention-workflow', {
    doctor_id: $json.doctor.id,
    risk_score: prediction.churn_risk,
    recommended_actions: prediction.actions
  });
}
```

## Recursos Adicionais

- **Documentação n8n:** <https://docs.n8n.io>
- **API Doctoralia Scrapper:** <http://localhost:8000/docs>
- **Suporte:** Crie uma issue no GitHub
- **Comunidade:** Discord do n8n

## Conclusão

Os workflows fornecidos cobrem a maioria dos casos de uso para monitoramento de perfis no Doctoralia. Personalize conforme suas necessidades específicas e não hesite em criar novos workflows combinando os nodes existentes.

**Dicas Finais:**

- Sempre teste em ambiente de desenvolvimento primeiro
- Mantenha backups dos workflows importantes
- Documente suas personalizações
- Monitore os logs regularmente
- Atualize as credenciais periodicamente
