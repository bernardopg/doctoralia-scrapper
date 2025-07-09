PROJECT_DIR="/home/hostinger/doctoralia-scrapper"
SCRIPT_PATH="$PROJECT_DIR/scripts/daily_scrape.sh"
LOG_PATH="$PROJECT_DIR/logs/cron.log"

case "$1" in
    "status")
        echo "📅 Current cron jobs for daily scraping:"
        crontab -l | grep daily_scrape.sh || echo "No daily scraping cron job found"
        ;;
    "stop")
        echo "🛑 Removing daily scraping cron job..."
        crontab -l | grep -v daily_scrape.sh | crontab -
        echo "✅ Daily scraping cron job removed"
        ;;
    "start")
        echo "🚀 Adding daily scraping cron job (9:00 AM every day)..."
        (crontab -l 2>/dev/null | grep -v daily_scrape.sh; echo "0 9 * * * $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -
        echo "✅ Daily scraping cron job added"
        ;;
    "logs")
        echo "📋 Recent cron job logs:"
        if [ -f "$LOG_PATH" ]; then
            tail -20 "$LOG_PATH"
        else
            echo "No cron logs found at $LOG_PATH"
        fi
        ;;
    "test")
        echo "🧪 Testing daily scraping script..."
        "$SCRIPT_PATH"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start  - Add daily cron job (9:00 AM)"
        echo "  stop   - Remove daily cron job"
        echo "  status - Show current cron job status"
        echo "  logs   - Show recent cron job logs"
        echo "  test   - Test the daily scraping script manually"
        exit 1
        ;;
esac
