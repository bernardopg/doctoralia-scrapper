# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Doctoralia Scrapper is a professional automation system for monitoring, analyzing, and responding to medical reviews from Doctoralia (and future sources).
It features resilient web scraping, AI-powered response generation, REST API, n8n integration, and observability.

**Tech Stack**: Python 3.10+, FastAPI, Selenium, Redis/RQ (job queue), Flask (dashboard), BeautifulSoup, n8n integration

## Essential Commands

### Development Setup
```bash
make venv              # Create .venv with Poetry, install deps, export requirements.txt
make install           # Install production deps (pip-based)
make install-dev       # Install dev deps + tools (pytest, black, mypy, etc)
make setup             # Initial project setup (create dirs, validate config)
```

### Testing & Quality
```bash
make test              # Run full test suite with coverage
make test-html         # Run tests with HTML coverage report
make lint              # Format (black+isort) + lint (flake8, pylint, mypy) + security (bandit, safety)
make format            # Only run black + isort
make security          # Only run bandit + safety checks
make ci                # CI/CD checks (format check + lint + test)
```

### Running Scraper
```bash
make run-url URL=<doctor_url>           # Quick scraping only
make run-full-url URL=<doctor_url>      # Scraping + generation + analysis
make analyze                            # Interactive quality analysis
make daemon                             # Continuous scheduled scraping loop
make daemon-debug                       # Daemon in debug mode (5s interval)
```

### Services
```bash
make api               # Start FastAPI REST API (localhost:8000)
make api-docs          # Open API docs in browser (/docs endpoint)
make dashboard         # Start Flask dashboard (localhost:5000)
make monitor           # Start system/scraping monitor
make status            # Show system diagnostic
```

### Docker
```bash
docker-compose up -d   # Start all services (api, worker, redis, selenium, n8n)
docker-compose logs -f api      # Follow API logs
docker-compose logs -f worker   # Follow worker logs
```

### Utilities
```bash
make health            # System health check
make diagnostic        # Full system diagnostic
make clean             # Remove temp files, cache, coverage reports
make info              # Environment info (Python, Git, system)
```

## Architecture Overview

### Core Components

**Entry Points**:
- `main.py` - CLI interface for all operations (scrape, generate, analyze, daemon, api, dashboard)
- `src/api/v1/main.py` - FastAPI application (REST endpoints)
- `src/dashboard.py` - Flask dashboard for monitoring
- `scripts/daemon.py` - Scheduled continuous scraping controller

**Scraping Layer**:
- `src/scraper.py` - Base `DoctoraliaScraper` class (Selenium-based scraping)
- `src/enhanced_scraper.py` - Enhanced scraper with circuit breaker pattern
- `src/multi_site_scraper.py` - Multi-platform adapter (Doctoralia + extensible)
- `src/circuit_breaker.py` - Circuit breaker for fault tolerance
- `src/error_handling.py` - Custom exceptions (ScrapingError, RateLimitError, PageNotFoundError) + retry decorators

**Intelligence Layer**:
- `src/response_generator.py` - AI response generation with templates
- `src/response_quality_analyzer.py` - Sentiment analysis, quality scoring, response validation

**API & Integration**:
- `src/api/v1/main.py` - FastAPI app with endpoints: `/v1/scrape:run`, `/v1/jobs`, `/v1/jobs/{job_id}`, `/v1/hooks/n8n/scrape`, `/v1/health`, `/v1/ready`, `/v1/metrics`, `/v1/version`
- `src/api/v1/deps.py` - API key auth, webhook signature verification
- `src/api/schemas/` - Pydantic models for requests/responses
- `src/integrations/n8n/normalize.py` - n8n-compatible result normalization
- `src/jobs/queue.py` - Redis + RQ job queue interface
- `src/jobs/tasks.py` - Background tasks (scrape_and_process)

**Infrastructure**:
- `src/health_checker.py` - Async health checks (Selenium, Redis)
- `src/performance_monitor.py` - Metrics collection (latency, success rate)
- `src/logger.py` - Structured logging
- `src/telegram_notifier.py` - Telegram notifications
- `src/secure_config.py` - Configuration with PII masking

### Data Flow

1. **Synchronous API**: User → FastAPI → Scraper → Response (direct)
2. **Async API**: User → FastAPI → Redis Queue → Worker → Webhook callback
3. **n8n Integration**: n8n → API endpoint → Job → Webhook → n8n workflow
4. **Scheduled**: Daemon → Scraper → Generator → Analyzer → Storage/Notification

### Configuration

**Config Files**:
- `config/config.json` - Main configuration (scraping params, delays, telegram settings)
- `config/config.example.json` - Example template
- `.env` - Secrets (API_KEY, WEBHOOK_SIGNING_SECRET, TELEGRAM_TOKEN, OPENAI_API_KEY, REDIS_URL, SELENIUM_REMOTE_URL)
- `.env.example` - Template for environment variables

**Settings Module**: `config/settings.py` (AppConfig class) loads and validates configuration

### Important Patterns

**Circuit Breaker**: Used in `enhanced_scraper.py` to prevent cascading failures. Monitors failure threshold and opens circuit to prevent repeated failing calls.

**Retry with Backoff**: Decorator in `error_handling.py` for automatic retries with exponential backoff (configurable max retries, backoff multiplier).

**Job Queue**: RQ (Redis Queue) for async processing. Jobs tracked with status (queued, started, finished, failed).

