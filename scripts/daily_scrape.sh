#!/bin/bash

# Daily scraping script for Doctoralia
# This script activates the virtual environment and runs the scraper with the specific URL

# Set strict error handling
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Log file for daily scraping
LOG_FILE="$PROJECT_DIR/logs/daily_scrape.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Function to log messages
log_message() {
    echo "[$DATE] $1" | tee -a "$LOG_FILE"
}

log_message "Starting daily scraping for Dr. Bruna Pinto Gomes"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    log_message "Virtual environment activated"
else
    log_message "ERROR: Virtual environment not found at venv/bin/activate"
    exit 1
fi

# Set the target URL
TARGET_URL="https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"

# Run the scraper
log_message "Running scraper for URL: $TARGET_URL"

if python3 main.py scrape --url "$TARGET_URL"; then
    log_message "✅ Daily scraping completed successfully"
else
    log_message "❌ Daily scraping failed with exit code $?"
    exit 1
fi

log_message "Daily scraping script finished"
