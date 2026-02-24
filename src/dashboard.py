"""
Web dashboard for monitoring Doctoralia scraper operations.
Provides real-time monitoring, analytics, and management interface.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config.settings import AppConfig
from src.logger import setup_logger
from src.multi_site_scraper import ScraperFactory
from src.performance_monitor import PerformanceMonitor
from src.response_quality_analyzer import ResponseQualityAnalyzer
from src.services.stats import StatsService


class DashboardApp:
    """
    Flask-based dashboard for monitoring scraper operations.
    """

    def __init__(self, config: Any = None, logger: Any = None) -> None:
        # Load config if not provided
        if config is None:
            try:
                config = AppConfig.load()
            except Exception:
                pass

        self.config = config
        self.logger = logger or (setup_logger("dashboard", config) if config else None)

        # Configure API connection
        api_host = "0.0.0.0"
        api_port = 8080
        if self.config and hasattr(self.config, "api"):
            api_host = getattr(self.config.api, "host", api_host)
            api_port = getattr(self.config.api, "port", api_port)

        # Use localhost for API calls from dashboard
        self.api_base_url = f"http://localhost:{api_port}"
        self.api_timeout = 5  # seconds

        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent.parent / "templates"),
            static_folder=str(Path(__file__).parent.parent / "static"),
        )
        CORS(self.app)

        self.performance_monitor = PerformanceMonitor(self.logger)
        self.quality_analyzer = ResponseQualityAnalyzer()

        # Shared stats service
        data_dir = self._get_data_directory()
        self.stats_service = StatsService(data_dir, self.logger)

        self.setup_routes()

    # The run() method is defined near the end of the file with more options (debug flag).
    # We keep a single implementation there to avoid duplication.

    def _call_api(self, endpoint: str, method: str = "GET", **kwargs) -> Optional[Dict]:
        """
        Make HTTP call to the main API.

        Args:
            endpoint: API endpoint (e.g., '/health', '/v1/metrics')
            method: HTTP method (GET, POST, etc.)
            **kwargs: Additional arguments for requests

        Returns:
            JSON response dict or None if API is unavailable
        """
        try:
            url = f"{self.api_base_url}{endpoint}"
            response = requests.request(method, url, timeout=self.api_timeout, **kwargs)
            if response.status_code == 200:
                return response.json()
            else:
                if self.logger:
                    self.logger.warning(
                        f"API call failed: {method} {endpoint} -> {response.status_code}"
                    )
                return None
        except requests.exceptions.ConnectionError:
            if self.logger:
                self.logger.debug(
                    f"API not available at {self.api_base_url} (connection refused)"
                )
            return None
        except requests.exceptions.Timeout:
            if self.logger:
                self.logger.warning(f"API timeout: {method} {endpoint}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error calling API: {e}")
            return None

    def _get_api_health(self) -> Dict[str, Any]:
        """Get health status from main API."""
        api_data = self._call_api("/v1/health")
        if api_data:
            return {
                "status": "connected",
                "api_url": self.api_base_url,
                "api_data": api_data,
            }
        else:
            return {
                "status": "disconnected",
                "api_url": self.api_base_url,
                "message": "API não está acessível",
            }

    def _get_api_metrics(self) -> Optional[Dict[str, Any]]:
        """Get performance metrics from main API."""
        return self._call_api("/v1/metrics")

    def _get_api_statistics(self) -> Optional[Dict[str, Any]]:
        """Get statistics from main API."""
        return self._call_api("/v1/metrics")

    def setup_routes(self) -> None:
        """Setup Flask routes."""
        self._setup_main_routes()
        self._setup_api_routes()

    def _setup_main_routes(self) -> None:
        """Setup main application routes."""

        @self.app.route("/")
        def index():
            """Main dashboard page."""
            return render_template("dashboard.html")

        @self.app.route("/settings")
        def settings():
            """Settings page."""
            return render_template("settings.html")

        @self.app.route("/history")
        def history():
            """History page."""
            return render_template("history.html")

        @self.app.route("/reports")
        def reports():
            """Reports page."""
            return render_template("reports.html")

        @self.app.route("/health-check")
        def health_check_page():
            """Health check visual page."""
            return render_template("health.html")

        @self.app.route("/api/health")
        def health_check():
            """Health check endpoint with API connection status."""
            api_health = self._get_api_health()
            return jsonify(
                {
                    "dashboard": {
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat(),
                        "version": "1.0.0",
                    },
                    "api": api_health,
                }
            )

    def _setup_api_routes(self) -> None:
        """Setup API routes."""

        @self.app.route("/api/stats")
        def get_stats():
            """Get scraper statistics from API or local files."""
            try:
                # Try to get stats from main API first
                api_stats = self._get_api_statistics()
                if api_stats:
                    return jsonify({"source": "api", "data": api_stats})

                # Fallback to local files
                stats = self._get_scraper_stats()
                return jsonify({"source": "local", "data": stats})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/performance")
        def get_performance():
            """Get performance metrics from API or local monitor."""
            try:
                # Try to get metrics from main API first
                api_metrics = self._get_api_metrics()
                if api_metrics:
                    return jsonify(
                        {
                            "source": "api",
                            "data": api_metrics,
                        }
                    )

                # Fallback to local performance monitor
                if self.performance_monitor:
                    summary = self.performance_monitor.get_summary()
                    return jsonify({"source": "local", "data": summary})

                return jsonify(
                    {
                        "source": "none",
                        "message": "No performance data available. Start the API with 'make api'",
                    }
                )
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/trends")
        def get_trends():
            """Get trend data for charts."""
            try:
                trends: Dict[str, Any] = self._get_trend_data()
                return jsonify({"source": "local", "data": trends})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/recent-activity")
        def get_recent_activity():
            """Get recent scraping activity."""
            try:
                activities = self._get_recent_activities()
                return jsonify(activities)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/quality-analysis", methods=["POST"])
        def analyze_quality():
            """Analyze response quality."""
            return self._handle_quality_analysis()

        @self.app.route("/api/platforms")
        def get_platforms():
            """Get supported platforms."""
            try:
                if ScraperFactory:
                    platforms = ScraperFactory.get_supported_platforms()
                    return jsonify({"platforms": platforms})
                return jsonify({"platforms": ["doctoralia"]})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/logs")
        def get_logs():
            """Get recent log entries."""
            try:
                lines = request.args.get("lines", default=50, type=int)
                logs = self._get_recent_logs(lines)
                return jsonify({"logs": logs})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        # Proxy endpoints to avoid CORS issues
        @self.app.route("/api/scrape", methods=["POST"])
        def proxy_scrape():
            """Proxy scraping request to main API."""
            try:
                data = request.get_json()
                result = self._call_api("/v1/scrape:run", method="POST", json=data)
                if result:
                    return jsonify(result)
                return (
                    jsonify(
                        {
                            "error": "API não disponível. Execute 'make api' para iniciar."
                        }
                    ),
                    503,
                )
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/tasks/<task_id>")
        def proxy_task_status(task_id):
            """Proxy task status request to main API."""
            try:
                result = self._call_api(f"/v1/jobs/{task_id}")
                if result:
                    return jsonify(result)
                return (
                    jsonify({"error": "API não disponível ou task não encontrada"}),
                    503,
                )
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/tasks")
        def proxy_list_tasks():
            """Proxy task list request to main API."""
            try:
                status = request.args.get("status")
                endpoint = "/v1/jobs"
                if status:
                    endpoint += f"?status={status}"

                result = self._call_api(endpoint)
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/settings")
        def proxy_get_settings():
            """Proxy GET settings request to main API."""
            try:
                result = self._call_api("/v1/settings")
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/settings", methods=["PUT"])
        def proxy_update_settings():
            """Proxy PUT settings request to main API."""
            try:
                data = request.get_json(force=True, silent=True)
                result = self._call_api("/v1/settings", method="PUT", json=data)
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/settings/validate", methods=["POST"])
        def proxy_validate_settings():
            """Proxy POST settings validate request to main API."""
            try:
                data = request.get_json(force=True, silent=True)
                result = self._call_api(
                    "/v1/settings/validate", method="POST", json=data
                )
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/reports/files")
        def get_report_files():
            """List available data files for reports."""
            try:
                files = self._get_data_files()
                return jsonify({"files": files})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/reports/export/<format_type>")
        def export_data(format_type):
            """Export scraped data in specified format."""
            try:
                from flask import Response

                data = self._get_export_data()
                if format_type == "json":
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    return Response(
                        content,
                        mimetype="application/json",
                        headers={
                            "Content-Disposition": "attachment; filename=doctoralia_export.json"
                        },
                    )
                elif format_type == "csv":
                    content = self._convert_to_csv(data)
                    return Response(
                        content,
                        mimetype="text/csv; charset=utf-8",
                        headers={
                            "Content-Disposition": "attachment; filename=doctoralia_export.csv"
                        },
                    )
                else:
                    return (
                        jsonify({"error": f"Formato '{format_type}' não suportado"}),
                        400,
                    )
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/reports/summary")
        def get_report_summary():
            """Get report summary statistics."""
            try:
                summary = self._get_report_summary()
                return jsonify(summary)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    def _handle_quality_analysis(self):
        """Handle quality analysis request."""
        try:
            data = request.get_json(force=True, silent=True)
            if data is None:
                return jsonify({"error": "Invalid JSON in request body"}), 400
            response_text = data.get("response", "")
            original_review = data.get("original_review", "")

            if not response_text:
                return jsonify({"error": "Response text is required"}), 400

            if self.quality_analyzer:
                analysis = self.quality_analyzer.analyze_response(
                    response_text, original_review
                )
                return jsonify(
                    {
                        "score": analysis.score.to_dict(),
                        "strengths": analysis.strengths,
                        "weaknesses": analysis.weaknesses,
                        "suggestions": analysis.suggestions,
                        "keywords": analysis.keywords,
                        "sentiment": analysis.sentiment,
                        "readability_score": analysis.readability_score,
                    }
                )
            else:
                return jsonify({"error": "Quality analyzer not available"}), 503

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def _get_trend_data(self) -> Dict[str, Any]:
        """Get trend data (reviews over time)."""
        try:
            return self.stats_service.get_trend_data()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting trend data: {e}")
            return {"dates": [], "reviews": [], "scrapes": []}

    def _get_scraper_stats(self) -> Dict[str, Any]:
        """Get comprehensive scraper statistics."""
        try:
            return self.stats_service.get_scraper_stats()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting scraper stats: {e}")
            return {
                "total_scraped_doctors": 0,
                "total_reviews": 0,
                "average_rating": 0.0,
                "last_scrape_time": None,
                "data_files": [],
                "platform_stats": {},
            }

    def _get_recent_activities(self) -> List[Dict[str, Any]]:
        """Get recent scraping activities."""
        activities = []

        try:
            data_dir = self._get_data_directory()
            if data_dir and data_dir.exists():
                json_files = self._get_recent_json_files(data_dir)
                activities = self._process_activity_files(json_files)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting recent activities: {e}")

        return activities

    def _get_data_directory(self) -> Path:
        """Get the data directory path."""
        if self.config and hasattr(self.config, "data_dir"):
            return Path(self.config.data_dir)
        return Path("data")

    def _get_recent_json_files(self, data_dir: Path) -> List[Path]:
        """Get the most recent JSON files."""
        json_files = sorted(data_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
        return json_files[:10]  # Last 10 activities

    def _process_activity_files(self, json_files: List[Path]) -> List[Dict[str, Any]]:
        """Process activity files and extract data."""
        activities = []
        for json_file in json_files:
            activity_data = self._extract_activity_data(json_file)
            if activity_data:
                activities.append(activity_data)
        return activities

    def _extract_activity_data(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """Extract activity data from a single JSON file."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Support both flat format (scraper.save_data) and nested format
            doctor_name = data.get("doctor_name") or data.get("doctor", {}).get(
                "name", "Unknown"
            )
            reviews = data.get("reviews", [])
            reviews_count = data.get("total_reviews", 0) or len(reviews)

            if "summary" in data:
                average_rating = data["summary"].get("average_rating", 0.0)
            else:
                ratings = [r.get("rating", 0) for r in reviews if r.get("rating")]
                average_rating = sum(ratings) / len(ratings) if ratings else 0.0

            scraped_at = data.get("scraped_at") or data.get("extraction_timestamp")

            return {
                "filename": json_file.name,
                "doctor_name": doctor_name,
                "platform": data.get("platform", "doctoralia"),
                "reviews_count": reviews_count,
                "average_rating": average_rating,
                "scraped_at": scraped_at,
                "file_size": json_file.stat().st_size,
            }

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Error reading activity {json_file}: {e}")
            return None

    def _get_recent_logs(self, lines: int = 50) -> List[str]:
        """Get recent log entries."""
        logs = []

        try:
            if self.config and hasattr(self.config, "logs_dir"):
                logs_dir = Path(self.config.logs_dir)
                if logs_dir.exists():
                    # Find the most recent log file
                    log_files = list(logs_dir.glob("*.log"))
                    if log_files:
                        latest_log = max(log_files, key=os.path.getmtime)

                        with open(latest_log, "r", encoding="utf-8") as f:
                            all_lines = f.readlines()
                            logs = [line.strip() for line in all_lines[-lines:]]

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading logs: {e}")
            logs = [f"Error reading logs: {e}"]

        return logs

    def _get_data_files(self) -> List[Dict[str, Any]]:
        """List available data files with metadata."""
        files: List[Dict[str, Any]] = []
        data_dir = self._get_data_directory()

        if not data_dir.exists():
            return files

        for json_file in sorted(
            data_dir.glob("*.json"), key=os.path.getmtime, reverse=True
        ):
            try:
                stat = json_file.stat()
                # Extract doctor name and date from filename
                parts = json_file.stem.split("_", 2)
                date_str = parts[0] if len(parts) > 0 else ""
                doctor_name = (
                    parts[2].replace("_", " ").title()
                    if len(parts) > 2
                    else json_file.stem
                )

                files.append(
                    {
                        "name": json_file.name,
                        "doctor": doctor_name,
                        "size": stat.st_size,
                        "size_human": self._format_file_size(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "date_str": (
                            f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                            if len(date_str) >= 8
                            else ""
                        ),
                    }
                )
            except Exception:
                continue

        return files

    def _get_export_data(self) -> List[Dict[str, Any]]:
        """Get all scraped data for export."""
        data_dir = self._get_data_directory()
        all_data: List[Dict[str, Any]] = []

        if not data_dir.exists():
            return all_data

        for json_file in sorted(data_dir.glob("*.json"), key=os.path.getmtime):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    all_data.append(file_data)
            except Exception:
                continue

        return all_data

    def _convert_to_csv(self, data: List[Dict[str, Any]]) -> str:
        """Convert scraped data to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "doctor_name",
                "extraction_date",
                "review_id",
                "author",
                "rating",
                "date",
                "comment",
                "generated_response",
            ]
        )

        for entry in data:
            doctor_name = entry.get("doctor_name", "")
            extraction_ts = entry.get("extraction_timestamp", "")
            reviews = entry.get("reviews", [])

            for review in reviews:
                writer.writerow(
                    [
                        doctor_name,
                        extraction_ts,
                        review.get("id", ""),
                        review.get("author", ""),
                        review.get("rating", ""),
                        review.get("date", ""),
                        review.get("comment", ""),
                        review.get("generated_response", ""),
                    ]
                )

        return output.getvalue()

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _get_report_summary(self) -> Dict[str, Any]:
        """Get summary statistics for reports page."""
        data_dir = self._get_data_directory()
        total_files = 0
        today_files = 0
        total_reviews = 0
        doctors = set()
        today = datetime.now().strftime("%Y%m%d")

        if data_dir.exists():
            for json_file in data_dir.glob("*.json"):
                total_files += 1
                if json_file.name.startswith(today):
                    today_files += 1
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                        doctor_name = file_data.get("doctor_name", "")
                        if doctor_name:
                            doctors.add(doctor_name)
                        total_reviews += len(file_data.get("reviews", []))
                except Exception:
                    continue

        return {
            "total_files": total_files,
            "today_files": today_files,
            "total_reviews": total_reviews,
            "unique_doctors": len(doctors),
        }

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
        """Run the Flask dashboard server."""
        if self.logger:
            self.logger.info(f"Starting dashboard server on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


def start_dashboard(
    host: str = "0.0.0.0", port: int = 5000, debug: bool = False
):  # pragma: no cover - thin wrapper
    """Convenience wrapper so the CLI can start the dashboard with a single import."""
    config = None
    try:
        from config.settings import AppConfig as _Cfg  # local import

        config = _Cfg.load()
    except Exception:  # noqa: BLE001
        config = None
    app = DashboardApp(config)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    dashboard = DashboardApp()
    dashboard.run(debug=True)
