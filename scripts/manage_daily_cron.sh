#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT="/root/dev/doctoralia-scrapper/scripts/daily_scrape.sh"
LOG="/root/dev/doctoralia-scrapper/data/logs/cron.log"

block_start="### DOCTORALIA_SCRAPER_CRON START"
block_end="### DOCTORALIA_SCRAPER_CRON END"

tmp="$(mktemp)"
crontab -l 2>/dev/null | awk -v s="$block_start" -v e="$block_end" '
  $0==s {skip=1}
  $0==e {skip=0; next}
  skip!=1 {print}
' > "$tmp"

{
  echo "$block_start"
  echo "SHELL=/bin/bash"
  echo "PATH=/root/dev/doctoralia-scrapper/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  echo "PYTHONPATH=/root/dev/doctoralia-scrapper"
  echo "30 08 * * * $SCRIPT >> $LOG 2>&1"
  echo "00 19 * * * $SCRIPT >> $LOG 2>&1"
  echo "$block_end"
} >> "$tmp"

crontab "$tmp"
rm -f "$tmp"
echo "✅ Cron installed successfully!"
echo "📅 Schedule: Every day at 08:30 and 19:00"
