# Multi-stage Dockerfile for Doctoralia Scrapper with n8n integration
FROM python:3.14-slim AS builder

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
    git \
    libpq-dev \
    && git config --global url."https://github.com/".insteadOf git@github.com: \
    && git config --global http.lowSpeedLimit 1000 \
    && git config --global http.lowSpeedTime 30 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build wheels once to keep the final image smaller and with fewer OS packages.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-index /wheels/*.whl && \
    rm -rf /wheels

COPY src ./src
COPY templates ./templates

# Create necessary directories
RUN mkdir -p data/logs data/responses data/temp logs

# Pre-download NLTK data to avoid runtime network calls and slow startup
RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Install curl for health checks and apply OS security patches (fixes libcap2, libsystemd0)
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
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
# Use start_dashboard() which runs without debug mode
CMD ["python", "-c", "from src.dashboard import start_dashboard; start_dashboard(host='0.0.0.0')"]

# Test runner with dev-only dependencies.
FROM base AS test
COPY main.py ./
COPY scripts ./scripts
COPY tests ./tests
RUN pip install --no-cache-dir \
    "pytest>=9.1.0" \
    "pytest-asyncio>=1.4.0" \
    "pytest-cov>=7.1.0" \
    "pytest-mock>=3.15.1" \
    "httpx2>=2.4.0"
CMD ["python", "-m", "pytest", "tests"]
