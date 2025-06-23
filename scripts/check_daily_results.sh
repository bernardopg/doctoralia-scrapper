#!/bin/bash

# Script to check recent daily scraping results

PROJECT_DIR="/home/hostinger/doctoralia-scrapper"
DATA_DIR="$PROJECT_DIR/data/extractions"
LOGS_DIR="$PROJECT_DIR/logs"

echo "🔍 Daily Scraping Results Summary"
echo "================================="
echo ""

# Check recent extractions
echo "📊 Recent Data Extractions:"
if [ -d "$DATA_DIR" ]; then
    ls -lt "$DATA_DIR" | head -5 | while read line; do
        if [[ $line == *"bruna_pinto_gomes"* ]]; then
            echo "  ✅ $line"
        fi
    done
else
    echo "  ❌ No data directory found"
fi

echo ""

# Check daily scraping logs
echo "📋 Recent Daily Scraping Logs:"
if [ -f "$LOGS_DIR/daily_scrape.log" ]; then
    echo "  Last 5 entries:"
    tail -5 "$LOGS_DIR/daily_scrape.log" | sed 's/^/    /'
else
    echo "  ❌ No daily scraping logs found"
fi

echo ""

# Check cron logs
echo "🤖 Recent Cron Job Logs:"
if [ -f "$LOGS_DIR/cron.log" ]; then
    echo "  Last 3 entries:"
    tail -3 "$LOGS_DIR/cron.log" | sed 's/^/    /'
else
    echo "  ❌ No cron logs found"
fi

echo ""

# Check if cron job is active
echo "⏰ Cron Job Status:"
if crontab -l | grep -q daily_scrape.sh; then
    echo "  ✅ Daily scraping cron job is active"
    echo "  📅 Next run: Every day at 9:00 AM"
else
    echo "  ❌ Daily scraping cron job is not active"
fi
