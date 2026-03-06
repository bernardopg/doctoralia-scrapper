#!/bin/bash

# Worker entrypoint script for RQ (Redis Queue) worker
# Starts the RQ worker with proper signal handling and error checking

set -e

# Load environment variables from .env if it exists (for local development)
# shellcheck source=.env
if [[ -f .env ]]; then
    set -a; . ./.env; set +a
fi

# Validate required environment variables
REQUIRED_VARS=("REDIS_URL")
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "ERROR: Required environment variable '${var}' is not set"
        exit 1
    fi
done

# Debug: Print startup info
echo "Starting RQ worker..."
echo "Redis URL: ${REDIS_URL}"
python_version=$(python --version)
echo "Python version: ${python_version}"
echo ""

# Start RQ worker with optimized settings
# --results-ttl: Time to keep successful job results (24 hours)
exec rq worker \
--results-ttl=86400 \
-u "${REDIS_URL}" \
--with-scheduler \
doctoralia
