"""
Shared statistics service for scraper data.
Used by both the API and the Dashboard to avoid code duplication.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StatsService:
    """
    Centralized service for computing scraper statistics from data files.
    """

    def __init__(self, data_dir: Path, log: Optional[logging.Logger] = None) -> None:
        self.data_dir = Path(data_dir)
        self.logger = log or logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get comprehensive scraper statistics."""
        stats: Dict[str, Any] = {
            "total_scraped_doctors": 0,
            "total_reviews": 0,
            "average_rating": 0.0,
            "last_scrape_time": None,
            "data_files": [],
            "platform_stats": {},
        }

        if not self.data_dir.exists():
            return stats

        json_files = list(self.data_dir.glob("*.json"))
        stats["data_files"] = [f.name for f in json_files]

        total_reviews = 0
        total_rating = 0.0
        doctors_count = 0
        platforms: Dict[str, Any] = {}

        for json_file in json_files:
            file_stats = self._process_single_file(json_file)
            if not file_stats:
                continue

            doctors_count += 1
            total_reviews += file_stats["reviews_count"]
            if file_stats["avg_rating"] > 0:
                total_rating += file_stats["avg_rating"]

            self._update_platform_stats(
                platforms, file_stats["platform"], file_stats["reviews_count"]
            )

            scraped_at = file_stats["scraped_at"]
            if scraped_at:
                self._update_last_scrape_time(stats, scraped_at)

        stats["total_scraped_doctors"] = doctors_count
        stats["total_reviews"] = total_reviews
        stats["average_rating"] = total_rating / max(doctors_count, 1)
        stats["platform_stats"] = platforms

        return stats

    def get_trend_data(self, max_days: int = 30) -> Dict[str, Any]:
        """Get trend data (reviews over time)."""
        trends: Dict[str, Any] = {"dates": [], "reviews": [], "scrapes": []}

        if not self.data_dir.exists():
            return trends

        daily_data: Dict[str, Dict[str, int]] = {}
        for json_file in self.data_dir.glob("*.json"):
            self._accumulate_trend_from_file(daily_data, json_file)

        sorted_dates = sorted(daily_data.keys())
        if len(sorted_dates) > max_days:
            sorted_dates = sorted_dates[-max_days:]

        trends["dates"] = sorted_dates
        trends["reviews"] = [daily_data[date]["reviews"] for date in sorted_dates]
        trends["scrapes"] = [daily_data[date]["scrapes"] for date in sorted_dates]

        return trends

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_single_file(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """Process a single JSON data file and return extracted stats."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            reviews = data.get("reviews", [])
            reviews_count = data.get("total_reviews", 0) or len(reviews)

            if "summary" in data:
                avg_rating = data["summary"].get("average_rating", 0.0)
            else:
                ratings = [r.get("rating", 0) for r in reviews if r.get("rating")]
                avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

            platform = data.get("platform", "doctoralia")
            scraped_at = data.get("scraped_at") or data.get("extraction_timestamp")

            return {
                "reviews_count": reviews_count,
                "avg_rating": avg_rating,
                "platform": platform,
                "scraped_at": scraped_at,
            }

        except Exception as e:
            self.logger.warning(f"Error reading {json_file}: {e}")
            return None

    @staticmethod
    def _update_platform_stats(
        platforms: Dict[str, Any], platform: str, reviews_count: int
    ) -> None:
        """Update platform statistics."""
        if platform not in platforms:
            platforms[platform] = {"doctors": 0, "reviews": 0}
        platforms[platform]["doctors"] += 1
        platforms[platform]["reviews"] += reviews_count

    @staticmethod
    def _update_last_scrape_time(stats: Dict[str, Any], scraped_at: str) -> None:
        """Update the last scrape time if newer."""
        try:
            scrape_time = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            current_last = stats["last_scrape_time"]
            if not current_last or scrape_time > datetime.fromisoformat(
                current_last.replace("Z", "+00:00")
            ):
                stats["last_scrape_time"] = scraped_at
        except Exception:
            pass

    def _accumulate_trend_from_file(
        self, daily_data: Dict[str, Dict[str, int]], json_file: Path
    ) -> None:
        """Accumulate trend metrics from one JSON data file."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            timestamp = data.get("scraped_at") or data.get("extraction_timestamp")
            if not timestamp:
                return

            date_key = timestamp.split("T", maxsplit=1)[0]
            reviews = data.get("reviews", [])
            reviews_count = data.get("total_reviews", 0) or len(reviews)

            if date_key not in daily_data:
                daily_data[date_key] = {"reviews": 0, "scrapes": 0}

            daily_data[date_key]["reviews"] += reviews_count
            daily_data[date_key]["scrapes"] += 1
        except Exception as e:
            self.logger.warning(f"Error reading {json_file} for trends: {e}")
