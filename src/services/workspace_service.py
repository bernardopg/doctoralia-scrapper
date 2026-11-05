"""
Workspace analytics service for the dashboard.
Provides profile-level aggregations, pending responses and filterable overview data.
"""

import hashlib
import json
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.services.snapshot_storage import snapshot_lock, write_json_atomic

logger = logging.getLogger(__name__)


def _safe_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _comparable_datetime(value: Optional[datetime]) -> datetime:
    """Normalize aware timestamps for comparisons with legacy naive values."""
    if value is None:
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _safe_date(value: Optional[str]) -> Optional[date]:
    parsed = _safe_datetime(value)
    if parsed is not None:
        return parsed.date()
    if value:
        try:
            return date.fromisoformat(value[:10])
        except Exception:
            return None
    return None


DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

# Parsed snapshots keyed by path and validated by inode, size and mtime. Every
# dashboard page re-aggregates all snapshots, so re-parsing unchanged files on
# each request dominated response time. Entries are copied before being
# returned so callers can never mutate the cached state.
_SnapshotKey = Tuple[int, int, int]
_snapshot_cache: Dict[str, Tuple[_SnapshotKey, Optional[Dict[str, Any]]]] = {}
_snapshot_cache_lock = threading.Lock()


def _copy_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    copied = dict(snapshot)
    copied["reviews"] = [dict(review) for review in snapshot["reviews"]]
    return copied


def _review_date(review: Dict[str, Any]) -> Optional[date]:
    """Return the calendar date on which the review was published.

    Offsets are kept as published by the source: ``2026-01-01T23:30-03:00`` is
    1 January, not 2 January in UTC. Values without a parsable date are
    reported as undated instead of being replaced by the collection date.
    """
    value = review.get("date")
    return _safe_date(value) if isinstance(value, str) else None


def _in_review_range(
    published: Optional[date], start: Optional[date], end: Optional[date]
) -> bool:
    """Apply a review-date range; undated reviews only pass when it is open."""
    if start is None and end is None:
        return True
    if published is None:
        return False
    return not ((start and published < start) or (end and published > end))


