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
RQ_RESULTS_TTL="${RQ_RESULTS_TTL:-86400}"

# Start RQ worker with CLI flags supported by the installed RQ version.
# Job timeout and failure TTL should be configured when jobs are enqueued.
exec rq worker \
--results-ttl="${RQ_RESULTS_TTL}" \
-u "${REDIS_URL}" \
--with-scheduler \
doctoralia
