# Daily Automation Setup

This document explains the daily automation setup for scraping Dr. Bruna Pinto Gomes' Doctoralia page.

## 🚀 What's Configured

Your system is now set up to automatically scrape the Doctoralia page for Dr. Bruna Pinto Gomes every day at **9:00 AM**.

- **Target URL**: <https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte>
- **Schedule**: Daily at 9:00 AM (Brazilian time)
- **Automation**: Linux cron job
- **Logs**: Stored in `logs/` directory

## 📁 Files Created

- `scripts/daily_scrape.sh` - Main daily scraping script
- `scripts/manage_daily_cron.sh` - Management script for cron jobs
- `scripts/check_daily_results.sh` - Script to check recent results
- `logs/daily_scrape.log` - Daily scraping execution logs
- `logs/cron.log` - Cron job system logs

## 🛠️ Management Commands

### Check Status

```bash
./scripts/manage_daily_cron.sh status
```

### Stop Daily Automation

```bash
./scripts/manage_daily_cron.sh stop
```

### Start Daily Automation

```bash
./scripts/manage_daily_cron.sh start
```

### View Recent Logs

```bash
./scripts/manage_daily_cron.sh logs
```

### Test Script Manually

```bash
./scripts/manage_daily_cron.sh test
```

### Check Recent Results

```bash
./scripts/check_daily_results.sh
```

## 📊 Monitoring

### Data Location

Scraped data is saved to: `data/extractions/YYYYMMDD_HHMMSS_bruna_pinto_gomes/`

### Log Files

- `logs/daily_scrape.log` - Detailed execution logs
- `logs/cron.log` - System cron job logs

### Telegram Notifications

If configured, you'll receive Telegram notifications after each successful scraping.

## 🔧 Customization

### Change Schedule

To modify the schedule, edit the cron job:

```bash
crontab -e
```

Current schedule: `0 9 * * *` (9:00 AM daily)

Examples:

- `0 8 * * *` - 8:00 AM daily
- `0 12 * * 1-5` - 12:00 PM weekdays only
- `0 9,18 * * *` - 9:00 AM and 6:00 PM daily

### Manual Execution

To run the scraper manually:

```bash
./scripts/daily_scrape.sh
```

## 🚨 Troubleshooting

### Check if Cron is Running

```bash
systemctl status cron
```

### View System Cron Logs

```bash
sudo journalctl -u cron -f
```

### Common Issues

1. **Virtual environment not found**: Ensure `venv/` directory exists
2. **Permission denied**: Make sure scripts are executable (`chmod +x`)
3. **Chrome not found**: Ensure Google Chrome is installed
4. **No network**: Check internet connection for scraping

### Recovery

If something goes wrong, you can:

1. Stop automation: `./scripts/manage_daily_cron.sh stop`
2. Test manually: `./scripts/manage_daily_cron.sh test`
3. Restart automation: `./scripts/manage_daily_cron.sh start`

## 📈 Expected Results

Each day at 9:00 AM, the system will:

1. ✅ Activate the Python virtual environment
2. ✅ Launch Chrome browser (headless mode)
3. ✅ Navigate to Dr. Bruna's Doctoralia page
4. ✅ Extract all patient comments and reviews
5. ✅ Save data to timestamped directory
6. ✅ Send Telegram notification (if configured)
7. ✅ Log execution details

The entire process typically takes 2-3 minutes to complete.
