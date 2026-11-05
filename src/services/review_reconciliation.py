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


def reconcile_snapshot_drafts(
    reviews: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    generation_revision: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Resolve legacy collection chronology, then explicitly versioned edits."""
    from src.services.workspace_service import _comparable_datetime

    timestamps = [item.get("extracted_ts") for item in snapshots]
    if timestamps and all(value is not None for value in timestamps):
        ordered_times = [_comparable_datetime(value) for value in timestamps]
        if len(set(ordered_times)) == len(ordered_times):
            ordered = sorted(
                snapshots,
                key=lambda item: _comparable_datetime(item["extracted_ts"]),
                reverse=True,
            )
            result = carry_forward_historical_drafts(
                reviews, [item["reviews"] for item in ordered]
            )
        else:
            result = [dict(review) for review in reviews]
    else:
        result = [dict(review) for review in reviews]

    max_revision = max(
        (
            item["draft_edit"]["version"]
            for snapshot in snapshots
            for item in snapshot["reviews"]
            if isinstance(item.get("draft_edit"), dict)
            and type(item["draft_edit"].get("version")) is int
        ),
        default=0,
    )
    candidates: List[List[tuple[int, Dict[str, Any]]]] = [[] for _ in reviews]
    target_counts = Counter(str(review.get("id") or "") for review in reviews)
    unsafe: set[str] = {
        review_id
        for review_id, count in target_counts.items()
        if review_id.startswith("doctoralia:") and count > 1
    }
    for snapshot in snapshots:
        counts = Counter(str(item.get("id") or "") for item in snapshot["reviews"])
        unsafe.update(
            review_id
            for review_id, count in counts.items()
            if review_id.startswith("doctoralia:") and count > 1
        )
    for index, review in enumerate(reviews):
        review_id = str(review.get("id") or "")
        if review_id.startswith("ambiguous:") or review_id in unsafe:
            result[index] = dict(review)
    for snapshot in snapshots:
        previous = snapshot["reviews"]
        marked = []
        for index, old in enumerate(previous):
            item = dict(old)
            item["generated_response"] = str(index + 1)
            marked.append(item)
        targets = [dict(review, generated_response="") for review in reviews]
        matched = carry_forward_drafts(targets, marked)
        for index, item in enumerate(matched):
            review_id = str(reviews[index].get("id") or "")
            if review_id in unsafe or review_id.startswith("ambiguous:"):
                continue
            marker = item.get("generated_response")
            if not marker:
                continue
            old = previous[int(marker) - 1]
            metadata = old.get("draft_edit")
            if isinstance(metadata, dict) and type(metadata.get("version")) is int:
                candidates[index].append((metadata["version"], old))

    for index, choices in enumerate(candidates):
        if not choices:
            continue
        newest = max(version for version, _ in choices)
        winners = [old for version, old in choices if version == newest]
        states = {
            (
                str(old.get("generated_response") or ""),
                bool(old["draft_edit"].get("cleared")),
            )
            for old in winners
        }
        if len(states) != 1:
            result[index] = dict(reviews[index])
            continue
        # A requested generation started after the edit may create a new draft.
        if (
            generation_revision is not None
            and newest <= generation_revision
            and reviews[index].get("generated_response")
        ):
            result[index]["draft_edit"] = {
                "version": max_revision + 1,
                "cleared": False,
            }
            continue
        old = winners[0]
        result[index]["draft_edit"] = dict(old["draft_edit"])
        if old["draft_edit"].get("cleared"):
            result[index]["generated_response"] = ""
        else:
            result[index]["generated_response"] = old.get("generated_response", "")
    return result
