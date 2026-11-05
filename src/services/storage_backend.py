"""Select the review storage backend (``json`` by default, ``postgres`` opt-in).

Environment:

* ``STORAGE_BACKEND``: ``json`` (default) or ``postgres``.
* ``STORAGE_WORKSPACE``: workspace slug or id used by the database backend
  (default ``default``, created by ``python -m src.db.init_db init-and-seed``).
* ``DATABASE_URL``: PostgreSQL connection string.

JSON snapshots are written in both modes. See ``docs/storage-postgres.md`` for
the cutover and rollback procedure.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.services.snapshot_storage import snapshot_lock, write_json_atomic

logger = logging.getLogger(__name__)

_runner: Any = None
_workspace_id: Optional[str] = None
_state_lock = threading.Lock()
_last_sync: Dict[str, Any] = {"status": "never", "at": None, "error": None}


def backend() -> str:
    value = os.environ.get("STORAGE_BACKEND", "json").strip().lower()
    return "postgres" if value in {"postgres", "postgresql"} else "json"


def is_postgres() -> bool:
    return backend() == "postgres"


def _runtime() -> Tuple[Any, str]:
    """Return the shared runner and the resolved workspace id."""
    global _runner, _workspace_id
    from src.db.review_store import StorageRunner, workspace_id_for

    with _state_lock:
        if _runner is None:
            _runner = StorageRunner()
        runner = _runner
    if _workspace_id is None:
        slug = os.environ.get("STORAGE_WORKSPACE", "default")
        resolved = runner.run(lambda engine: workspace_id_for(engine, slug))
        with _state_lock:
            _workspace_id = resolved
    assert _workspace_id is not None
    return runner, _workspace_id


def reset() -> None:
    """Forget the runner and workspace (tests and configuration reloads)."""
    global _runner, _workspace_id
    with _state_lock:
        runner, _runner, _workspace_id = _runner, None, None
    if runner is not None:
        runner.close()


def status() -> Dict[str, Any]:
    return {"backend": backend(), "last_sync": dict(_last_sync)}


def sync_after_publish(data_dir: Path) -> Optional[Dict[str, Any]]:
    """Mirror the snapshot directory into PostgreSQL after a JSON publication.

    The JSON snapshot is already durable, so a database failure is logged and
    reported by :func:`status` instead of failing the collection. Staging is
    idempotent: the next successful synchronisation catches up.
    """
    if not is_postgres():
        return None
    from src.db.review_store import sync_directory

    at = datetime.now(timezone.utc).isoformat()
    try:
        runner, workspace = _runtime()
        report: Dict[str, Any] = runner.run(
            lambda engine: sync_directory(engine, workspace, Path(data_dir))
        )
    except Exception as exc:  # noqa: BLE001 - reported, JSON remains durable
        logger.error("PostgreSQL synchronisation failed: %s", type(exc).__name__)
        _last_sync.update(status="failed", at=at, error=type(exc).__name__)
        return None
    _last_sync.update(status="ok", at=at, error=None)
    return report


def load_snapshot_payloads() -> List[Dict[str, Any]]:
    from src.db.review_store import load_snapshot_payloads as load

    runner, workspace = _runtime()
    payloads: List[Dict[str, Any]] = runner.run(lambda engine: load(engine, workspace))
    return payloads


def ensure_draft_editable(profile_url: str, source_id: str) -> None:
    """Raise ``PendingDraftConflict`` when the database withholds the draft."""
    from src.db.review_store import StorageError, save_draft

    runner, workspace = _runtime()
    try:
        runner.run(
            lambda engine: save_draft(
                engine, workspace, profile_url, source_id, None, 0, check_only=True
            )
        )
    except StorageError as exc:
        if type(exc).__name__ == "PendingDraftConflict":
            raise
        # Reviews not stored in the database (no stable identity) stay JSON-only.
        logger.info("Draft edit not mirrored: %s", exc)


def record_draft(
    profile_url: str, source_id: str, body: Optional[str], edit_version: int
) -> None:
    from src.db.review_store import StorageError, save_draft

    try:
        runner, workspace = _runtime()
        runner.run(
            lambda engine: save_draft(
                engine, workspace, profile_url, source_id, body, edit_version
            )
        )
    except StorageError as exc:
        if type(exc).__name__ == "PendingDraftConflict":
            raise
        logger.info("Draft edit not mirrored: %s", exc)
    except Exception as exc:  # noqa: BLE001 - JSON already holds the edit
        logger.error("Draft edit not mirrored to PostgreSQL: %s", type(exc).__name__)


def export_drafts_to_json(
    data_dir: Path, drafts: Dict[Tuple[str, str], Optional[str]]
) -> Dict[str, int]:
    """Write approved database drafts into the latest JSON snapshot per profile.

    Used after resolving conflicts in the database and before rolling back to
    the JSON backend, so no edit is lost. Each change gets a new
    ``draft_edit.version`` so later synchronisations accept it as an edit.
    """
    from src.services.workspace_service import WorkspaceService

    data_dir = Path(data_dir)
    updated = unchanged = 0
    files = 0
    with snapshot_lock(data_dir):
        service = WorkspaceService(data_dir)
        snapshots = service._load_json_snapshots()
        latest = service._latest_by_profile(snapshots)
        version = max(
            (
                review["draft_edit"]["version"]
                for snapshot in snapshots
                for review in snapshot["reviews"]
                if isinstance(review.get("draft_edit"), dict)
                and type(review["draft_edit"].get("version")) is int
            ),
            default=0,
        )
        for snapshot in latest.values():
            path = Path(snapshot["file_path"])
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            url = payload.get("url") or (payload.get("doctor") or {}).get(
                "profile_url", ""
            )
            changed = False
            for review in payload.get("reviews", []):
                key = (url, str(review.get("id") or ""))
                if key not in drafts:
                    continue
                body = drafts[key] or ""
                if (review.get("generated_response") or "") == body:
                    unchanged += 1
                    continue
                version += 1
                review["generated_response"] = body
                review["draft_edit"] = {"version": version, "cleared": not body}
                updated += 1
                changed = True
            if changed:
                write_json_atomic(path, payload)
                files += 1
    return {"updated": updated, "unchanged": unchanged, "files": files}
