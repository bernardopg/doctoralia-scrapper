# Snapshot migration (opt in)

The running application still reads and writes JSON. Database reconciliation does
not switch runtime repositories or resolve conflicts. Apply the database
migrations first (`python -m src.db.init_db init`), and use the workspace ID of an
existing workspace. Back up the database as well as the snapshots before any
write; test the restore. Keep the snapshot backup outside the source directory.
The staging command makes content-addressed copies and verifies existing copies.
Protect backups and the database as they contain review and draft content.

Rehearse with a disposable PostgreSQL and copies of anonymized snapshots:

```sh
export DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@HOST/DB'
python -m src.db.init_db init
# Inspection only: no database write or backup.
python -m src.db.snapshot_import --data-dir /path/to/snapshot-copies
# Explicit staging, after reviewing the report and making a database backup.
python -m src.db.snapshot_import --data-dir /path/to/snapshot-copies --workspace-id WORKSPACE_ID --backup-dir /path/to/backup --apply
# Separate opt-in write: reconcile already staged snapshots for one workspace.
python -m src.db.snapshot_reconcile --workspace-id WORKSPACE_ID
```

Reconciliation verifies the staged SHA-256, then commits one staged snapshot per
transaction. PostgreSQL advisory transaction locks serialize imports per
workspace, including overlapping invocations. An unexpected failure rolls back
the current snapshot; previously committed snapshots remain. Rerun the command
to resume. The output sums the persisted outcomes of all staged snapshots in the
workspace: source reviews, newly imported reviews, existing source identities
(duplicates), rejected reviews, pending draft conflicts, and snapshots. It is a
cumulative report, so repeating the command returns the same counts. Stage
additional files and rerun to process them.

Only `doctoralia:` followed by decimal digits identifies a review. Legacy,
fingerprint, ambiguous, missing or repeated source IDs within a snapshot are
rejected individually, including their drafts; no content matching is used.
A source ID repeated in a later snapshot for the same profile creates an
observation, not a new review. Its original observed payload remains available;
review fields are not overwritten. The first imported draft is retained; differing observations, including absent
or empty drafts, create explicit pending conflicts instead of overwriting it.
The newest observation time and value are recorded per review, so older staged
observations cannot create a draft after a newer absence. Equal-time differing
observations are conflicts. If older observations predate the provenance table,
a newly encountered draft is held as a conflict when no active draft exists.
A draft in conflict can remain active until a human
resolves it; inspect conflicts before using drafts. Reviews absent from a partial
snapshot do not imply draft deletion. A human
must inspect `snapshot_rejections` and the original `snapshot_imports` bytes;
there is no conflict-resolution interface yet. Rejected review counts and pending
draft counts measure different things and may not be added as review totals.

Original bytes, filenames, SHA-256 and workspace are retained in staging;
`snapshot_reconciliations` links each snapshot to its run and report, and
`snapshot_rejections` records the index, payload and reason. Raw review payloads
are preserved in observations. A collection timestamp is used as both run start
and finish because the legacy snapshot has no start timestamp; timezone-less
values are rejected as uncertain, without inventing an instant. Supply corrected
source snapshots only when their original timezone is known; the staged originals
remain available. Review datetime values retain their source civil date, without
converting offsets to UTC. Profile URLs are trimmed; case-only differences are
flagged as ambiguous rather than silently merging potentially distinct paths.
Counts outside the PostgreSQL integer range and text containing NUL are rejected;
unsafe rejection payloads refer back to the original staged bytes. A missing collection status is unknown. Invalid
review dates, ratings and text fields are rejected rather than guessed. A
snapshot whose profile or timestamp cannot be normalized is recorded as a
snapshot rejection. This importer does not establish that a partial snapshot is
complete or delete previously observed reviews. Runtime database repositories,
cutover, and human conflict resolution remain future work.

For integration tests use only a PostgreSQL service created for testing: the
suite drops and recreates its schema. Never point it at a real database:

```sh
TEST_POSTGRES_URL='postgresql+asyncpg://USER:PASSWORD@HOST/DISPOSABLE_DB' \
  pytest -q tests/test_review_storage_migrations.py tests/test_snapshot_reconcile.py
```

