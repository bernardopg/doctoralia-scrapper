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

# Worker runtime settings (explicit defaults for predictable behavior)
RQ_JOB_TIMEOUT="${RQ_JOB_TIMEOUT:-1800}"
RQ_RESULTS_TTL="${RQ_RESULTS_TTL:-86400}"
RQ_FAILURE_TTL="${RQ_FAILURE_TTL:-604800}"
RQ_SCHEDULER_INTERVAL="${RQ_SCHEDULER_INTERVAL:-60}"

# Start RQ worker with optimized settings
# --job-timeout: Timeout for individual jobs (30 minutes)
# --results-ttl: Time to keep successful job results (24 hours)
# --failure-ttl: Time to keep failed job results (7 days)
exec rq worker \
--job-timeout="${RQ_JOB_TIMEOUT}" \
--results-ttl="${RQ_RESULTS_TTL}" \
--failure-ttl="${RQ_FAILURE_TTL}" \
-u "${REDIS_URL}" \
--with-scheduler \
--scheduler-interval="${RQ_SCHEDULER_INTERVAL}" \
doctoralia
