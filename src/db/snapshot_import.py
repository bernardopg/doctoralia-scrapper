"""Safely stage legacy snapshots for a later, explicit reconciliation step."""

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.db.base import database_url
from src.services.snapshot_storage import snapshot_lock


@dataclass(frozen=True)
class Candidate:
    filename: str
    digest: str
    content: bytes
    issues: dict[str, int]


def inspect_snapshots(directory: Path) -> tuple[list[Candidate], list[dict[str, str]]]:
    """Read snapshots under the same lock used by writers, without changing them."""
    if not directory.is_dir():
        raise ValueError("Snapshot directory does not exist")
    candidates: list[Candidate] = []
    rejected: list[dict[str, str]] = []
    with snapshot_lock(directory):
        for path in sorted(directory.glob("*.json")):
            try:
                content = path.read_bytes()
                data = json.loads(content)
                if not isinstance(data, dict) or not isinstance(
                    data.get("reviews"), list
                ):
                    raise ValueError("not a snapshot")
                if not (data.get("extraction_timestamp") or data.get("scraped_at")):
                    raise ValueError("missing collection timestamp")
                doctor = data.get("doctor") or {}
                if not isinstance(doctor, dict) or not (
                    data.get("url") or doctor.get("profile_url")
                ):
                    raise ValueError("missing profile URL")
                reviews = data["reviews"]
                if any(not isinstance(review, dict) for review in reviews):
                    raise ValueError("invalid review entry")
                ids = [str(review.get("id") or "") for review in reviews]
                counts = Counter(
                    value for value in ids if value.startswith("doctoralia:")
                )
                fingerprints = Counter(
                    value for value in ids if value.startswith("fingerprint:")
                )
                identities = Counter(
                    (
                        str(review.get("author") or "").strip(),
                        str(review.get("comment") or review.get("text") or "").strip(),
                    )
                    for review in reviews
                    if review.get("author")
                    and (review.get("comment") or review.get("text"))
                )
                issues = {
                    "duplicate_source_ids": sum(
                        count for count in counts.values() if count > 1
                    ),
                    "duplicate_fingerprints": sum(
                        count for count in fingerprints.values() if count > 1
                    ),
                    "ambiguous_author_comments": sum(
                        count for count in identities.values() if count > 1
                    ),
                    "legacy_or_missing_ids": sum(
                        not value.startswith(
                            ("doctoralia:", "fingerprint:", "ambiguous:")
                        )
                        for value in ids
                    ),
                    "ambiguous_ids": sum(
                        value.startswith("ambiguous:") for value in ids
                    ),
                }
                candidates.append(
                    Candidate(
                        path.name, hashlib.sha256(content).hexdigest(), content, issues
                    )
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                rejected.append({"filename": path.name, "reason": "invalid JSON"})
            except ValueError as exc:
                rejected.append({"filename": path.name, "reason": str(exc)})
            except (OSError, TypeError) as exc:
                rejected.append({"filename": path.name, "reason": type(exc).__name__})
    return candidates, rejected


def backup_snapshots(candidates: list[Candidate], directory: Path) -> None:
    """Store content-addressed copies, never overwriting a pre-existing file."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for candidate in candidates:
        path = directory / (candidate.digest + ".snapshot")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if (
                path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != candidate.digest
            ):
                raise ValueError("Existing backup does not match its checksum")
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(candidate.content)
                stream.flush()
                os.fsync(stream.fileno())
            if hashlib.sha256(path.read_bytes()).hexdigest() != candidate.digest:
                raise ValueError("Written backup does not match its checksum")


async def stage_snapshots(
    engine: AsyncEngine, workspace_id: str, candidates: list[Candidate]
) -> dict[str, int]:
    """Atomically stage files once per workspace and checksum."""
    inserted = 0
    async with engine.begin() as connection:
        exists = await connection.execute(
            text("SELECT 1 FROM workspaces WHERE id = :id"), {"id": workspace_id}
        )
        if not exists.scalar_one_or_none():
            raise ValueError("Workspace does not exist")
        for candidate in candidates:
            result = await connection.execute(
                text(
                    "INSERT INTO snapshot_imports (id, workspace_id, filename, sha256, original_bytes, issue_summary) VALUES (:id, :workspace, :filename, :sha, :content, :issues) ON CONFLICT (workspace_id, sha256) DO NOTHING RETURNING id"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "workspace": workspace_id,
                    "filename": candidate.filename,
                    "sha": candidate.digest,
                    "content": candidate.content,
                    "issues": json.dumps(candidate.issues),
                },
            )
            if result.scalar_one_or_none() is not None:
                inserted += 1
            else:
                existing = await connection.execute(
                    text(
                        "SELECT original_bytes FROM snapshot_imports WHERE workspace_id = :workspace AND sha256 = :sha"
                    ),
                    {"workspace": workspace_id, "sha": candidate.digest},
                )
                if existing.scalar_one() != candidate.content:
                    raise ValueError("Stored snapshot does not match its checksum")
    return {"inserted": inserted, "duplicates": len(candidates) - inserted}


async def run(args: argparse.Namespace) -> dict[str, Any]:
    directory = Path(args.data_dir)
    candidates, rejected = inspect_snapshots(directory)
    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "files": [
            {"filename": item.filename, "sha256": item.digest, "issues": item.issues}
            for item in candidates
        ],
        "rejected": rejected,
    }
    if args.apply:
        if not args.workspace_id or not args.backup_dir:
            raise ValueError("--apply requires --workspace-id and --backup-dir")
        backup = Path(args.backup_dir)
        if backup.resolve() == directory.resolve():
            raise ValueError("Backup directory must differ from snapshot directory")
        backup_snapshots(candidates, backup)
        engine = create_async_engine(database_url(), pool_pre_ping=True)
        try:
            report.update(await stage_snapshots(engine, args.workspace_id, candidates))
        finally:
            await engine.dispose()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--workspace-id")
    parser.add_argument("--backup-dir")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["rejected"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