**Error Handling Hierarchy**:
- `ScrapingError` (base, with retryable flag + context)
  - `RateLimitError` (retryable)
  - `PageNotFoundError` (non-retryable)
  - `SessionExpiredError`
  - `InvalidSelectorError`

**API Security**:
- X-API-Key header authentication (via `require_api_key` dependency)
- HMAC-SHA256 webhook signature verification (X-Webhook-Signature)
- PII masking in logs when `MASK_PII=true`

## Testing Strategy

**Test Organization**:
- `tests/test_scraper.py` - Core scraping logic
- `tests/test_response_generator.py` - Response generation
- `tests/test_api.py` - API endpoints (if exists)
- `tests/test_circuit_breaker.py` - Circuit breaker behavior
- `tests/test_error_handling.py` - Exception handling
- `tests/fixtures/` - Shared test fixtures

**Run Single Test**:
```bash
pytest tests/test_scraper.py::TestClass::test_method -v
pytest tests/test_scraper.py -k "test_method_name" -v
```

**Coverage Target**: ≥85% (as noted in README badge)

## Development Guidelines

**Code Style**:
- Black formatting (88 char line length)
- isort for import sorting (black profile)
- Type hints required (mypy strict mode)
- Docstrings for all public functions/classes

**Adding New Scraping Platform**:
1. Create adapter in `src/multi_site_scraper.py`
2. Implement platform-specific selectors
3. Add platform detection logic
4. Update tests in `tests/test_multi_site_scraper.py`

**Adding New API Endpoint**:
1. Add route in `src/api/v1/main.py`
2. Define schemas in `src/api/schemas/`
3. Add dependency injection in `src/api/v1/deps.py` if needed
4. Update OpenAPI docs (automatic via FastAPI)
5. Add tests

**Extending Response Templates**:
- Edit `config/templates.py` or JSON templates in `config/`
- Templates support variables: `{doctor_name}`, `{review_text}`, `{sentiment}`, etc.
- See `docs/templates.md` for full documentation

## Common Issues & Solutions

**Selenium Connection Errors**:
- Check `SELENIUM_REMOTE_URL` in `.env`
- Ensure selenium container is running: `docker-compose ps selenium`
- VNC debug: Connect to `localhost:7900` (see docker-compose.yml)

**Rate Limiting**:
- Adjust delays in `config/config.json` → `scraping.delays`
- Circuit breaker will auto-open after 3 consecutive failures (30s timeout)
- Use `retry_with_backoff` decorator for transient failures

**Job Queue Issues**:
- Check Redis connection: `redis-cli -u $REDIS_URL ping`
- View queue status: `make status` or API endpoint `/v1/jobs/status`
- Failed jobs stored with error details in Redis

**Webhook Signature Mismatch**:
- Verify `WEBHOOK_SIGNING_SECRET` matches between API and n8n
- Signature format: `HMAC-SHA256(secret, request_body)`
- Header: `X-Webhook-Signature: sha256=<hex_digest>`

## Project Structure Reference

```
├── main.py                    # CLI entrypoint
├── src/
│   ├── scraper.py            # Base scraper (Selenium)
│   ├── enhanced_scraper.py   # + circuit breaker
│   ├── multi_site_scraper.py # Multi-platform support
│   ├── response_generator.py # AI response generation
│   ├── response_quality_analyzer.py  # Sentiment & quality
│   ├── api/
│   │   └── v1/
│   │       ├── main.py       # FastAPI app
│   │       ├── deps.py       # Auth dependencies
│   │       └── schemas/      # Pydantic models
│   ├── jobs/
│   │   ├── queue.py          # RQ interface
│   │   └── tasks.py          # Background tasks
│   ├── integrations/n8n/     # n8n normalization
│   └── telegram_notifier.py  # Notifications
├── config/
│   ├── config.json           # Main config
│   └── templates.py          # Response templates
├── scripts/
│   ├── daemon.py             # Scheduled scraping
│   ├── system_diagnostic.py  # System health
│   └── monitor_scraping.py   # Monitoring
├── tests/                    # Test suite
├── data/                     # Output (logs, extractions, responses)
├── docs/                     # Detailed documentation
└── examples/n8n/             # n8n workflow examples
```

## Deployment Notes

**Docker Production**:
- Multi-stage Dockerfile with `api` and `worker` targets
- Services: api, worker, redis, selenium, n8n
- Health checks: `/health` (API), Redis PING, Selenium status
- Ports: 8000 (API), 5678 (n8n), 6379 (Redis), 4444/7900 (Selenium)

**Environment Variables** (production critical):
- `API_KEY` - Strong random key for API auth
- `WEBHOOK_SIGNING_SECRET` - HMAC secret for webhook validation
- `REDIS_URL` - Redis connection string
- `SELENIUM_REMOTE_URL` - Selenium Grid endpoint

**Monitoring**:
- Metrics endpoint: `/v1/metrics` (requests, errors, durations)
- Dashboard: Flask app at port 5000
- Health check: `/health` (service status)
- Logs: `data/logs/` directory (structured JSON)

## Additional Resources

- Full architecture: `docs/overview.md`
- API reference: `docs/api.md`
- n8n workflows: `docs/n8n.md` + `examples/n8n/`
- Deployment guide: `docs/deployment.md`
- Operations runbook: `docs/operations.md`
- Changelog: `docs/changelog.md`
