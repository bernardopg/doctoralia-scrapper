# Multi-stage Dockerfile for Doctoralia Scrapper with n8n integration
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-optimized.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir redis rq

# Copy application code
COPY src ./src
COPY config ./config
COPY templates ./templates

# Create necessary directories
RUN mkdir -p logs

# API service (default)
FROM base AS api
CMD ["uvicorn", "src.api.v1.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Worker service
FROM base AS worker
CMD ["rq", "worker", "-u", "${REDIS_URL:-redis://redis:6379/0}", "doctoralia"]
