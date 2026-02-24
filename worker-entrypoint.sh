#!/bin/bash

# Worker entrypoint script for RQ (Redis Queue) worker
# Starts the RQ worker with proper signal handling and error checking

set -e

# Load environment variables from .env if it exists (for local development)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Validate required environment variables
REQUIRED_VARS=("REDIS_URL")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: Required environment variable '$var' is not set"
        exit 1
    fi
done

# Debug: Print startup info
echo "Starting RQ worker..."
echo "Redis URL: ${REDIS_URL}"
echo "Python version: $(python --version)"
echo ""

# Start RQ worker with optimized settings
# --job-timeout: Timeout for individual jobs (30 minutes)
# --results-ttl: Time to keep successful job results (24 hours)
# --failure-ttl: Time to keep failed job results (7 days)
exec rq worker \
--job-timeout=1800 \
--results-ttl=86400 \
--failure-ttl=604800 \
-u "${REDIS_URL}" \
--with-scheduler \
--scheduler-interval=60 \
doctoralia
