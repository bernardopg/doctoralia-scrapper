#!/usr/bin/env bash
set -euo pipefail

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          DOCTORALIA SCRAPER - STATUS CHECK             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

LOG_DIR="/root/dev/doctoralia-scrapper/data/logs"
RUN_LOG="$(ls -1t $LOG_DIR/daily_scrape.*.log 2>/dev/null | head -1 || true)"

echo "📅 Cron Schedule:"
crontab -l 2>/dev/null | grep -A 1 "DOCTORALIA_SCRAPER_CRON" || echo "No cron configured"
echo ""

echo "📁 Latest Run Log: ${RUN_LOG:-none}"
if [[ -n "${RUN_LOG:-}" ]]; then
  echo ""
  echo "📝 Last 30 lines:"
  echo "----------------------------------------"
  tail -n 30 "$RUN_LOG"
fi
echo ""

echo "🔒 Lock File:"
if [[ -e /var/lock/doctoralia-daily.lock ]]; then 
  ls -l /var/lock/doctoralia-daily.lock
else 
  echo "  No lock file (not running)"
fi
echo ""

echo "💾 Disk Usage:"
df -h /root/dev/doctoralia-scrapper | tail -1
echo ""

echo "📊 Status JSON:"
if [[ -f /root/dev/doctoralia-scrapper/data/health/status.json ]]; then
  cat /root/dev/doctoralia-scrapper/data/health/status.json | python3 -m json.tool 2>/dev/null || cat /root/dev/doctoralia-scrapper/data/health/status.json
else
  echo "{\"status\": \"never_run\"}"
fi
