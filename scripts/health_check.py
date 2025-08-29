#!/usr/bin/env python3
"""
Health Check script for Doctoralia Scraper
Performs comprehensive system health checks and reports issues
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import AppConfig


class HealthChecker:
    def __init__(self):
        self.config = AppConfig.load()
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.metrics: Dict[str, Any] = {}

    def check_disk_space(self) -> None:
        """Check available disk space"""
        try:
            stat = os.statvfs(self.config.base_dir)
            # Available space in GB
            available_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
            used_percent = ((total_gb - available_gb) / total_gb) * 100

            self.metrics["disk"] = {
                "available_gb": round(available_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 2),
            }

            if available_gb < 1:
                self.issues.append(
                    f"Critical: Only {available_gb:.2f}GB disk space available"
                )
            elif available_gb < 5:
                self.warnings.append(f"Low disk space: {available_gb:.2f}GB available")

        except Exception as e:
            self.issues.append(f"Failed to check disk space: {e}")

    def check_data_files(self) -> None:
        """Check data files and their freshness"""
        data_dir = self.config.data_dir

        if not data_dir.exists():
            self.issues.append("Data directory does not exist")
            return

        # Count data files
        json_files = list(data_dir.glob("*.json"))
        self.metrics["data_files"] = {"count": len(json_files), "total_size_mb": 0.0}

        if json_files:
            total_size = sum(f.stat().st_size for f in json_files)
            self.metrics["data_files"]["total_size_mb"] = round(
                total_size / (1024**2), 2
            )

            # Check most recent file
            most_recent = max(json_files, key=lambda f: f.stat().st_mtime)
            age_hours = (time.time() - most_recent.stat().st_mtime) / 3600

            self.metrics["data_files"]["most_recent_age_hours"] = round(age_hours, 1)

            if age_hours > 48:  # 2 days
                self.warnings.append(f"Data files are stale: {age_hours:.1f} hours old")
        else:
            self.warnings.append("No data files found")

    def check_logs(self) -> None:
        """Check log files and recent activity"""
        logs_dir = self.config.logs_dir

        if not logs_dir.exists():
            self.issues.append("Logs directory does not exist")
            return

        log_files = list(logs_dir.glob("*.log"))
        self.metrics["logs"] = {
            "files": len(log_files),
            "total_size_mb": 0.0,
            "recent_errors": 0,
        }

        if log_files:
            total_size = sum(f.stat().st_size for f in log_files)
            self.metrics["logs"]["total_size_mb"] = round(total_size / (1024**2), 2)

            # Check for recent errors in main log files
            main_log = logs_dir / "scraper.log"
            if main_log.exists():
                try:
                    with open(main_log, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Count errors in last 1000 lines
                        lines = content.split("\n")[-1000:]
                        error_count = sum(
                            1 for line in lines if "ERROR" in line or "❌" in line
                        )
                        self.metrics["logs"]["recent_errors"] = error_count

                        if error_count > 10:
                            self.warnings.append(
                                f"High error count in logs: {error_count} errors"
                            )
                except Exception as e:
                    self.warnings.append(f"Could not read log file: {e}")

    def check_telegram_config(self) -> None:
        """Check Telegram configuration"""
        if not self.config.telegram.enabled:
            self.warnings.append("Telegram notifications are disabled")
            return

        if not self.config.telegram.token:
            self.issues.append("Telegram token not configured")
        elif len(self.config.telegram.token) < 45:
            self.issues.append("Telegram token appears invalid")

        if not self.config.telegram.chat_id:
            self.issues.append("Telegram chat ID not configured")

        self.metrics["telegram"] = {
            "enabled": self.config.telegram.enabled,
            "token_configured": bool(self.config.telegram.token),
            "chat_id_configured": bool(self.config.telegram.chat_id),
        }

    def check_cron_jobs(self) -> None:
        """Check if cron jobs are properly configured"""
        import subprocess

        try:
            result = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                cron_content = result.stdout
                has_daily_scrape = "daily_scrape.sh" in cron_content

                self.metrics["cron"] = {
                    "configured": True,
                    "daily_scrape_active": has_daily_scrape,
                }

                if not has_daily_scrape:
                    self.warnings.append("Daily scraping cron job not found")
            else:
                self.metrics["cron"] = {"configured": False}
                self.warnings.append("Could not read crontab")

        except Exception as e:
            self.metrics["cron"] = {"configured": False}
            self.warnings.append(f"Error checking cron jobs: {e}")

    def check_memory_usage(self) -> None:
        """Check system memory usage"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            self.metrics["memory"] = {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": round(memory.percent, 1),
            }

            if memory.percent > 90:
                self.issues.append(f"Critical memory usage: {memory.percent}%")
            elif memory.percent > 80:
                self.warnings.append(f"High memory usage: {memory.percent}%")

        except ImportError:
            self.warnings.append("psutil not available for memory check")
        except Exception as e:
            self.warnings.append(f"Error checking memory: {e}")

    def generate_report(self) -> str:
        """Generate comprehensive health report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""🏥 DOCTORALIA SCRAPER HEALTH REPORT
{'=' * 50}
📅 Generated: {timestamp}

"""

        # Issues
        if self.issues:
            report += f"❌ CRITICAL ISSUES ({len(self.issues)}):\n"
            for i, issue in enumerate(self.issues, 1):
                report += f"   {i}. {issue}\n"
            report += "\n"

        # Warnings
        if self.warnings:
            report += f"⚠️ WARNINGS ({len(self.warnings)}):\n"
            for i, warning in enumerate(self.warnings, 1):
                report += f"   {i}. {warning}\n"
            report += "\n"

        # Metrics
        report += "📊 SYSTEM METRICS:\n"

        if "disk" in self.metrics:
            disk = self.metrics["disk"]
            report += f"   💾 Disk: {disk['used_percent']}% used ({disk['available_gb']}GB free)\n"

        if "memory" in self.metrics:
            mem = self.metrics["memory"]
            report += f"   🧠 Memory: {mem['used_percent']}% used ({mem['available_gb']}GB free)\n"

        if "data_files" in self.metrics:
            data = self.metrics["data_files"]
            report += (
                f"   📁 Data Files: {data['count']} files ({data['total_size_mb']}MB)\n"
            )
            if "most_recent_age_hours" in data:
                report += (
                    f"   🕐 Latest Data: {data['most_recent_age_hours']} hours old\n"
                )

        if "logs" in self.metrics:
            logs = self.metrics["logs"]
            report += f"   📋 Logs: {logs['files']} files ({logs['total_size_mb']}MB)\n"
            if "recent_errors" in logs:
                report += f"   🚨 Recent Errors: {logs['recent_errors']}\n"

        if "telegram" in self.metrics:
            tg = self.metrics["telegram"]
            status = "✅ Enabled" if tg["enabled"] else "❌ Disabled"
            report += f"   📱 Telegram: {status}\n"

        if "cron" in self.metrics:
            cron = self.metrics["cron"]
            if cron.get("configured"):
                scrape_status = (
                    "✅ Active" if cron.get("daily_scrape_active") else "❌ Inactive"
                )
                report += (
                    f"   ⏰ Cron Jobs: Configured, Daily Scrape: {scrape_status}\n"
                )
            else:
                report += "   ⏰ Cron Jobs: Not configured\n"

        # Overall status
        report += "\n" + "=" * 50 + "\n"
        if self.issues:
            report += "🔴 STATUS: CRITICAL - Requires immediate attention\n"
        elif self.warnings:
            report += "🟡 STATUS: WARNING - Monitor closely\n"
        else:
            report += "🟢 STATUS: HEALTHY - All systems operational\n"

        return report

    def run_full_check(self) -> None:
        """Run all health checks"""
        print("🔍 Running comprehensive health check...")

        self.check_disk_space()
        self.check_data_files()
        self.check_logs()
        self.check_telegram_config()
        self.check_cron_jobs()
        self.check_memory_usage()

        report = self.generate_report()
        print(report)

        # Save report to file
        reports_dir = self.config.logs_dir / "reports"
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = reports_dir / f"health_report_{timestamp}.txt"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"📄 Report saved to: {report_file}")


def main():
    checker = HealthChecker()
    checker.run_full_check()


if __name__ == "__main__":
    main()
