"""Assign review identifiers without relying on the order of a collection."""

import hashlib
import json
import uuid
from collections import Counter
from typing import Any, Dict, List


def assign_review_identities(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use source IDs, or a content fingerprint when the source has no ID.

    Colliding candidates get ephemeral IDs so they cannot overwrite one another
    or be mistaken for stable identity on a later collection.
    """
    candidates: List[str | None] = []
    for review in reviews:
        source_id = str(review.get("id") or "")
        author = str(review.get("author") or "").strip()
        comment = str(review.get("comment") or "").strip()
        if source_id.startswith("doctoralia:"):
            candidates.append(source_id)
        elif author and comment:
            content = json.dumps(
                [author, comment, str(review.get("date") or "")],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            candidates.append(
                "fingerprint:" + hashlib.sha256(content.encode()).hexdigest()
            )
        else:
            candidates.append(None)

    counts = Counter(candidate for candidate in candidates if candidate)
    result = []
    for review, candidate in zip(reviews, candidates):
        copy = dict(review)
        if not candidate or counts[candidate] != 1:
            copy["id"] = f"ambiguous:{uuid.uuid4().hex}"
            copy["identity_status"] = "ambiguous"
        else:
            copy["id"] = candidate
            copy["identity_status"] = (
                "source" if candidate.startswith("doctoralia:") else "fingerprint"
            )
        result.append(copy)
    return result
