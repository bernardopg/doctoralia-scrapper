#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SCRIPT_PATH="$SCRIPT_DIR/daily_scrape.sh"
LOG_PATH="$PROJECT_DIR/data/logs/cron.log"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/data/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                 ⏰ CRON JOB MANAGER                          ║${NC}"
    echo -e "${BLUE}║                Doctoralia Daily Scraping                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

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

validate_environment() {
    # Check if script exists and is executable
    if [ ! -f "$SCRIPT_PATH" ]; then
        print_error "Daily scraping script not found: $SCRIPT_PATH"
        return 1
    fi

    if [ ! -x "$SCRIPT_PATH" ]; then
        print_warning "Making script executable: $SCRIPT_PATH"
        chmod +x "$SCRIPT_PATH"
    fi

    # Check if we're running as a user that can use cron
    if ! crontab -l >/dev/null 2>&1; then
        print_error "Cannot access crontab. Make sure you're running as a regular user (not root)"
        return 1
    fi

    return 0
}

case "$1" in
    "status")
        print_header
        echo "📅 Current cron jobs for daily scraping:"
        echo ""

        if crontab -l 2>/dev/null | grep -q "daily_scrape.sh"; then
            print_success "Daily scraping cron job is ACTIVE"
            echo ""
            echo "📝 Current cron entries:"
            crontab -l | grep "daily_scrape.sh" | nl -v1 | sed 's/^/   /'
            echo ""
            print_info "Next scheduled run: Every day at 9:00 AM"
        else
            print_warning "No daily scraping cron job found"
            echo ""
            print_info "Use '$0 start' to add the cron job"
        fi
        ;;

    "stop")
        print_header
        echo "🛑 Removing daily scraping cron job..."
        echo ""

        if ! validate_environment; then
            exit 1
        fi

        if crontab -l 2>/dev/null | grep -q "daily_scrape.sh"; then
            crontab -l | grep -v "daily_scrape.sh" | crontab -
            print_success "Daily scraping cron job removed successfully"
        else
            print_warning "No daily scraping cron job was active"
        fi
        ;;

    "start")
        print_header
        echo "🚀 Adding daily scraping cron job (9:00 AM every day)..."
        echo ""

        if ! validate_environment; then
            exit 1
        fi

        # Remove any existing entries first
        crontab -l 2>/dev/null | grep -v "daily_scrape.sh" | crontab - >/dev/null 2>&1

        # Add new cron job
        (crontab -l 2>/dev/null | grep -v "daily_scrape.sh"; echo "0 9 * * * $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

        if [ $? -eq 0 ]; then
            print_success "Daily scraping cron job added successfully"
            echo ""
            print_info "Job will run every day at 9:00 AM"
            print_info "Logs will be saved to: $LOG_PATH"
        else
            print_error "Failed to add cron job"
            exit 1
        fi
        ;;

    "logs")
        print_header
        echo "📋 Recent cron job logs:"
        echo ""

        if [ -f "$LOG_PATH" ]; then
            echo "📄 Last 20 lines from $LOG_PATH:"
            echo ""
            tail -20 "$LOG_PATH" | sed 's/^/   /'
            echo ""
            print_info "Full log file: $LOG_PATH"
        else
            print_warning "No cron logs found at $LOG_PATH"
            echo ""
            print_info "Logs will appear here after the cron job runs"
        fi
        ;;

    "test")
        print_header
        echo "🧪 Testing daily scraping script..."
        echo ""

        if ! validate_environment; then
            exit 1
        fi

        echo "📝 Script path: $SCRIPT_PATH"
        echo "📝 Log path: $LOG_PATH"
        echo ""

        if [ -x "$SCRIPT_PATH" ]; then
            print_info "Running test execution..."
            echo ""
            "$SCRIPT_PATH"
            exit_code=$?

            echo ""
            if [ $exit_code -eq 0 ]; then
                print_success "Test completed successfully (exit code: $exit_code)"
            else
                print_error "Test failed with exit code: $exit_code"
                exit 1
            fi
        else
            print_error "Script is not executable: $SCRIPT_PATH"
            exit 1
        fi
        ;;

    "info")
        print_header
        echo "ℹ️ Cron Job Information:"
        echo ""
        echo "📁 Project Directory: $PROJECT_DIR"
        echo "📜 Script Path: $SCRIPT_PATH"
        echo "📋 Log Path: $LOG_PATH"
        echo "⏰ Schedule: Every day at 9:00 AM (0 9 * * *)"
        echo ""
        echo "🔧 Script Status:"
        if [ -f "$SCRIPT_PATH" ]; then
            print_success "Script exists"
        else
            print_error "Script not found"
        fi

        if [ -x "$SCRIPT_PATH" ]; then
            print_success "Script is executable"
        else
            print_warning "Script is not executable"
        fi

        echo ""
        echo "📊 Log Status:"
        if [ -f "$LOG_PATH" ]; then
            log_size=$(du -h "$LOG_PATH" 2>/dev/null | cut -f1)
            print_success "Log file exists (${log_size})"
        else
            print_info "Log file doesn't exist yet"
        fi
        ;;

    *)
        print_header
        echo "Usage: $0 {start|stop|status|logs|test|info}"
        echo ""
        echo "Commands:"
        echo "  start  - Add daily cron job (9:00 AM)"
        echo "  stop   - Remove daily cron job"
        echo "  status - Show current cron job status"
        echo "  logs   - Show recent cron job logs"
        echo "  test   - Test the daily scraping script manually"
        echo "  info   - Show detailed information about the setup"
        echo ""
        echo "Examples:"
        echo "  $0 start    # Add cron job"
        echo "  $0 status   # Check if active"
        echo "  $0 logs     # View recent logs"
        echo "  $0 test     # Test script manually"
        exit 1
        ;;
esac
