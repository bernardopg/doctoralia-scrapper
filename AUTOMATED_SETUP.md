# 🎯 Doctoralia Scraper - Automated Setup Complete

## ✅ Installation Summary

Your Doctoralia scraper is now **fully configured** and **production-ready**!

### 📅 Automated Schedule

- **Morning Run**: Every day at **08:30 AM**
- **Evening Run**: Every day at **19:00 PM** (7:00 PM)

### 🔧 What Was Configured

1. **✓ Python Environment**
   - Virtual environment with Poetry
   - All dependencies installed

2. **✓ Configuration**
   - Target URL: `https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte`
   - Telegram notifications enabled
   - Full workflow mode (scrape + generate responses)

3. **✓ Automation**
   - Cron jobs installed for 08:30 and 19:00
   - Automatic retries (up to 3 attempts)
   - Intelligent error detection and recovery

4. **✓ Monitoring**
   - Telegram notifications for every run
   - Detailed logging in `data/logs/`
   - Health status tracking in `data/health/status.json`
   - Log rotation (14 days retention, compressed)

5. **✓ Error Handling**
   - Network timeout detection
   - Rate limit detection
   - Selenium/WebDriver error recovery
   - Exponential backoff retry logic

---

## 📋 Useful Commands

### Check Status

```bash
# Quick status check
/root/dev/doctoralia-scrapper/scripts/status_check.sh

# View cron schedule
crontab -l

# View latest log
tail -f /root/dev/doctoralia-scrapper/data/logs/latest.log
```

### Manual Operations

```bash
# Run manually (test)
/root/dev/doctoralia-scrapper/scripts/daily_scrape.sh

# Update cron schedule
/root/dev/doctoralia-scrapper/scripts/manage_daily_cron.sh

# Remove cron jobs
crontab -l | grep -v "DOCTORALIA_SCRAPER_CRON" | crontab -
```

### Logs & Monitoring

```bash
# View all logs
ls -lh /root/dev/doctoralia-scrapper/data/logs/

# View today's log
tail -100 /root/dev/doctoralia-scrapper/data/logs/daily_scrape.$(date +%F).log

# View health status
cat /root/dev/doctoralia-scrapper/data/health/status.json
```

---

## 📱 Telegram Notifications

You'll receive notifications for:

- ⏳ Job started
- ✅ Successful completion (with attempt number)
- 🔴 Failures (with error details and log location)

### Test Telegram Notifications

```bash
source /root/dev/doctoralia-scrapper/.env
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  -d text="🧪 Test notification from Doctoralia scraper!"
```

---

## 🛠️ Troubleshooting

### If a run fails

1. Check the latest log: `tail -100 /root/dev/doctoralia-scrapper/data/logs/latest.log`
2. Check health status: `cat /root/dev/doctoralia-scrapper/data/health/status.json`
3. The script will automatically retry (up to 3 times) with these strategies:
   - **Rate limiting**: Wait 3x longer
   - **Network errors**: Wait with exponential backoff
   - **Selenium errors**: Restart with clean state

### Common Issues

**Network failures:**

- Script retries automatically with exponential backoff
- Check connectivity: `curl -I https://www.doctoralia.com.br`

**Selenium/WebDriver errors:**

- Dependencies auto-installed in venv
- If persistent, recreate venv: `cd /root/dev/doctoralia-scrapper && poetry install --no-root`

**Rate limiting (HTTP 429):**

- Script automatically backs off 3x longer
- Consider adding random jitter if persistent

### Re-create Environment

```bash
cd /root/dev/doctoralia-scrapper
rm -rf .venv
poetry install --no-root
```

---

## 📊 File Structure

```text
/root/dev/doctoralia-scrapper/
├── .env                          # Environment variables (Telegram, etc.)
├── config/config.json            # Scraper configuration
├── data/
│   ├── logs/                     # All run logs (rotated daily)
│   │   ├── latest.log           # Symlink to most recent log
│   │   ├── daily_scrape.*.log   # Daily run logs
│   │   └── cron.log             # Cron execution log
│   ├── health/
│   │   └── status.json          # Last run status & health
│   ├── backups/                 # Data backups
│   └── temp/                    # Temporary files
└── scripts/
    ├── daily_scrape.sh          # Main automation script
    ├── manage_daily_cron.sh     # Cron management
    └── status_check.sh          # Status checker
```

---

## 🔒 Security Notes

- `.env` file contains sensitive Telegram credentials
- Already added to `.gitignore` (won't be committed)
- Backup files (`*.bak`, `*.backup`) also ignored
- Logs and data directories excluded from git

---

## ⚙️ Changing the Schedule

To modify run times, edit `/root/dev/doctoralia-scrapper/scripts/manage_daily_cron.sh`:

```bash
# Change these lines:
echo "30 08 * * * $SCRIPT >> $LOG 2>&1"  # 08:30 AM
echo "00 19 * * * $SCRIPT >> $LOG 2>&1"  # 19:00 PM (7:00 PM)

# Then reinstall:
/root/dev/doctoralia-scrapper/scripts/manage_daily_cron.sh
```

**Cron time format**: `minute hour day month weekday`

- `30 08 * * *` = 08:30 AM every day
- `00 19 * * *` = 19:00 PM (7:00 PM) every day
- `*/15 * * * *` = Every 15 minutes

---

## 🎉 Next Steps

1. **Wait for the first scheduled run** at 08:30 or 19:00
2. **Check your Telegram** for notifications
3. **Monitor logs** if you're curious: `tail -f /root/dev/doctoralia-scrapper/data/logs/latest.log`

Your system is now running autonomously! 🚀

---

**Setup completed on:** $(date '+%Y-%m-%d %H:%M:%S %Z')
**Configuration:** Production-ready with full monitoring
**Support:** Check logs and health status for any issues
