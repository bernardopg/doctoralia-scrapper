"""Describe whether a Doctoralia collection reached the advertised total."""

import re
from typing import Optional, cast

from bs4 import BeautifulSoup


def advertised_review_count(html: str) -> Optional[int]:
    """Read the count from the review section; never infer it from comments."""
    section = BeautifulSoup(html, "html.parser").select_one("#profile-reviews")
    if section is None:
        return None
    for element in section.select("p.mb-0"):
        text = element.get_text(" ", strip=True)
        match = re.fullmatch(
            r"(\d+(?:\.\d{3})*)\s+opini(?:ão|ões)", text, re.IGNORECASE
        )
        if match:
            return int(match.group(1).replace(".", ""))
    return None


def collection_info(expected: Optional[int], extracted: int, reason: str) -> dict:
    """Conservatively distinguish verified completion from incomplete results."""
    if reason != "exhausted":
        status = "partial"
    elif expected is None:
        status = "unknown"
    elif extracted == expected:
        status = "complete"
    else:
        status = "partial"
    return {
        "status": status,
        "expected_count": expected,
        "extracted_count": extracted,
        "stop_reason": reason,
    }


def result_status(info: Optional[dict]) -> str:
    """Preserve the legacy contract when completeness metadata is absent."""
    return (
        "partial"
        if info is not None and info.get("status") != "complete"
        else "completed"
    )


def ensure_collection(result: dict) -> dict:
    """Annotate new results from scrapers that cannot verify completeness."""
    if not isinstance(result.get("collection"), dict):
        result["collection"] = {
            "status": "unknown",
            "expected_count": None,
            "extracted_count": len(result.get("reviews") or []),
            "stop_reason": "metadata_unavailable",
            "duration_ms": None,
        }
    return cast(dict, result["collection"])
