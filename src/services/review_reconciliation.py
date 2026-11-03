"""Conservative reconciliation of review drafts between snapshots."""

from collections import Counter
from typing import Any, Dict, List, Optional


def carry_forward_drafts(
    reviews: List[Dict[str, Any]], previous: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Preserve drafts only when the old and new review match unambiguously."""

    def key(review: Dict[str, Any]) -> Optional[tuple[str, str]]:
        author = str(review.get("author") or "").strip()
        comment = str(review.get("comment") or review.get("text") or "").strip()
        return (author, comment) if author and comment else None

    old_counts = Counter(key(review) for review in previous)
    new_counts = Counter(key(review) for review in reviews)
    old_ids = Counter(str(review.get("id") or "") for review in previous)
    new_ids = Counter(str(review.get("id") or "") for review in reviews)
    old_by_id = {str(review.get("id") or ""): review for review in previous}
    old_by_key = {key(review): review for review in previous}
    result = []
    for review in reviews:
        copy = dict(review)
        review_id = str(review.get("id") or "")
        review_key = key(review)
        old = None
        if (
            review_id.startswith("doctoralia:")
            and old_ids[review_id] == new_ids[review_id] == 1
        ):
            old = old_by_id[review_id]
        elif review_key and old_counts[review_key] == new_counts[review_key] == 1:
            candidate = old_by_key[review_key]
            candidate_id = str(candidate.get("id") or "")
            if not (
                review_id.startswith("doctoralia:")
                and candidate_id.startswith("doctoralia:")
            ):
                old = candidate
        if old and old.get("generated_response") and not copy.get("generated_response"):
            copy["generated_response"] = old["generated_response"]
        result.append(copy)
    return result
