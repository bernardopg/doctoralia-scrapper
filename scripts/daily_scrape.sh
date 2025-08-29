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
LOG_FILE="$PROJECT_DIR/data/logs/daily_scrape.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/data/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

# Function to log messages
log_message() {
    echo "[$DATE] $1" | tee -a "$LOG_FILE"
}

# Function to cleanup on exit
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_message "Script failed with exit code $exit_code"
        print_error "Daily scraping failed - check logs at $LOG_FILE"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

print_info "Starting daily scraping for Dr. Bruna Pinto Gomes"
log_message "Starting daily scraping for Dr. Bruna Pinto Gomes"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    print_error "main.py not found in $PROJECT_DIR"
    log_message "ERROR: main.py not found in $PROJECT_DIR"
    exit 1
fi

# Check if virtual environment exists
if [ -f "venv/bin/activate" ]; then
    print_info "Activating virtual environment..."
    source venv/bin/activate
    log_message "Virtual environment activated"
elif [ -f ".venv/bin/activate" ]; then
    print_info "Activating virtual environment (.venv)..."
    source .venv/bin/activate
    log_message "Virtual environment activated (.venv)"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import selenium" >/dev/null 2>&1; then
    print_warning "No virtual environment found, using system Python"
    log_message "WARNING: No virtual environment found, using system Python"
else
    print_error "Virtual environment not found and system Python missing selenium"
    log_message "ERROR: Virtual environment not found at venv/bin/activate"
    exit 1
fi

# Verify Python environment
if ! python3 -c "import selenium, bs4, requests" >/dev/null 2>&1; then
    print_error "Required Python packages not found"
    log_message "ERROR: Required Python packages not found"
    exit 1
fi

# Set the target URL
TARGET_URL="https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"

print_info "Target URL: $TARGET_URL"
log_message "Running scraper for URL: $TARGET_URL"

# Run the scraper with timeout
timeout 1800 python3 main.py scrape --url "$TARGET_URL" 2>&1 | tee -a "$LOG_FILE"

# Check the exit code of the python command (not tee)
PYTHON_EXIT_CODE=${PIPESTATUS[0]}

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    print_success "Daily scraping completed successfully"
    log_message "✅ Daily scraping completed successfully"
elif [ $PYTHON_EXIT_CODE -eq 124 ]; then
    print_warning "Daily scraping timed out after 30 minutes"
    log_message "⚠️ Daily scraping timed out after 30 minutes"
    exit 1
else
    print_error "Daily scraping failed with exit code $PYTHON_EXIT_CODE"
    log_message "❌ Daily scraping failed with exit code $PYTHON_EXIT_CODE"
    exit 1
fi

print_info "Daily scraping script finished"
log_message "Daily scraping script finished"

log_message "Daily scraping script finished"
