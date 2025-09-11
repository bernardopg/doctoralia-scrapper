# n8n Integration Guide for Doctoralia Scrapper

This guide explains how to integrate the Doctoralia Scrapper API with n8n workflows.

## Table of Contents

1. [Quick Start](#quick-start)
2. [API Authentication](#api-authentication)
3. [Available Endpoints](#available-endpoints)
4. [n8n Workflow Examples](#n8n-workflow-examples)
5. [Webhook Security](#webhook-security)
6. [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Start the services

```bash
# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker-compose up -d

# Services will be available at:
# - API: http://localhost:8000
# - n8n: http://localhost:5678
# - API Docs: http://localhost:8000/docs
```

### 2. Test the API

```bash
# Health check
curl http://localhost:8000/v1/health

# Test scraping (replace YOUR_API_KEY)
curl -X POST http://localhost:8000/v1/scrape:run \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/example",
    "include_analysis": true
  }'
```

## API Authentication

All API endpoints (except health checks) require authentication via API key.

### Setting up authentication in n8n

1. **HTTP Request Node Configuration:**
   - Add a header: `X-API-Key: YOUR_API_KEY`
   - Or use Bearer token: `Authorization: Bearer YOUR_API_KEY`

2. **Using n8n Credentials:**
   - Create a new credential of type "Header Auth"
   - Name: `X-API-Key`
   - Value: Your API key

## Available Endpoints

### 1. Synchronous Scraping

**Endpoint:** `POST /v1/scrape:run`

Perfect for simple workflows where you want immediate results.

**Request Body:**
```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/example",
  "include_analysis": true,
  "include_generation": false,
  "language": "pt"
}
```

**Response:**
```json
{
  "doctor": {
    "id": "abc123",
    "name": "Dr. Example",
    "specialty": "Cardiologist",
    "rating": 4.5
  },
  "reviews": [...],
  "analysis": {
    "summary": "Analyzed 10 reviews",
    "sentiments": {
      "compound": 0.85,
      "positive": 0.75,
      "neutral": 0.20,
      "negative": 0.05
    }
  },
  "status": "completed"
}
```

### 2. Asynchronous Jobs

**Create Job:** `POST /v1/jobs`

For long-running scraping tasks with callback support.

**Request Body:**
```json
{
  "doctor_url": "https://www.doctoralia.com.br/medico/example",
  "include_analysis": true,
  "include_generation": true,
  "callback_url": "https://your-n8n-instance.com/webhook/abc123",
  "mode": "async"
}
```

**Check Status:** `GET /v1/jobs/{job_id}`

### 3. Webhook Endpoint

**Endpoint:** `POST /v1/hooks/n8n/scrape`

Designed specifically for n8n webhook triggers.

## n8n Workflow Examples

### Example 1: Simple Synchronous Scraping

```json
{
  "name": "Doctoralia Simple Scrape",
  "nodes": [
    {
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "position": [250, 300]
    },
    {
      "name": "Scrape Doctor",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "method": "POST",
        "url": "http://api:8000/v1/scrape:run",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-API-Key",
              "value": "YOUR_API_KEY"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "doctor_url",
              "value": "https://www.doctoralia.com.br/medico/example"
            },
            {
              "name": "include_analysis",
              "value": true
            }
          ]
        }
      }
    },
    {
      "name": "Send to Telegram",
      "type": "n8n-nodes-base.telegram",
      "position": [650, 300],
      "parameters": {
        "text": "Doctor: {{$json.doctor.name}}\nRating: {{$json.doctor.rating}}\nReviews: {{$json.metrics.scraped_count}}",
        "chatId": "YOUR_CHAT_ID"
      }
    }
  ]
}
```

### Example 2: Async with Polling

```json
{
  "name": "Doctoralia Async Polling",
  "nodes": [
    {
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "position": [250, 300]
    },
    {
      "name": "Create Job",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "method": "POST",
        "url": "http://api:8000/v1/jobs",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-API-Key",
              "value": "YOUR_API_KEY"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "doctor_url",
              "value": "https://www.doctoralia.com.br/medico/example"
            },
            {
              "name": "include_analysis",
              "value": true
            },
            {
              "name": "mode",
              "value": "async"
            }
          ]
        }
      }
    },
    {
      "name": "Wait",
      "type": "n8n-nodes-base.wait",
      "position": [650, 300],
      "parameters": {
        "amount": 5,
        "unit": "seconds"
      }
    },
    {
      "name": "Check Status",
      "type": "n8n-nodes-base.httpRequest",
      "position": [850, 300],
      "parameters": {
        "method": "GET",
        "url": "=http://api:8000/v1/jobs/{{$node[\"Create Job\"].json[\"job_id\"]}}",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-API-Key",
              "value": "YOUR_API_KEY"
            }
          ]
        }
      }
    },
    {
      "name": "Check Complete",
      "type": "n8n-nodes-base.if",
      "position": [1050, 300],
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.status}}",
              "value2": "completed"
            }
          ]
        }
      }
    }
  ]
}
```

### Example 3: Webhook Callback Pattern

```json
{
  "name": "Doctoralia Webhook Callback",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "webhookId": "abc123",
      "parameters": {
        "path": "doctoralia-callback",
        "responseMode": "onReceived",
        "responseData": "firstEntryJson"
      }
    },
    {
      "name": "Create Async Job",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "method": "POST",
        "url": "http://api:8000/v1/jobs",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-API-Key",
              "value": "YOUR_API_KEY"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "doctor_url",
              "value": "={{$json.doctor_url}}"
            },
            {
              "name": "callback_url",
              "value": "={{$node.Webhook.json[\"webhookUrl\"]}}"
            },
            {
              "name": "include_analysis",
              "value": true
            },
            {
              "name": "mode",
              "value": "async"
            }
          ]
        }
      }
    },
    {
      "name": "Process Results",
      "type": "n8n-nodes-base.function",
      "position": [650, 500],
      "parameters": {
        "functionCode": "// Results from callback\nconst doctor = items[0].json.doctor;\nconst reviews = items[0].json.reviews;\nconst analysis = items[0].json.analysis;\n\nreturn {\n  doctor_name: doctor.name,\n  total_reviews: reviews.length,\n  sentiment_score: analysis?.sentiments?.compound || 0\n};"
      }
    }
  ]
}
```

## Webhook Security

### Verifying Webhook Signatures

When receiving callbacks, you can verify the signature:

```javascript
// n8n Function Node
const crypto = require('crypto');

const secret = 'YOUR_WEBHOOK_SECRET';
const timestamp = $headers['x-timestamp'];
const signature = $headers['x-signature'];
const body = JSON.stringify($input.all()[0].json);

// Calculate expected signature
const message = `${timestamp}.${body}`;
const expectedSig = 'sha256=' + crypto
  .createHmac('sha256', secret)
  .update(message)
  .digest('hex');

// Verify
if (signature !== expectedSig) {
  throw new Error('Invalid signature');
}

return items;
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure all services are running: `docker-compose ps`
   - Check service logs: `docker-compose logs api`

2. **Authentication Failed**
   - Verify API key is set correctly in `.env`
   - Check header format: `X-API-Key: YOUR_KEY`

3. **Timeout Errors**
   - Increase timeout in n8n HTTP Request node
   - Use async endpoints for long-running tasks

4. **Job Not Found**
   - Jobs expire after 1 hour by default
   - Check Redis is running: `docker-compose logs redis`

### Debug Mode

Enable debug logging:
```bash
DEBUG=true docker-compose up api
```

### Health Checks

```bash
# API health
curl http://localhost:8000/v1/health

# Readiness (checks all dependencies)
curl http://localhost:8000/v1/ready
```

## Best Practices

1. **Use Async for Large Jobs**
   - Sync endpoint has 30s timeout
   - Async jobs can run up to 30 minutes

2. **Implement Retry Logic**
   - Use n8n's built-in retry on fail
   - Set exponential backoff for webhooks

3. **Monitor Job Status**
   - Poll `/v1/jobs/{id}` every 5-10 seconds
   - Or use webhook callbacks for real-time updates

4. **Rate Limiting**
   - Default: 10 requests per minute
   - Implement delays in n8n workflows

5. **Error Handling**
   - Always check `status` field in responses
   - Log errors for debugging
