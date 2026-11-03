"""Crash-safe publication of JSON snapshots on the same filesystem."""

import json
import os
import stat
import threading
import uuid
from pathlib import Path
from typing import Any

from filelock import FileLock

_locks_guard = threading.Lock()
_locks: dict[Path, FileLock] = {}


def snapshot_lock(data_dir: Path) -> FileLock:
    """Share one reentrant, cross-process lock per snapshot directory."""
    directory = Path(data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with _locks_guard:
        if directory not in _locks:
            _locks[directory] = FileLock(directory / ".snapshots.lock", mode=0o666)
        return _locks[directory]


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write a complete temporary file before atomically replacing the target."""
    path = Path(path)
    with snapshot_lock(path.parent):
        _write_json_atomic_locked(path, payload)


def _write_json_atomic_locked(path: Path, payload: Any) -> None:
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    temporary = path.parent / f".snapshot-{uuid.uuid4().hex}.tmp"
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if previous_mode is not None:
                os.chmod(temporary, previous_mode)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
