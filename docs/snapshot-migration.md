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
review fields are not overwritten. The first imported draft is retained; a
different later draft is recorded as a pending conflict instead of overwriting
it. Processing order follows staging time and ID, not draft recency. A human
must inspect `snapshot_rejections` and the original `snapshot_imports` bytes;
there is no conflict-resolution interface yet. Rejected review counts and pending
draft counts measure different things and may not be added as review totals.

Original bytes, filenames, SHA-256 and workspace are retained in staging;
`snapshot_reconciliations` links each snapshot to its run and report, and
`snapshot_rejections` records the index, payload and reason. Raw review payloads
are preserved in observations. A collection timestamp is used as both run start
and finish because the legacy snapshot has no start timestamp; timezone-less
values are interpreted as UTC. A missing collection status is unknown. Invalid
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
