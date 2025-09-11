# 🔗 Doctoralia Scrapper - n8n Integration

## Overview

The Doctoralia Scrapper has been enhanced with n8n integration capabilities, allowing you to easily incorporate medical review scraping and analysis into your n8n workflows.

## Key Features

### 🚀 API Endpoints
- **Synchronous Scraping** (`POST /v1/scrape:run`) - Get immediate results
- **Asynchronous Jobs** (`POST /v1/jobs`) - Queue long-running tasks
- **Job Status** (`GET /v1/jobs/{id}`) - Check job progress
- **Webhook Support** (`POST /v1/hooks/n8n/scrape`) - Trigger from n8n webhooks
- **Health Monitoring** (`GET /v1/health`, `/v1/ready`) - Service status

### 🔒 Security
- API Key authentication
- HMAC webhook signature verification
- Request ID tracking
- Secure callback signing

### 📊 Data Processing
- Selenium-based web scraping
- VADER sentiment analysis
- AI response generation
- Telegram notifications
- Unified JSON responses optimized for n8n

## Quick Start

### 1. Setup

```bash
# Clone the repository
git clone <repository-url>
cd doctoralia-scrapper

# Checkout n8n integration branch
git checkout feat/n8n-integration

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start services
docker-compose up -d
```

### 2. Access Services

- **API Documentation**: http://localhost:8000/docs
- **n8n Interface**: http://localhost:5678
- **API Base URL**: http://localhost:8000

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/v1/health

# Scrape a doctor profile
curl -X POST http://localhost:8000/v1/scrape:run \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/example",
    "include_analysis": true
  }'
```

## n8n Integration Examples

### Simple Synchronous Workflow

1. Open n8n (http://localhost:5678)
2. Create a new workflow
3. Add nodes:
   - **Manual Trigger** - Start the workflow
   - **HTTP Request** - Call the scraping API
   - **Set** - Process the results
   - **Telegram/Email** - Send notifications

### Async with Webhooks

1. Create a webhook node to receive results
2. Call `/v1/jobs` with the webhook URL
3. Process results when they arrive

## API Response Format

All endpoints return a unified JSON structure:

```json
{
  "doctor": {
    "id": "abc123",
    "name": "Dr. John Doe",
    "specialty": "Cardiology",
    "rating": 4.5,
    "profile_url": "https://..."
  },
  "reviews": [
    {
      "id": "rev1",
      "date": "2024-01-15",
      "rating": 5,
      "text": "Excellent doctor!",
      "author": {
        "name": "Patient Name",
        "is_verified": true
      }
    }
  ],
  "analysis": {
    "summary": "Analyzed 25 reviews",
    "sentiments": {
      "compound": 0.85,
      "positive": 0.75,
      "neutral": 0.20,
      "negative": 0.05
    },
    "quality_score": 85.0
  },
  "metrics": {
    "scraped_count": 25,
    "duration_ms": 3500,
    "source": "doctoralia"
  },
  "status": "completed"
}
```

## Environment Variables

```env
# API Configuration
API_KEY=your-secure-api-key
WEBHOOK_SIGNING_SECRET=your-webhook-secret

# Redis (for async jobs)
REDIS_URL=redis://redis:6379/0

# Selenium
SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub

# Optional Services
TELEGRAM_TOKEN=your-telegram-token
TELEGRAM_CHAT_ID=your-chat-id
OPENAI_API_KEY=your-openai-key

# n8n Auth (optional)
N8N_BASIC_AUTH_ACTIVE=false
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=password
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│     n8n     │────▶│   API v1    │────▶│   Scraper   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐     ┌─────────────┐
                    │    Redis    │     │  Selenium   │
                    │   (Queue)   │     │  (Browser)  │
                    └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Worker    │
                    │  (RQ Jobs)  │
                    └─────────────┘
```

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run API
uvicorn src.api.v1.main:app --reload

# Run worker
rq worker -u redis://localhost:6379/0 doctoralia

# Run tests
pytest tests/
```

### Adding New Features

1. Create schemas in `src/api/schemas/`
2. Add endpoints in `src/api/v1/main.py`
3. Implement logic in `src/integrations/n8n/`
4. Update documentation

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   docker-compose ps  # Check services
   docker-compose logs api  # View logs
   ```

2. **Authentication Failed**
   - Verify API_KEY in .env
   - Check header: `X-API-Key: your-key`

3. **Job Not Found**
   - Jobs expire after 1 hour
   - Check Redis: `docker-compose logs redis`

### Debug Mode

```bash
DEBUG=true docker-compose up api
```

## Support

For issues or questions:
1. Check the [documentation](docs/n8n-integration.md)
2. Review [API docs](http://localhost:8000/docs)
3. Open an issue on GitHub

## License

Proprietary - See LICENSE file

## Credits

Built with:
- FastAPI for the REST API
- n8n for workflow automation
- Selenium for web scraping
- Redis/RQ for job queuing
- Docker for containerization
