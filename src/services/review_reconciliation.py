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
        if review_id.startswith("ambiguous:"):
            result.append(copy)
            continue
        if (
            review_id.startswith("doctoralia:")
            and old_ids[review_id] == new_ids[review_id] == 1
        ):
            old = old_by_id[review_id]
        elif review_key and old_counts[review_key] == new_counts[review_key] == 1:
            candidate = old_by_key[review_key]
            candidate_id = str(candidate.get("id") or "")
            if not (
                candidate_id.startswith("ambiguous:")
                or (
                    review_id.startswith("doctoralia:")
                    and candidate_id.startswith("doctoralia:")
                )
            ):
                old = candidate
        if old and old.get("generated_response") and not copy.get("generated_response"):
            copy["generated_response"] = old["generated_response"]
        result.append(copy)
    return result


def carry_forward_historical_drafts(
    reviews: List[Dict[str, Any]], history: List[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Recover older drafts only for unambiguous, stable source identities.

    Snapshots must be supplied from newest to oldest, independently of
    which snapshot is preferred for display. A prior occurrence without a draft is authoritative
    and must not resurrect an older draft.
    """
    if not history:
        return [dict(review) for review in reviews]

    result = carry_forward_drafts(reviews, history[0])
    target_ids = Counter(str(review.get("id") or "") for review in reviews)
    targets = {str(review.get("id") or ""): review for review in result}
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    newer_has_legacy_ids = False

    for index, snapshot in enumerate(history):
        counts = Counter(str(review.get("id") or "") for review in snapshot)
        for old in snapshot:
            old_id = str(old.get("id") or "")
            old_key = (
                str(old.get("author") or "").strip(),
                str(old.get("comment") or old.get("text") or "").strip(),
            )
            if (
                index > 0
                and old_id.startswith("doctoralia:")
                and old_id not in seen_ids
                and not newer_has_legacy_ids
                and counts[old_id] == target_ids[old_id] == 1
                and old_key not in seen_keys
                and old.get("generated_response")
            ):
                target = targets[old_id]
                if not target.get("generated_response"):
                    target["generated_response"] = old["generated_response"]
        seen_ids.update(counts)
        newer_has_legacy_ids = newer_has_legacy_ids or any(
            not str(item.get("id") or "").startswith("doctoralia:") for item in snapshot
        )
        seen_keys.update(
            (
                str(item.get("author") or "").strip(),
                str(item.get("comment") or item.get("text") or "").strip(),
            )
            for item in snapshot
            if item.get("author") and (item.get("comment") or item.get("text"))
        )
    return result
