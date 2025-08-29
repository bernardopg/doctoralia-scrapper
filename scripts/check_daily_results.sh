#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
LOGS_DIR="$PROJECT_DIR/data/logs"

echo "🔍 Daily Scraping Results Summary"
echo "================================="
echo ""

# Check recent extractions
echo "📊 Recent Data Extractions:"
if [ -d "$DATA_DIR" ]; then
    # Look for JSON files with doctor names
    find "$DATA_DIR" -name "*.json" -type f -printf '%T@ %p\n' | sort -n | tail -5 | while read timestamp file; do
        filename=$(basename "$file")
        if [[ $filename == *"bruna"* ]] || [[ $filename == *"doctor"* ]]; then
            date_str=$(date -d "@${timestamp%.*}" '+%Y-%m-%d %H:%M')
            echo "  ✅ $date_str - $filename"
        fi
    done
else
    echo "  ❌ No data directory found at $DATA_DIR"
fi

echo ""

# Check daily scraping logs
echo "📋 Recent Daily Scraping Logs:"
if [ -f "$LOGS_DIR/scraper.log" ]; then
    echo "  Last 5 entries:"
    tail -5 "$LOGS_DIR/scraper.log" | sed 's/^/    /'
elif [ -f "$LOGS_DIR/daily_scrape.log" ]; then
    echo "  Last 5 entries:"
    tail -5 "$LOGS_DIR/daily_scrape.log" | sed 's/^/    /'
else
    echo "  ❌ No scraping logs found"
fi

echo ""

# Check cron logs
echo "🤖 Recent Cron Job Logs:"
if [ -f "$LOGS_DIR/cron.log" ]; then
    echo "  Last 3 entries:"
    tail -3 "$LOGS_DIR/cron.log" | sed 's/^/    /'
else
    echo "  ❌ No cron logs found at $LOGS_DIR/cron.log"
fi

echo ""

# Check if cron job is active
echo "⏰ Cron Job Status:"
if crontab -l 2>/dev/null | grep -q "daily_scrape.sh"; then
    echo "  ✅ Daily scraping cron job is active"
    echo "  📅 Next run: Every day at 9:00 AM"

    # Show the actual cron entry
    echo "  📝 Cron entry:"
    crontab -l | grep "daily_scrape.sh" | sed 's/^/    /'
else
    echo "  ❌ Daily scraping cron job is not active"
    echo "  💡 Run: ./scripts/manage_daily_cron.sh start"
fi

echo ""

# Check system resources
echo "💻 System Resources:"
if command -v free >/dev/null 2>&1; then
    echo "  Memory usage:"
    free -h | grep -E "^(Mem|Swap)" | sed 's/^/    /'
fi

if command -v df >/dev/null 2>&1; then
    echo "  Disk usage:"
    df -h "$PROJECT_DIR" | tail -1 | sed 's/^/    /'
fi

echo ""

# Check for any error files
echo "🚨 Error Files:"
if [ -d "$LOGS_DIR" ]; then
    error_files=$(find "$LOGS_DIR" -name "*error*" -o -name "*fail*" -type f 2>/dev/null | wc -l)
    if [ "$error_files" -gt 0 ]; then
        echo "  ⚠️ Found $error_files error log files"
        find "$LOGS_DIR" -name "*error*" -o -name "*fail*" -type f 2>/dev/null | sed 's/^/    /'
    else
        echo "  ✅ No error files found"
    fi
else
    echo "  ❌ Logs directory not found"
fi
    echo "  ❌ Daily scraping cron job is not active"
fi
