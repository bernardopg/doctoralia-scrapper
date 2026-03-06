# Multi-stage Dockerfile for Doctoralia Scrapper with n8n integration
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Build dependencies are only needed in the builder stage.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build wheels once to keep the final image smaller and with fewer OS packages.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

COPY src ./src
COPY config ./config
COPY templates ./templates
COPY static ./static

# Create necessary directories
RUN mkdir -p data/logs data/responses data/temp logs

# Pre-download NLTK data to avoid runtime network calls and slow startup
RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Install curl for health checks (minimal footprint)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# API service
FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1
CMD ["uvicorn", "src.api.v1.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]

# Worker service
FROM base AS worker
COPY worker-entrypoint.sh /
RUN chmod +x /worker-entrypoint.sh
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import redis, os; r=redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379/0')); r.ping()" || exit 1
CMD ["/worker-entrypoint.sh"]

# Dashboard service
FROM base AS dashboard
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1
# Use start_dashboard() which runs without debug mode (python src/dashboard.py uses debug=True)
CMD ["python", "-c", "from src.dashboard import start_dashboard; start_dashboard(host='0.0.0.0')"]