def _page_bounds(
    total: int, page: Optional[int], page_size: Optional[int]
) -> Tuple[int, int, Dict[str, Any]]:
    """Clamp pagination input and return slice bounds plus metadata.

    Without ``page`` and ``page_size`` every item is returned, which keeps
    existing API consumers working.
    """
    if page is None and page_size is None:
        return (
            0,
            total,
            {
                "page": 1,
                "page_size": total,
                "total_items": total,
                "total_pages": 1,
            },
        )
    requested_size = DEFAULT_PAGE_SIZE if page_size is None else page_size
    size = min(max(int(requested_size), 1), MAX_PAGE_SIZE)
    total_pages = max((total + size - 1) // size, 1)
    current = min(max(int(1 if page is None else page), 1), total_pages)
    start = (current - 1) * size
    return (
        start,
        min(start + size, total),
        {
            "page": current,
            "page_size": size,
            "total_items": total,
            "total_pages": total_pages,
        },
    )


class WorkspaceService:
    """Aggregate Doctoralia scraping data for multi-page dashboard views.

    Date filters have two distinct meanings. ``date_from``/``date_to`` select
    snapshots by collection date (``scraped_at``). ``review_date_from`` and
    ``review_date_to`` select reviews by the date they were published.
    """

    def __init__(self, data_dir: Path, log: Optional[logging.Logger] = None) -> None:
        self.data_dir = Path(data_dir)
        self.logger = log or logger

    @staticmethod
    def make_profile_id(profile_url: str, doctor_name: str) -> str:
        base = (profile_url or doctor_name or "unknown").strip().lower()
        return hashlib.md5(base.encode(), usedforsecurity=False).hexdigest()[:12]

    def _load_snapshots(self) -> List[Dict[str, Any]]:
        snapshots: List[Dict[str, Any]] = []
        if not self.data_dir.exists():
            return snapshots

        entries = []
        for json_file in self.data_dir.glob("*.json"):
            try:
                if json_file.is_symlink():
                    continue
                stat = json_file.stat()
            except OSError:
                continue
            entries.append((stat.st_mtime, json_file, stat))

        seen: set[str] = set()
        for _, json_file, stat in sorted(entries, key=lambda item: item[0]):
            cache_path = str(json_file.resolve())
            seen.add(cache_path)
            key = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            with _snapshot_cache_lock:
                cached = _snapshot_cache.get(cache_path)
            if cached is not None and cached[0] == key:
                snapshot = cached[1]
            else:
                snapshot = self._read_snapshot(json_file)
                with _snapshot_cache_lock:
                    _snapshot_cache[cache_path] = (key, snapshot)
            if snapshot:
                snapshots.append(_copy_snapshot(snapshot))

        prefix = str(self.data_dir.resolve()) + "/"
        with _snapshot_cache_lock:
            for stale in [
                path
                for path in _snapshot_cache
                if path.startswith(prefix)
                and "/" not in path[len(prefix) :]
                and path not in seen
            ]:
                del _snapshot_cache[stale]
        return snapshots

    def _read_snapshot(self, json_file: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
                return None
            reviews = data["reviews"]
            doctor_name = data.get("doctor_name") or data.get("doctor", {}).get("name")
            profile_url = data.get("url") or data.get("doctor", {}).get(
                "profile_url", ""
            )
            extracted_at = data.get("scraped_at") or data.get("extraction_timestamp")
            if not any(
                isinstance(value, str) and value.strip()
                for value in (doctor_name, profile_url)
            ):
                return None
            doctor_name = doctor_name or "Perfil sem nome"
            profile_id = self.make_profile_id(profile_url, doctor_name)
            ratings = [
                review.get("rating") for review in reviews if review.get("rating")
            ]
            average_rating = data.get("average_rating")
            if average_rating is None:
                average_rating = sum(ratings) / len(ratings) if ratings else 0.0
            unanswered_count = sum(
                1 for review in reviews if not review.get("doctor_reply")
            )
            generated_count = sum(
                1 for review in reviews if review.get("generated_response")
            )
            latest_review_date = max(
                (
                    _comparable_datetime(_safe_datetime(review.get("date")))
                    for review in reviews
                    if review.get("date")
                ),
                default=None,
            )

            return {
                "profile_id": profile_id,
                "doctor_name": doctor_name,
                "profile_url": profile_url,
                "specialty": data.get("specialty")
                or data.get("doctor", {}).get("specialty"),
                "location": data.get("location")
                or data.get("doctor", {}).get("location"),
                "filename": json_file.name,
                "file_path": str(json_file),
                "file_size": json_file.stat().st_size,
                "extracted_at": extracted_at,
                "extracted_date": extracted_at[:10] if extracted_at else None,
                "extracted_ts": _safe_datetime(extracted_at),
                "collection": data.get("collection"),
                "average_rating": float(average_rating or 0.0),
                "reviews_count": data.get("total_reviews", 0) or len(reviews),
                "unanswered_count": unanswered_count,
                "generated_count": generated_count,
                "reply_count": sum(
                    1 for review in reviews if review.get("doctor_reply")
                ),
                "latest_review_date": (
                    latest_review_date.isoformat()
                    if isinstance(latest_review_date, datetime)
                    else None
                ),
                "reviews": reviews,
            }
        except Exception as exc:
            self.logger.warning(
                "Error reading workspace snapshot %s: %s", json_file, exc
            )
            return None

    @staticmethod
    def _select_snapshot(
        snapshots: List[Dict[str, Any]], profile_id: Optional[str], filename: str
    ) -> Dict[str, Any]:
        if not profile_id or Path(filename).name != filename or filename in {".", ".."}:
            raise ValueError("Snapshot não encontrado")
        for snapshot in snapshots:
            if (
                snapshot["filename"] == filename
                and snapshot["profile_id"] == profile_id
            ):
                return snapshot
        raise ValueError("Snapshot não encontrado")

    def _filter_snapshots(
        self,
        snapshots: List[Dict[str, Any]],
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_date = _safe_date(date_from)
        end_date = _safe_date(date_to)
        filtered: List[Dict[str, Any]] = []

        for snapshot in snapshots:
            if profile_id and snapshot["profile_id"] != profile_id:
                continue
            snapshot_date = _safe_date(snapshot.get("extracted_at"))
            if start_date and snapshot_date and snapshot_date < start_date:
                continue
            if end_date and snapshot_date and snapshot_date > end_date:
                continue
            filtered.append(snapshot)

        return filtered

    @staticmethod
    def _latest_by_profile(
        snapshots: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for snapshot in snapshots:
            profile_id = snapshot["profile_id"]
            current = latest.get(profile_id)
            snapshot_info = snapshot.get("collection")
            snapshot_incomplete = (
                isinstance(snapshot_info, dict)
                and snapshot_info.get("status") != "complete"
            )
            current_info = current.get("collection") if current is not None else None
            current_incomplete = (
                isinstance(current_info, dict)
                and current_info.get("status") != "complete"
            )
            if current is not None and snapshot_incomplete != current_incomplete:
                if not snapshot_incomplete:
                    latest[profile_id] = snapshot
                continue
            current_ts = current["extracted_ts"] if current is not None else None
            snapshot_ts = snapshot["extracted_ts"]
            if current is None or (
                snapshot_ts is not None
                and (
                    current_ts is None
                    or _comparable_datetime(snapshot_ts)
                    > _comparable_datetime(current_ts)
                )
            ):
                latest[profile_id] = snapshot
        return latest

    @staticmethod
    def _favorite_url_set(
        favorite_profiles: Optional[Iterable[Dict[str, Any]]],
    ) -> set[str]:
        if not favorite_profiles:
            return set()
        urls = set()
        for profile in favorite_profiles:
            profile_url = str(profile.get("profile_url") or "").strip().lower()
            if profile_url:
                urls.add(profile_url)
        return urls

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    @staticmethod
    def _is_snapshot_latest(
        snapshot: Dict[str, Any], latest_by_profile: Dict[str, Dict[str, Any]]
    ) -> bool:
        latest = latest_by_profile.get(snapshot["profile_id"])
        return bool(latest and latest.get("file_path") == snapshot.get("file_path"))

    def build_filter_options(
        self, snapshots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        latest_profiles = self._latest_by_profile(snapshots)
        options = [
            {
                "profile_id": snapshot["profile_id"],
                "doctor_name": snapshot["doctor_name"],
                "profile_url": snapshot["profile_url"],
                "specialty": snapshot.get("specialty"),
            }
            for snapshot in latest_profiles.values()
        ]
        return sorted(options, key=lambda item: item["doctor_name"].lower())

    def get_overview(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        favorite_profiles: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        snapshots = self._load_snapshots()
        filtered = self._filter_snapshots(snapshots, profile_id, date_from, date_to)
        latest_profiles = self._latest_by_profile(filtered)
        favorite_urls = self._favorite_url_set(favorite_profiles)
        current_profiles = list(latest_profiles.values())
        total_reviews_current = sum(item["reviews_count"] for item in current_profiles)
        unanswered_current = sum(item["unanswered_count"] for item in current_profiles)
        generated_current = sum(item["generated_count"] for item in current_profiles)
        average_rating = (
            sum(item["average_rating"] for item in current_profiles)
            / len(current_profiles)
            if current_profiles
            else 0.0
        )
        timeline_map: Dict[str, Dict[str, int]] = {}
        for snapshot in filtered:
            key = snapshot.get("extracted_date") or "Sem data"
            timeline_map.setdefault(key, {"scrapes": 0, "reviews": 0, "unanswered": 0})
            timeline_map[key]["scrapes"] += 1
            timeline_map[key]["reviews"] += snapshot["reviews_count"]
            timeline_map[key]["unanswered"] += snapshot["unanswered_count"]

        timeline_dates = sorted(timeline_map.keys())[-14:]
        favorite_profiles_summary = [
            {
                "profile_id": snapshot["profile_id"],
                "doctor_name": snapshot["doctor_name"],
                "profile_url": snapshot["profile_url"],
                "average_rating": snapshot["average_rating"],
                "unanswered_count": snapshot["unanswered_count"],
                "reviews_count": snapshot["reviews_count"],
                "last_scraped_at": snapshot["extracted_at"],
            }
            for snapshot in current_profiles
            if snapshot["profile_url"].strip().lower() in favorite_urls
        ]

        recent_scrapes = sorted(
            (
                {
                    "profile_id": snapshot["profile_id"],
                    "doctor_name": snapshot["doctor_name"],
                    "profile_url": snapshot["profile_url"],
                    "reviews_count": snapshot["reviews_count"],
                    "unanswered_count": snapshot["unanswered_count"],
                    "average_rating": snapshot["average_rating"],
                    "extracted_at": snapshot["extracted_at"],
                    "filename": snapshot["filename"],
                    "collection": snapshot.get("collection"),
                }
                for snapshot in filtered
            ),
            key=lambda item: item["extracted_at"] or "",
            reverse=True,
        )[:8]

        return {
            "summary": {
                "total_scrapes": len(filtered),
                "profiles_tracked": len(current_profiles),
                "total_reviews_current": total_reviews_current,
                "unanswered_reviews_current": unanswered_current,
                "generated_suggestions_current": generated_current,
                "average_rating_current": round(average_rating, 2),
                "favorite_profiles_count": len(favorite_profiles_summary),
            },
            "favorite_profiles": sorted(
                favorite_profiles_summary,
                key=lambda item: (
                    -item["unanswered_count"],
                    -item["average_rating"],
                    item["doctor_name"].lower(),
                ),
            ),
            "recent_scrapes": recent_scrapes,
            "timeline": {
                "dates": timeline_dates,
                "scrapes": [timeline_map[day]["scrapes"] for day in timeline_dates],
                "reviews": [timeline_map[day]["reviews"] for day in timeline_dates],
                "unanswered": [
                    timeline_map[day]["unanswered"] for day in timeline_dates
                ],
            },
            "filters": self.build_filter_options(filtered or snapshots),
        }

    def get_history(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshots = self._load_snapshots()
        filtered = self._filter_snapshots(snapshots, profile_id, date_from, date_to)
        latest_by_profile = self._latest_by_profile(snapshots)
        query = (search or "").strip().lower()
        normalized_status = (status or "all").strip().lower()
        entries: List[Dict[str, Any]] = []

        for snapshot in sorted(
            filtered,
            key=lambda item: item.get("extracted_at") or "",
            reverse=True,
        ):
            is_latest = self._is_snapshot_latest(snapshot, latest_by_profile)
            collection = snapshot.get("collection")
            incomplete = (
                isinstance(collection, dict) and collection.get("status") != "complete"
            )
            snapshot_status = (
                "partial" if incomplete else ("latest" if is_latest else "outdated")
            )
            if (
                normalized_status not in {"", "all"}
                and snapshot_status != normalized_status
            ):
                continue

            entry = {
                "profile_id": snapshot["profile_id"],
                "doctor_name": snapshot["doctor_name"],
                "profile_url": snapshot["profile_url"],
                "specialty": snapshot.get("specialty"),
                "filename": snapshot["filename"],
                "extracted_at": snapshot["extracted_at"],
                "reviews_count": snapshot["reviews_count"],
                "unanswered_count": snapshot["unanswered_count"],
                "generated_count": snapshot["generated_count"],
                "average_rating": round(snapshot["average_rating"], 2),
                "file_size": snapshot["file_size"],
                "file_size_human": self._format_file_size(snapshot["file_size"]),
                "status": snapshot_status,
                "collection": collection,
                "is_latest": is_latest,
            }
            if query and query not in json.dumps(entry, ensure_ascii=False).lower():
                continue
            entries.append(entry)

        total_storage = sum(entry["file_size"] for entry in entries)
        outdated_snapshots = sum(
            1 for entry in entries if entry["status"] == "outdated"
        )
        latest_snapshots = sum(1 for entry in entries if entry["is_latest"])

        return {
            "summary": {
                "total_snapshots": len(entries),
                "profiles_covered": len({entry["profile_id"] for entry in entries}),
                "outdated_snapshots": outdated_snapshots,
                "latest_snapshots": latest_snapshots,
                "storage_used_bytes": total_storage,
                "storage_used_human": self._format_file_size(total_storage),
            },
            "entries": entries,
            "filters": self.build_filter_options(filtered or snapshots),
        }

    def list_profiles(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        favorite_profiles: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        snapshots = self._filter_snapshots(
            self._load_snapshots(),
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
        )
        latest_profiles = self._latest_by_profile(snapshots)
        favorite_urls = self._favorite_url_set(favorite_profiles)
        profile_metrics: List[Dict[str, Any]] = []

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for snapshot in snapshots:
            grouped.setdefault(snapshot["profile_id"], []).append(snapshot)

        for current_profile_id, profile_snapshots in grouped.items():
            latest = latest_profiles[current_profile_id]
            ratings = [
                item["average_rating"]
                for item in profile_snapshots
                if item["average_rating"]
            ]
            profile_metrics.append(
                {
                    "profile_id": current_profile_id,
                    "doctor_name": latest["doctor_name"],
                    "profile_url": latest["profile_url"],
                    "specialty": latest.get("specialty"),
                    "location": latest.get("location"),
                    "total_scrapes": len(profile_snapshots),
                    "average_rating": round(
                        (
                            (sum(ratings) / len(ratings))
                            if ratings
                            else latest["average_rating"]
                        ),
                        2,
                    ),
                    "current_reviews": latest["reviews_count"],
                    "current_unanswered": latest["unanswered_count"],
                    "current_generated": latest["generated_count"],
                    "last_scraped_at": latest["extracted_at"],
                    "latest_review_date": latest["latest_review_date"],
                    "is_favorite": latest["profile_url"].strip().lower()
                    in favorite_urls,
                }
            )

        return sorted(
            profile_metrics,
            key=lambda item: (
                not item["is_favorite"],
                -item["current_unanswered"],
                item["doctor_name"].lower(),
            ),
        )

    def get_profile_detail(
        self,
        profile_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        favorite_profiles: Optional[Iterable[Dict[str, Any]]] = None,
        snapshot: Optional[str] = None,
        review_date_from: Optional[str] = None,
        review_date_to: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        review_start = _safe_date(review_date_from)
        review_end = _safe_date(review_date_to)
        profiles = self.list_profiles(
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
            favorite_profiles=favorite_profiles,
        )
        if not profiles:
            return None

        all_snapshots = self._filter_snapshots(
            self._load_snapshots(),
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
        )
        latest = (
            self._select_snapshot(all_snapshots, profile_id, snapshot)
            if snapshot is not None
            else self._latest_by_profile(all_snapshots).get(profile_id)
        )
        if latest is None:
            return None

        timeline = sorted(
            (
                {
                    "extracted_at": snapshot["extracted_at"],
                    "reviews_count": snapshot["reviews_count"],
                    "average_rating": snapshot["average_rating"],
                    "unanswered_count": snapshot["unanswered_count"],
                    "generated_count": snapshot["generated_count"],
                }
                for snapshot in all_snapshots
            ),
            key=lambda item: item["extracted_at"] or "",
        )

        latest_reviews = sorted(
            (
                {
                    "review_id": str(review.get("id") or ""),
                    "author": review.get("author") or "Paciente",
                    "comment": review.get("comment") or review.get("text") or "",
                    "rating": review.get("rating"),
                    "date": review.get("date"),
                    "review_date": published.isoformat() if published else None,
                    "collected_at": latest["extracted_at"],
                    "doctor_reply": review.get("doctor_reply"),
                    "generated_response": review.get("generated_response"),
                    "pending_response": not bool(review.get("doctor_reply")),
                }
                for review, published in (
                    (review, _review_date(review)) for review in latest["reviews"]
                )
                if _in_review_range(published, review_start, review_end)
            ),
            key=lambda item: item["date"] or "",
            reverse=True,
        )

        return {
            "selected_snapshot": {
                "filename": latest["filename"],
                "collection": latest.get("collection"),
                "reviews_count": len(latest["reviews"]),
                "unanswered_count": latest["unanswered_count"],
                "generated_count": latest["generated_count"],
            },
            "profile": profiles[0],
            "timeline": timeline,
            "latest_reviews": latest_reviews,
        }

    def list_pending_responses(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        favorite_profiles: Optional[Iterable[Dict[str, Any]]] = None,
        favorites_only: bool = False,
        search: Optional[str] = None,
        snapshot: Optional[str] = None,
        review_date_from: Optional[str] = None,
        review_date_to: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        review_start = _safe_date(review_date_from)
        review_end = _safe_date(review_date_to)
        undated_excluded = 0
        snapshots = self._filter_snapshots(
            self._load_snapshots(),
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
        )
        latest_profiles = (
            {profile_id: self._select_snapshot(snapshots, profile_id, snapshot)}
            if snapshot is not None and profile_id
            else self._latest_by_profile(snapshots)
        )
        if snapshot is not None and not profile_id:
            raise ValueError("Snapshot não encontrado")
        favorite_urls = self._favorite_url_set(favorite_profiles)
        query = (search or "").strip().lower()
        items: List[Dict[str, Any]] = []

        for current_snapshot in latest_profiles.values():
            is_favorite = (
                current_snapshot["profile_url"].strip().lower() in favorite_urls
            )
            if favorites_only and not is_favorite:
                continue

            for review in current_snapshot["reviews"]:
                if review.get("doctor_reply"):
                    continue
                published = _review_date(review)
                if not _in_review_range(published, review_start, review_end):
                    undated_excluded += int(published is None)
                    continue
                item = {
                    "profile_id": current_snapshot["profile_id"],
                    "snapshot": current_snapshot["filename"],
                    "doctor_name": current_snapshot["doctor_name"],
                    "profile_url": current_snapshot["profile_url"],
                    "review_id": str(review.get("id") or ""),
                    "author": review.get("author") or "Paciente",
                    "comment": review.get("comment") or review.get("text") or "",
                    "rating": review.get("rating"),
                    "date": review.get("date"),
                    "review_date": published.isoformat() if published else None,
                    "collected_at": current_snapshot["extracted_at"],
                    "generated_response": review.get("generated_response"),
                    "is_favorite": is_favorite,
                }
                if query and query not in json.dumps(item, ensure_ascii=False).lower():
                    continue
                items.append(item)

        items.sort(
            key=lambda item: (item["date"] or "", item["doctor_name"]), reverse=True
        )
        start, end, pagination = _page_bounds(len(items), page, page_size)
        selected = (
            next(iter(latest_profiles.values()), None) if snapshot is not None else None
        )
        return {
            "snapshot": (
                {
                    "filename": selected["filename"],
                    "collection": selected.get("collection"),
                    "reviews_count": len(selected["reviews"]),
                    "unanswered_count": selected["unanswered_count"],
                    "generated_count": selected["generated_count"],
                }
                if selected
                else None
            ),
            "summary": {
                "pending_reviews": len(items),
                "profiles_with_pending": len({item["profile_id"] for item in items}),
                "favorite_pending": sum(1 for item in items if item["is_favorite"]),
                "generated_ready": sum(
                    1 for item in items if item.get("generated_response")
                ),
                "undated_excluded": undated_excluded,
            },
            "date_filters": {
                "collected_from": date_from,
                "collected_to": date_to,
                "review_date_from": (
                    review_start.isoformat() if review_start else None
                ),
                "review_date_to": review_end.isoformat() if review_end else None,
            },
            "pagination": pagination,
            # Profiles whose current data comes from an incomplete collection,
            # so operators know the queue may be missing reviews.
            "incomplete_collections": [
                {
                    "profile_id": current["profile_id"],
                    "doctor_name": current["doctor_name"],
                    "status": current["collection"].get("status"),
                    "expected_count": current["collection"].get("expected_count"),
                    "extracted_count": current["collection"].get(
                        "extracted_count", len(current["reviews"])
                    ),
                    "stop_reason": current["collection"].get("stop_reason"),
                }
                for current in latest_profiles.values()
                if isinstance(current.get("collection"), dict)
                and current["collection"].get("status") != "complete"
            ],
            "items": items[start:end],
            "filters": self.build_filter_options(
                list(latest_profiles.values()) or snapshots
            ),
        }

    def get_reports(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        favorite_profiles: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        snapshots = self._filter_snapshots(
            self._load_snapshots(),
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
        )
        history = self.get_history(
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
        )
        overview = self.get_overview(
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
            favorite_profiles=favorite_profiles,
        )
        profiles = self.list_profiles(
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
            favorite_profiles=favorite_profiles,
        )
        latest_profiles = self._latest_by_profile(snapshots)
        extracted_values = [
            extracted_at
            for extracted_at in (snapshot.get("extracted_at") for snapshot in snapshots)
            if isinstance(extracted_at, str) and extracted_at
        ]
        latest_snapshot_at = max(
            extracted_values,
            default=None,
        )
        oldest_snapshot_at = min(
            extracted_values,
            default=None,
        )
        cleanup_candidates: List[Dict[str, Any]] = []
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for snapshot in snapshots:
            grouped.setdefault(snapshot["profile_id"], []).append(snapshot)

        for current_profile_id, profile_snapshots in grouped.items():
            latest = latest_profiles.get(current_profile_id)
            if latest is None or len(profile_snapshots) <= 1:
                continue
            outdated = sum(
                1
                for snapshot in profile_snapshots
                if not self._is_snapshot_latest(snapshot, latest_profiles)
                and not (
                    isinstance(snapshot.get("collection"), dict)
                    and snapshot["collection"].get("status") != "complete"
                )
            )
            if outdated <= 0:
                continue
            cleanup_candidates.append(
                {
                    "profile_id": current_profile_id,
                    "doctor_name": latest["doctor_name"],
                    "profile_url": latest["profile_url"],
                    "outdated_snapshots": outdated,
                    "total_snapshots": len(profile_snapshots),
                }
            )

        return {
            "summary": {
                "total_files": history["summary"]["total_snapshots"],
                "profiles_tracked": len(
                    {snapshot["profile_id"] for snapshot in snapshots}
                ),
                "storage_used_bytes": history["summary"]["storage_used_bytes"],
                "storage_used_human": history["summary"]["storage_used_human"],
                "outdated_snapshots": history["summary"]["outdated_snapshots"],
                "latest_snapshot_at": latest_snapshot_at,
                "oldest_snapshot_at": oldest_snapshot_at,
                "total_reviews_current": overview["summary"]["total_reviews_current"],
                "unanswered_current": overview["summary"]["unanswered_reviews_current"],
                "generated_current": overview["summary"][
                    "generated_suggestions_current"
                ],
                "average_rating_current": overview["summary"]["average_rating_current"],
            },
            "timeline": overview["timeline"],
            "top_profiles": profiles[:8],
            "cleanup_candidates": sorted(
                cleanup_candidates,
                key=lambda item: (
                    -item["outdated_snapshots"],
                    item["doctor_name"].lower(),
                ),
            )[:8],
            "inventory": history["entries"][:200],
            "filters": history["filters"],
        }

    def draft_revision(self, profile_id: str) -> int:
        """Read the current edit revision while holding the publication lock."""
        with snapshot_lock(self.data_dir):
            snapshots = self._filter_snapshots(
                self._load_snapshots(), profile_id=profile_id
            )
            return max(
                (
                    review["draft_edit"]["version"]
                    for item in snapshots
                    for review in item["reviews"]
                    if isinstance(review.get("draft_edit"), dict)
                    and type(review["draft_edit"].get("version")) is int
                ),
                default=0,
            )

    def save_generated_response(
        self,
        profile_id: str,
        review_id: str,
        generated_response: str,
        snapshot: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with snapshot_lock(self.data_dir):
            return self._save_generated_response_locked(
                profile_id, review_id, generated_response, snapshot
            )

    def _save_generated_response_locked(
        self,
        profile_id: str,
        review_id: str,
        generated_response: str,
        snapshot: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        snapshots = self._filter_snapshots(
            self._load_snapshots(), profile_id=profile_id
        )
        latest = (
            self._select_snapshot(snapshots, profile_id, snapshot)
            if snapshot is not None
            else self._latest_by_profile(snapshots).get(profile_id)
        )
        if latest is None:
            return None

        file_path = Path(latest["file_path"])
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                payload = json.load(file)

            matches = [
                review
                for review in payload.get("reviews", [])
                if str(review.get("id") or "") == str(review_id)
            ]
            if len(matches) != 1:
                return None
            versions = [
                review.get("draft_edit", {}).get("version", 0)
                for item in snapshots
                for review in item["reviews"]
                if isinstance(review.get("draft_edit"), dict)
                and type(review["draft_edit"].get("version")) is int
            ]
            matches[0]["generated_response"] = generated_response
            matches[0]["draft_edit"] = {
                "version": max(versions, default=0) + 1,
                "cleared": not bool(generated_response),
            }

            write_json_atomic(file_path, payload)

            return {
                "profile_id": profile_id,
                "review_id": review_id,
                "file": file_path.name,
                "generated_response": generated_response,
            }
        except Exception as exc:
            self.logger.error(
                "Error saving generated response to %s: %s", file_path, exc
            )
            return None

    def delete_snapshot(self, filename: str) -> Optional[Dict[str, Any]]:
        with snapshot_lock(self.data_dir):
            return self._delete_snapshot_locked(filename)

    def _delete_snapshot_locked(self, filename: str) -> Optional[Dict[str, Any]]:
        filename = Path(filename).name
        history = self.get_history()
        target = next(
            (entry for entry in history["entries"] if entry["filename"] == filename),
            None,
        )
        if target is None:
            return None

        file_path = self.data_dir / filename
        if not file_path.exists():
            return None

        file_size = file_path.stat().st_size
        file_path.unlink()
        return {
            "filename": filename,
            "doctor_name": target["doctor_name"],
            "profile_id": target["profile_id"],
            "deleted_bytes": file_size,
            "deleted_size_human": self._format_file_size(file_size),
        }

    def prune_outdated_snapshots(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        with snapshot_lock(self.data_dir):
            return self._prune_outdated_snapshots_locked(profile_id, date_from, date_to)

    def _prune_outdated_snapshots_locked(
        self,
        profile_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = self.get_history(
            profile_id=profile_id,
            date_from=date_from,
            date_to=date_to,
            status="outdated",
        )
        deleted_files: List[Dict[str, Any]] = []
        deleted_bytes = 0
        profiles_affected: set[str] = set()

        for entry in history["entries"]:
            deleted = self.delete_snapshot(entry["filename"])
            if deleted is None:
                continue
            deleted_files.append(deleted)
            deleted_bytes += deleted["deleted_bytes"]
            profiles_affected.add(deleted["profile_id"])

        return {
            "deleted_count": len(deleted_files),
            "deleted_bytes": deleted_bytes,
            "deleted_size_human": self._format_file_size(deleted_bytes),
            "profiles_affected": len(profiles_affected),
            "files": deleted_files,
        }