## Repairing already reconciled installations

Run `python -m src.db.init_db init` before reconciliation, including on a database
that already applied revisions 0003 or 0004. Revision 0005 repairs the missing
provenance from existing observations and records unresolved legacy histories as
explicit draft rejections. It preserves active drafts, original observations and
staged bytes; it does not approve or choose a draft on the operator's behalf.
Missing provenance is reconstructed from the newest observed collection time.
Conflicting or insufficient observations and legacy timezone uncertainty require
human review. Each observation must exactly match the unique item with its source
ID in the staged original. Missing, duplicate or divergent source items make
observation integrity uncertain and require review; a partial object containing
only an ID is not evidence of draft removal. Repair markers contain integrity
flags, not copies of review or draft text. Existing draft rejections are preserved without a second pending
entry for the same review. The cumulative pending report increases only when a
previously unreported legacy uncertainty is discovered.

The repair serializes each workspace with the same advisory lock as reconciliation.
Migration failure rolls back the repair; rerunning initialization resumes safely.
Repeated initialization and downgrade/re-upgrade preserve the audit records and
do not duplicate pending counts. A schema downgrade intentionally does not undo
these data repairs; returning to the original data requires the verified database
backup. Future runtime repositories must exclude unresolved drafts from approved
response flows even when an old draft remains physically stored.

The upgrade regression creates legacy observations and cached reports at revision
0003 or 0004 in a disposable PostgreSQL, then applies the actual Alembic upgrade.
It covers removal, mixed existing provenance, separate workspaces, existing
conflicts, chronology independent of staging order, repeated/concurrent startup,
legacy timezone uncertainty and failure/rollback/resume. Run the schema tests
first because their PostgreSQL check requires an empty disposable database:

```sh
TEST_POSTGRES_URL='postgresql+asyncpg://USER:PASSWORD@HOST/DISPOSABLE_DB' \
  pytest -q tests/test_review_storage_migrations.py tests/test_snapshot_import.py \
  tests/test_snapshot_reconcile.py tests/test_snapshot_upgrade.py
```

## Resolving draft conflicts (opt in)

Reconciliation records a `draft` rejection whenever observations of the same
review disagree; it never overwrites the first imported draft. Migration
`0006_draft_resolution` links each draft rejection to its review when a stable
identifier allows it (the review ID recorded by the legacy repair, or the
snapshot profile plus the `doctoralia:` source ID). Rejections without such an
identifier stay listed as `unlinked`; no association is inferred.

```sh
# Every review with pending draft conflicts, its observations and decisions.
python -m src.db.draft_resolution list --workspace-id WORKSPACE_ID
# One review.
python -m src.db.draft_resolution list --workspace-id WORKSPACE_ID --review-id REVIEW_ID
# Record a decision. --expected-revision is the revision shown by `list`.
python -m src.db.draft_resolution resolve --workspace-id WORKSPACE_ID \
  --review-id REVIEW_ID --decision keep|choose|clear --actor NAME \
  --expected-revision N [--rejection-id REJECTION_ID] [--note TEXT]
```

- `keep` keeps the current draft (or its absence), `choose` adopts the draft
  proposed by one pending conflict (`--rejection-id`), `clear` removes the draft.
  One decision resolves every pending conflict of the review.
- A decision on an outdated revision fails with exit code 2 and changes
  nothing. Decisions use the same workspace lock as reconciliation.
- `draft_resolutions` is append-only in PostgreSQL (a trigger rejects `UPDATE`
  and `DELETE`). It stores the actor, the previous and resolved drafts, the
  expected and resulting revisions, the resolved rejections and the time.
- A later snapshot with a different draft creates a new pending conflict and
  reopens the review.
- `src.db.draft_resolution.draft_for_review` returns `status: "pending"` and no
  approved body while any conflict is unresolved. The running application still
  reads drafts from JSON; this accessor is for the future database repositories.
- Downgrading below `0006` drops the resolution history. Restore the verified
  database backup instead if it must be kept.
