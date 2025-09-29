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

# Validate HH:MM time
is_valid_time() {
    local t="$1"
    [[ "$t" =~ ^([01][0-9]|2[0-3]):([0-5][0-9])$ ]]
}

# Add cron entries for a list of times (CSV "HH:MM,HH:MM,...")
add_cron_for_times() {
    local times_csv="$1"
    local new_crons=""

    IFS=',' read -r -a times_arr <<< "$times_csv"
    if [ "${#times_arr[@]}" -eq 0 ]; then
        print_error "No valid times provided"
        return 1
    fi

    for t in "${times_arr[@]}"; do
        t="$(echo "$t" | xargs)" # trim
        if ! is_valid_time "$t"; then
            print_error "Invalid time format: '$t' (expected HH:MM, 00-23:00-59)"
            return 1
        fi
    done

    # Remove existing entries first
    crontab -l 2>/dev/null | grep -v "daily_scrape.sh" | crontab - >/dev/null 2>&1

    # Build new cron entries
    for t in "${times_arr[@]}"; do
        local hh="${t%:*}"
        local mm="${t#*:}"
        new_crons+="$mm $hh * * * $SCRIPT_PATH >> $LOG_PATH 2>&1"$'\n'
    done

    # Install
    { crontab -l 2>/dev/null | grep -v "daily_scrape.sh"; echo -n "$new_crons"; } | crontab -

    if [ $? -eq 0 ]; then
        print_success "Daily scraping cron job added successfully"
        echo ""
        print_info "Configured daily times:"
        for t in "${times_arr[@]}"; do
            echo "   • $t (local server time)"
        done
        print_info "Logs will be saved to: $LOG_PATH"
    else
        print_error "Failed to add cron job"
        return 1
    fi
}

# Add cron entry for every N minutes (*/N * * * *)
add_cron_every_minutes() {
    local n="$1"
    if ! [[ "$n" =~ ^[1-9][0-9]*$ ]]; then
        print_error "Invalid value for minutes: '$n'"
        return 1
    fi
    if [ "$n" -gt 59 ]; then
        print_warning "Minutes value > 59. Cron will still accept */$n but may be unusual."
    fi

    # Remove existing entries first
    crontab -l 2>/dev/null | grep -v "daily_scrape.sh" | crontab - >/dev/null 2>&1

    # Add new cron job
    (crontab -l 2>/dev/null | grep -v "daily_scrape.sh"; echo "*/$n * * * * $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

    if [ $? -eq 0 ]; then
        print_success "Daily scraping cron job added successfully"
        echo ""
        print_info "Configured schedule: every $n minute(s)"
        print_info "Logs will be saved to: $LOG_PATH"
    else
        print_error "Failed to add cron job"
        return 1
    fi
}

show_configured_entries() {
    if crontab -l 2>/dev/null | grep -q "daily_scrape.sh"; then
        print_success "Daily scraping cron job is ACTIVE"
        echo ""
        echo "📝 Current cron entries:"
        crontab -l | grep "daily_scrape.sh" | nl -v1 | sed 's/^/   /'
        echo ""
        print_info "Note: Entries reflect server local time."
    else
        print_warning "No daily scraping cron job found"
        echo ""
        print_info "Use '$0 start' to add the cron job"
    fi
}

usage() {
    print_header
    echo "Usage: $0 {start|stop|status|logs|test|info} [options]"
    echo ""
    echo "Commands:"
    echo "  start                Add cron job with default time (09:00)"
    echo "  start HH:MM          Add cron job to run daily at HH:MM"
    echo "  start T1,T2,...      Add multiple times (e.g., 09:00,15:00,21:00)"
    echo "  start --every-min N  Run every N minutes (e.g., --every-min 30)"
    echo "  stop                 Remove cron job(s)"
    echo "  status               Show current cron entries"
    echo "  logs                 Show recent cron logs"
    echo "  test                 Test the daily scraping script manually"
    echo "  info                 Show detailed setup information"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 start 09:00"
    echo "  $0 start 09:00,13:30,18:45"
    echo "  $0 start --every-min 30"
}

case "$1" in
    "status")
        print_header
        echo "📅 Current cron jobs for daily scraping:"
        echo ""
        show_configured_entries
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
        echo "🚀 Configuring daily scraping cron job..."
        echo ""

        if ! validate_environment; then
            exit 1
        fi

        # Default time if none provided
        if [ $# -eq 1 ]; then
            print_info "No time provided, using default 09:00 daily"
            add_cron_for_times "09:00" || exit 1
            exit 0
        fi

        # Shift to get options/args after 'start'
        shift
        if [ "$1" == "--every-min" ]; then
            if [ -z "${2:-}" ]; then
                print_error "Missing value for --every-min"
                usage
                exit 1
            fi
            add_cron_every_minutes "$2" || exit 1
            exit 0
        else
            # Expect HH:MM[,HH:MM...]
            add_cron_for_times "$1" || exit 1
            exit 0
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
        echo "🗓️ Configured cron entries:"
        if crontab -l 2>/dev/null | grep -q "daily_scrape.sh"; then
            crontab -l | grep "daily_scrape.sh" | sed 's/^/   /'
        else
            print_warning "No entries currently configured"
        fi
        ;;

    ""|-h|--help|help)
        usage
        ;;

    *)
        usage
        exit 1
        ;;
esac
