"""
Web dashboard for monitoring Doctoralia scraper operations.
Provides real-time monitoring, analytics, and management interface.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import our modules
try:
    from config.settings import AppConfig
    from src.logger import setup_logger
    from src.multi_site_scraper import ScraperFactory
    from src.performance_monitor import PerformanceMonitor
    from src.response_quality_analyzer import ResponseQualityAnalyzer
except ImportError:
    # Handle import errors gracefully
    AppConfig = None
    setup_logger = None
    PerformanceMonitor = None
    ResponseQualityAnalyzer = None
    ScraperFactory = None

# Import Flask modules
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS


class DashboardApp:
    """
    Flask-based dashboard for monitoring scraper operations.
    """

    def __init__(self, config: Any = None, logger: Any = None) -> None:
        self.config = config
        self.logger = logger or (
            setup_logger("dashboard", config) if setup_logger else None
        )

        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent.parent / "templates"),
            static_folder=str(Path(__file__).parent.parent / "static"),
        )
        CORS(self.app)

        self.performance_monitor = (
            PerformanceMonitor(self.logger) if PerformanceMonitor else None
        )
        self.quality_analyzer = (
            ResponseQualityAnalyzer() if ResponseQualityAnalyzer else None
        )

        self.setup_routes()

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

        @self.app.route("/api/health")
        def health_check():
            """Health check endpoint."""
            return jsonify(
                {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0",
                }
            )

    def _setup_api_routes(self) -> None:
        """Setup API routes."""

        @self.app.route("/api/stats")
        def get_stats():
            """Get scraper statistics."""
            try:
                stats = self._get_scraper_stats()
                return jsonify(stats)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/performance")
        def get_performance():
            """Get performance metrics."""
            try:
                if self.performance_monitor:
                    summary = self.performance_monitor.get_summary()
                    return jsonify(summary)
                return jsonify({"message": "Performance monitoring not available"})
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

    def _handle_quality_analysis(self):
        """Handle quality analysis request."""
        try:
            data = request.get_json()
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

    def _get_scraper_stats(self) -> Dict[str, Any]:
        """Get comprehensive scraper statistics."""
        stats = self._initialize_stats_dict()

        try:
            if self.config and hasattr(self.config, "data_dir"):
                data_dir = Path(self.config.data_dir) / "scraped_data"
                if data_dir.exists():
                    self._process_data_files(stats, data_dir)
        except Exception as e:
            self._log_error(f"Error getting scraper stats: {e}")

        return stats

    def _initialize_stats_dict(self) -> Dict[str, Any]:
        """Initialize the statistics dictionary."""
        return {
            "total_scraped_doctors": 0,
            "total_reviews": 0,
            "average_rating": 0.0,
            "last_scrape_time": None,
            "data_files": [],
            "platform_stats": {},
        }

    def _process_data_files(self, stats: Dict[str, Any], data_dir: Path) -> None:
        """Process data files to extract statistics."""
        json_files = list(data_dir.glob("*.json"))
        stats["data_files"] = [f.name for f in json_files]

        total_reviews = 0
        total_rating = 0.0
        doctors_count = 0
        platforms = {}

        for json_file in json_files:
            total_reviews, total_rating, doctors_count = self._process_single_file(
                json_file, stats, platforms, total_reviews, total_rating, doctors_count
            )

        self._finalize_stats(
            stats, total_reviews, total_rating, doctors_count, platforms
        )

    def _process_single_file(
        self,
        json_file: Path,
        stats: Dict[str, Any],
        platforms: Dict[str, Any],
        total_reviews: int,
        total_rating: float,
        doctors_count: int,
    ) -> tuple[int, float, int]:
        """Process a single data file."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            doctors_count += 1
            reviews_count = data.get("summary", {}).get("total_reviews", 0)
            avg_rating = data.get("summary", {}).get("average_rating", 0.0)
            platform = data.get("platform", "unknown")

            total_reviews += reviews_count
            if avg_rating > 0:
                total_rating += avg_rating

            self._update_platform_stats(platforms, platform, reviews_count)

            # Track last scrape time
            scraped_at = data.get("scraped_at")
            if scraped_at:
                self._update_last_scrape_time(stats, scraped_at)

        except Exception as e:
            self._log_warning(f"Error reading {json_file}: {e}")

        return total_reviews, total_rating, doctors_count

    def _update_platform_stats(
        self, platforms: Dict[str, Any], platform: str, reviews_count: int
    ) -> None:
        """Update platform statistics."""
        if platform not in platforms:
            platforms[platform] = {"doctors": 0, "reviews": 0}
        platforms[platform]["doctors"] += 1
        platforms[platform]["reviews"] += reviews_count

    def _update_last_scrape_time(self, stats: Dict[str, Any], scraped_at: str) -> None:
        """Update the last scrape time if newer."""
        try:
            scrape_time = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            current_last = stats["last_scrape_time"]
            if not current_last or scrape_time > datetime.fromisoformat(
                current_last.replace("Z", "+00:00")
            ):
                stats["last_scrape_time"] = scraped_at
        except Exception:
            pass  # Ignore datetime parsing errors

    def _finalize_stats(
        self,
        stats: Dict[str, Any],
        total_reviews: int,
        total_rating: float,
        doctors_count: int,
        platforms: Dict[str, Any],
    ) -> None:
        """Finalize statistics calculations."""
        stats["total_scraped_doctors"] = doctors_count
        stats["total_reviews"] = total_reviews
        stats["average_rating"] = total_rating / max(doctors_count, 1)
        stats["platform_stats"] = platforms

    def _log_error(self, message: str) -> None:
        """Log error message if logger is available."""
        if self.logger:
            self.logger.error(message)

    def _log_warning(self, message: str) -> None:
        """Log warning message if logger is available."""
        if self.logger:
            self.logger.warning(message)

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

    def _get_data_directory(self) -> Optional[Path]:
        """Get the data directory path."""
        if self.config and hasattr(self.config, "data_dir"):
            return Path(self.config.data_dir) / "scraped_data"
        return None

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

            return {
                "filename": json_file.name,
                "doctor_name": data.get("doctor", {}).get("name", "Unknown"),
                "platform": data.get("platform", "unknown"),
                "reviews_count": data.get("summary", {}).get("total_reviews", 0),
                "average_rating": data.get("summary", {}).get("average_rating", 0.0),
                "scraped_at": data.get("scraped_at"),
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

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
        """Run the Flask dashboard server."""
        if self.logger:
            self.logger.info(f"Starting dashboard server on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


def create_dashboard_template():
    """Create the dashboard HTML template file."""
    template_dir = Path(__file__).parent.parent / "templates"
    template_dir.mkdir(exist_ok=True)

    template_file = template_dir / "dashboard.html"
    if not template_file.exists():
        # Copy template content if it doesn't exist
        source_template = Path(__file__).parent.parent / "templates" / "dashboard.html"
        if source_template.exists():
            import shutil

            shutil.copy2(source_template, template_file)

    print(f"Dashboard template created at: {template_file}")


if __name__ == "__main__":
    # Create template and run dashboard
    create_dashboard_template()

    # Initialize and run dashboard
    dashboard = DashboardApp()
    dashboard.run(debug=True)
