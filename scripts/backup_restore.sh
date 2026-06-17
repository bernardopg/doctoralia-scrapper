#!/usr/bin/env bash
#
# Backup and restore for Doctoralia Scrapper.
#
# Backs up (and restores) everything needed to rebuild operational state:
#   - data/            extractions, responses, logs, snapshots
#   - src/config/      config.json (and example)
#   - .env             secrets / runtime configuration
#   - Redis            full RDB dump (job queue, metrics, notifications)
#   - n8n              exported workflows + credentials (when n8n is running)
#
# Redis and n8n are read from the running Docker Compose stack. When the stack
# is not up, those parts are skipped with a warning and the file backup still
# succeeds.
#
# Usage:
#   scripts/backup_restore.sh backup            # create a new backup
#   scripts/backup_restore.sh list              # list existing backups
#   scripts/backup_restore.sh restore <file>    # restore from a backup
#   scripts/backup_restore.sh verify <file>     # validate a backup (no changes)
#   scripts/backup_restore.sh cleanup           # keep only the 5 newest
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

DATA_DIR="$PROJECT_DIR/data"
CONFIG_DIR="$PROJECT_DIR/src/config"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
KEEP_COUNT=5

# Compose invocation: prefer `docker compose`, fall back to `docker-compose`.
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    COMPOSE=()
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
print_header()  { echo -e "${BLUE}== 💾 Doctoralia Scrapper — Backup & Restore ==${NC}\n"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error()   { echo -e "${RED}❌ $1${NC}" >&2; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_info()    { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Echoes the container id for a compose service, or nothing if not running.
compose_container() {
    local service="$1"
    [ "${#COMPOSE[@]}" -gt 0 ] || return 0
    (cd "$PROJECT_DIR" && "${COMPOSE[@]}" ps -q "$service" 2>/dev/null) || true
}

# Reads REDIS_PASSWORD from .env (empty if unset).
redis_password() {
    [ -f "$ENV_FILE" ] || return 0
    grep -E '^REDIS_PASSWORD=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true
}

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
backup_redis() {
    local dest="$1"
    local cid; cid="$(compose_container redis)"
    if [ -z "$cid" ]; then
        print_warning "Redis container not running — skipping Redis backup"
        return 0
    fi
    print_info "Backing up Redis (RDB snapshot)..."
    local pass; pass="$(redis_password)"
    local auth=(); [ -n "$pass" ] && auth=(-a "$pass" --no-auth-warning)
    # Force a synchronous save so the dump on disk is current.
    if ! docker exec "$cid" redis-cli "${auth[@]}" SAVE >/dev/null 2>&1; then
        print_warning "Redis SAVE failed — dump may be stale"
    fi
    if docker cp "$cid:/data/dump.rdb" "$dest/redis_dump.rdb" 2>/dev/null; then
        print_success "Redis dump saved"
    else
        print_warning "Could not copy Redis dump.rdb"
    fi
}

backup_n8n() {
    local dest="$1"
    local cid; cid="$(compose_container n8n)"
    if [ -z "$cid" ]; then
        print_warning "n8n container not running — skipping n8n backup"
        return 0
    fi
    print_info "Backing up n8n workflows..."
    if docker exec "$cid" n8n export:workflow --all --output=/tmp/n8n_workflows.json >/dev/null 2>&1; then
        docker cp "$cid:/tmp/n8n_workflows.json" "$dest/n8n_workflows.json" 2>/dev/null \
            && print_success "n8n workflows saved" \
            || print_warning "Could not copy n8n workflows"
    else
        print_warning "n8n export returned no workflows (or failed)"
    fi
}

create_backup() {
    mkdir -p "$BACKUP_DIR"
    local backup_file="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
    local temp_dir; temp_dir="$(mktemp -d)"
    trap 'rm -rf "$temp_dir"' RETURN
    local contents="$temp_dir/doctoralia_backup_$TIMESTAMP"
    mkdir -p "$contents"

    if [ -d "$DATA_DIR" ]; then
        print_info "Backing up data/ ..."
        cp -r "$DATA_DIR" "$contents/data"
        print_success "data/ backed up"
    else
        print_warning "data/ not found: $DATA_DIR"
    fi

    if [ -d "$CONFIG_DIR" ]; then
        print_info "Backing up src/config/ ..."
        mkdir -p "$contents/config"
        cp "$CONFIG_DIR"/*.json "$contents/config/" 2>/dev/null || true
        print_success "src/config/ backed up"
    fi

    if [ -f "$ENV_FILE" ]; then
        print_info "Backing up .env ..."
        cp "$ENV_FILE" "$contents/env"
        print_success ".env backed up"
    fi

    backup_redis "$contents"
    backup_n8n "$contents"

    # Manifest used by verify/restore to know what to expect.
    cat > "$contents/backup_info.txt" <<EOF
Doctoralia Scrapper Backup
Created: $(date)
Project Directory: $PROJECT_DIR
Backup Timestamp: $TIMESTAMP

Contents:
$([ -d "$contents/data" ]    && echo "- data directory")
$([ -d "$contents/config" ]  && echo "- src/config")
$([ -f "$contents/env" ]     && echo "- .env")
$([ -f "$contents/redis_dump.rdb" ]   && echo "- Redis dump.rdb")
$([ -f "$contents/n8n_workflows.json" ] && echo "- n8n workflows")
EOF

    print_info "Creating compressed archive..."
    tar -czf "$backup_file" -C "$temp_dir" "doctoralia_backup_$TIMESTAMP"

    print_success "Backup created: $backup_file ($(du -h "$backup_file" | cut -f1))"
    print_info "Validate it with: $0 verify $backup_file"
}

# ---------------------------------------------------------------------------
# Verify (no side effects) — extracts to a temp dir and checks integrity.
# ---------------------------------------------------------------------------
verify_backup() {
    local backup_file="$1"
    [ -f "$backup_file" ] || { print_error "Backup file not found: $backup_file"; exit 1; }

    print_info "Verifying archive integrity..."
    if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
        print_error "Archive is corrupt or not a valid tar.gz"
        exit 1
    fi
    print_success "Archive is a readable tar.gz"

    local temp_dir; temp_dir="$(mktemp -d)"
    trap 'rm -rf "$temp_dir"' RETURN
    tar -xzf "$backup_file" -C "$temp_dir"

    local contents; contents="$(find "$temp_dir" -maxdepth 1 -name 'doctoralia_backup_*' -type d | head -1)"
    if [ -z "$contents" ]; then
        print_error "Invalid backup structure (missing doctoralia_backup_* root)"
        exit 1
    fi

    if [ ! -f "$contents/backup_info.txt" ]; then
        print_error "Missing manifest backup_info.txt"
        exit 1
    fi
    print_success "Manifest present"

    local ok=0
    # Validate Redis dump magic header (REDISxxxx) when present.
    if [ -f "$contents/redis_dump.rdb" ]; then
        if [ "$(head -c 5 "$contents/redis_dump.rdb")" = "REDIS" ]; then
            print_success "Redis dump has valid RDB header"
        else
            print_error "Redis dump present but header is not 'REDIS'"
            ok=1
        fi
    fi
    # Validate n8n export is valid JSON when present.
    if [ -f "$contents/n8n_workflows.json" ]; then
        if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$contents/n8n_workflows.json" 2>/dev/null; then
            print_success "n8n workflows are valid JSON"
        else
            print_error "n8n workflows file is not valid JSON"
            ok=1
        fi
    fi
    # Validate config.json is valid JSON when present.
    if [ -f "$contents/config/config.json" ]; then
        if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$contents/config/config.json" 2>/dev/null; then
            print_success "config.json is valid JSON"
        else
            print_error "config.json is not valid JSON"
            ok=1
        fi
    fi

    if [ "$ok" -eq 0 ]; then
        print_success "Backup verified successfully"
    else
        print_error "Backup verification found problems"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------
restore_redis() {
    local contents="$1"
    [ -f "$contents/redis_dump.rdb" ] || return 0
    local cid; cid="$(compose_container redis)"
    if [ -z "$cid" ]; then
        print_warning "Redis not running — skipping Redis restore (dump kept in data/)"
        cp "$contents/redis_dump.rdb" "$DATA_DIR/redis_dump.rdb" 2>/dev/null || true
        return 0
    fi
    print_info "Restoring Redis dump (container will restart)..."
    # Stop Redis BEFORE copying the dump. A running Redis saves its current
    # (post-restore-target) state to dump.rdb on shutdown, which would clobber
    # the file we just copied. Copying while stopped, then starting, makes the
    # restored dump the one Redis loads.
    (cd "$PROJECT_DIR" && "${COMPOSE[@]}" stop redis >/dev/null 2>&1) || docker stop "$cid" >/dev/null
    docker cp "$contents/redis_dump.rdb" "$cid:/data/dump.rdb"
    (cd "$PROJECT_DIR" && "${COMPOSE[@]}" start redis >/dev/null 2>&1) || docker start "$cid" >/dev/null
    print_success "Redis restored"
}

restore_n8n() {
    local contents="$1"
    [ -f "$contents/n8n_workflows.json" ] || return 0
    local cid; cid="$(compose_container n8n)"
    if [ -z "$cid" ]; then
        print_warning "n8n not running — skipping n8n restore"
        return 0
    fi
    print_info "Restoring n8n workflows..."
    docker cp "$contents/n8n_workflows.json" "$cid:/tmp/n8n_workflows.json"
    if docker exec "$cid" n8n import:workflow --input=/tmp/n8n_workflows.json >/dev/null 2>&1; then
        print_success "n8n workflows restored"
    else
        print_warning "n8n import failed"
    fi
}

restore_backup() {
    local backup_file="$1"
    [ -f "$backup_file" ] || { print_error "Backup file not found: $backup_file"; exit 1; }

    # Validate before touching anything.
    verify_backup "$backup_file"

    print_warning "This will overwrite existing data, config, .env, Redis and n8n state."
    read -r -p "Proceed with restore from $(basename "$backup_file")? (y/N): " reply
    [[ "$reply" =~ ^[Yy]$ ]] || { print_info "Restore cancelled"; exit 0; }

    local temp_dir; temp_dir="$(mktemp -d)"
    trap 'rm -rf "$temp_dir"' RETURN
    tar -xzf "$backup_file" -C "$temp_dir"
    local contents; contents="$(find "$temp_dir" -maxdepth 1 -name 'doctoralia_backup_*' -type d | head -1)"

    if [ -d "$contents/data" ]; then
        print_info "Restoring data/ ..."
        mkdir -p "$DATA_DIR"
        # Files written by root-owned containers may not be overwritable by the
        # current user. Force removal of the destination first and report any
        # files that still could not be restored, without aborting the run.
        local failed=0
        while IFS= read -r -d '' src; do
            local rel="${src#"$contents/data/"}"
            local target="$DATA_DIR/$rel"
            mkdir -p "$(dirname "$target")"
            if ! cp --remove-destination "$src" "$target" 2>/dev/null; then
                failed=$((failed + 1))
            fi
        done < <(find "$contents/data" -type f -print0)
        if [ "$failed" -eq 0 ]; then
            print_success "data/ restored"
        else
            print_warning "data/ restored with $failed file(s) skipped (permission denied — run with sudo or fix ownership)"
        fi
    fi
    if [ -d "$contents/config" ]; then
        print_info "Restoring src/config/ ..."
        mkdir -p "$CONFIG_DIR"
        cp "$contents/config/"*.json "$CONFIG_DIR/" 2>/dev/null || true
        print_success "src/config/ restored"
    fi
    if [ -f "$contents/env" ]; then
        print_info "Restoring .env ..."
        cp "$contents/env" "$ENV_FILE"
        print_success ".env restored"
    fi

    restore_redis "$contents"
    restore_n8n "$contents"

    print_success "Restore complete"
}

# ---------------------------------------------------------------------------
# List / cleanup
# ---------------------------------------------------------------------------
list_backups() {
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(find "$BACKUP_DIR" -name 'backup_*.tar.gz' 2>/dev/null)" ]; then
        print_warning "No backups found in $BACKUP_DIR"
        return
    fi
    echo "📁 $BACKUP_DIR"
    find "$BACKUP_DIR" -name 'backup_*.tar.gz' -printf '%T@ %p\n' | sort -n | while read -r ts file; do
        printf '   📦 %s - %s (%s)\n' \
            "$(date -d "@${ts%.*}" '+%Y-%m-%d %H:%M:%S')" \
            "$(basename "$file")" "$(du -h "$file" | cut -f1)"
    done
}

cleanup_old_backups() {
    [ -d "$BACKUP_DIR" ] || { print_warning "No backup directory"; return; }
    local old
    old="$(find "$BACKUP_DIR" -name 'backup_*.tar.gz' -printf '%T@ %p\n' | sort -n | head -n "-$KEEP_COUNT" | cut -d' ' -f2-)"
    [ -n "$old" ] || { print_info "No old backups to remove (keeping $KEEP_COUNT)"; return; }
    echo "$old" | while read -r file; do
        [ -f "$file" ] && rm "$file" && print_info "Removed $(basename "$file")"
    done
    print_success "Old backups cleaned (kept $KEEP_COUNT newest)"
}

show_usage() {
    print_header
    cat <<EOF
Usage: $0 {backup|list|restore <file>|verify <file>|cleanup|help}

  backup           Create a new backup (data, config, .env, Redis, n8n)
  list             List available backups
  restore <file>   Validate then restore from a backup
  verify <file>    Validate a backup archive without changing anything
  cleanup          Remove old backups, keeping the $KEEP_COUNT newest
EOF
}

case "${1:-help}" in
    backup)  print_header; create_backup ;;
    list)    print_header; list_backups ;;
    restore) [ -n "${2:-}" ] || { print_error "Specify a backup file"; exit 1; }; print_header; restore_backup "$2" ;;
    verify)  [ -n "${2:-}" ] || { print_error "Specify a backup file"; exit 1; }; print_header; verify_backup "$2" ;;
    cleanup) print_header; cleanup_old_backups ;;
    help|*)  show_usage ;;
esac
