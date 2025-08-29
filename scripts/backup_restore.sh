#!/bin/bash

# Backup and Restore script for Doctoralia Scraper
# This script handles data backup, configuration backup, and restoration

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
DATA_DIR="$PROJECT_DIR/data"
CONFIG_FILE="$PROJECT_DIR/config/config.json"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                 💾 BACKUP & RESTORE                          ║${NC}"
    echo -e "${BLUE}║                Doctoralia Scraper Data                       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

create_backup() {
    print_info "Creating backup..."

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    # Create backup filename
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"

    # Create temporary directory for backup contents
    TEMP_DIR=$(mktemp -d)
    BACKUP_CONTENTS="$TEMP_DIR/doctoralia_backup_$TIMESTAMP"

    mkdir -p "$BACKUP_CONTENTS"

    # Copy data directory
    if [ -d "$DATA_DIR" ]; then
        print_info "Backing up data directory..."
        cp -r "$DATA_DIR" "$BACKUP_CONTENTS/"
        print_success "Data directory backed up"
    else
        print_warning "Data directory not found: $DATA_DIR"
    fi

    # Copy configuration file
    if [ -f "$CONFIG_FILE" ]; then
        print_info "Backing up configuration..."
        mkdir -p "$BACKUP_CONTENTS/config"
        cp "$CONFIG_FILE" "$BACKUP_CONTENTS/config/"
        print_success "Configuration backed up"
    else
        print_warning "Configuration file not found: $CONFIG_FILE"
    fi

    # Create backup info file
    cat > "$BACKUP_CONTENTS/backup_info.txt" << EOF
Doctoralia Scraper Backup
Created: $(date)
Project Directory: $PROJECT_DIR
Backup Timestamp: $TIMESTAMP

Contents:
$(if [ -d "$DATA_DIR" ]; then echo "- Data directory"; fi)
$(if [ -f "$CONFIG_FILE" ]; then echo "- Configuration file"; fi)

To restore, run:
    tar -xzf $BACKUP_FILE -C /
    # Then run setup.py to reconfigure
EOF

    # Create compressed archive
    print_info "Creating compressed archive..."
    cd "$TEMP_DIR"
    tar -czf "$BACKUP_FILE" "doctoralia_backup_$TIMESTAMP"

    # Cleanup
    cd "$PROJECT_DIR"
    rm -rf "$TEMP_DIR"

    # Calculate backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

    print_success "Backup created successfully!"
    print_info "Backup file: $BACKUP_FILE"
    print_info "Backup size: $BACKUP_SIZE"

    echo ""
    print_info "To restore this backup, run:"
    echo "    $0 restore $BACKUP_FILE"
}

list_backups() {
    print_info "Available backups:"

    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backup directory found: $BACKUP_DIR"
        return
    fi

    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "backup_*.tar.gz" | wc -l)

    if [ "$BACKUP_COUNT" -eq 0 ]; then
        print_warning "No backup files found"
        return
    fi

    echo ""
    echo "📁 Backup Directory: $BACKUP_DIR"
    echo "📊 Total Backups: $BACKUP_COUNT"
    echo ""
    echo "📋 Backup Files:"
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -printf '%T@ %p\n' | sort -n | while read timestamp file; do
        date_str=$(date -d "@${timestamp%.*}" '+%Y-%m-%d %H:%M:%S')
        size=$(du -h "$file" | cut -f1)
        filename=$(basename "$file")
        echo "   📦 $date_str - $filename (${size})"
    done
}

restore_backup() {
    BACKUP_FILE="$1"

    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    print_warning "⚠️ This will overwrite existing data!"
    read -p "Are you sure you want to restore from $BACKUP_FILE? (y/N): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Restore cancelled"
        exit 0
    fi

    print_info "Restoring from backup..."

    # Create temporary directory for extraction
    TEMP_DIR=$(mktemp -d)

    # Extract backup
    print_info "Extracting backup..."
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

    # Find the backup contents directory
    BACKUP_CONTENTS=$(find "$TEMP_DIR" -name "doctoralia_backup_*" -type d | head -1)

    if [ -z "$BACKUP_CONTENTS" ]; then
        print_error "Invalid backup file structure"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    # Show backup info
    if [ -f "$BACKUP_CONTENTS/backup_info.txt" ]; then
        echo ""
        print_info "Backup Information:"
        cat "$BACKUP_CONTENTS/backup_info.txt" | sed 's/^/   /'
        echo ""
    fi

    # Restore data directory
    if [ -d "$BACKUP_CONTENTS/data" ]; then
        print_info "Restoring data directory..."
        mkdir -p "$DATA_DIR"
        cp -r "$BACKUP_CONTENTS/data"/* "$DATA_DIR/" 2>/dev/null || true
        print_success "Data directory restored"
    fi

    # Restore configuration
    if [ -d "$BACKUP_CONTENTS/config" ] && [ -f "$BACKUP_CONTENTS/config/config.json" ]; then
        print_info "Restoring configuration..."
        mkdir -p "$(dirname "$CONFIG_FILE")"
        cp "$BACKUP_CONTENTS/config/config.json" "$CONFIG_FILE"
        print_success "Configuration restored"
        print_warning "You may need to reconfigure Telegram settings"
    fi

    # Cleanup
    rm -rf "$TEMP_DIR"

    print_success "Backup restored successfully!"
    print_info "You may want to run setup.py to verify configuration"
}

cleanup_old_backups() {
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backup directory found"
        return
    fi

    # Keep only the 5 most recent backups
    KEEP_COUNT=5
    BACKUP_FILES=$(find "$BACKUP_DIR" -name "backup_*.tar.gz" -printf '%T@ %p\n' | sort -n | head -n -$KEEP_COUNT | cut -d' ' -f2-)

    if [ -z "$BACKUP_FILES" ]; then
        print_info "No old backups to clean up"
        return
    fi

    print_info "Cleaning up old backups (keeping $KEEP_COUNT most recent)..."

    echo "$BACKUP_FILES" | while read file; do
        if [ -f "$file" ]; then
            size=$(du -h "$file" | cut -f1)
            rm "$file"
            print_info "Removed: $(basename "$file") (${size})"
        fi
    done

    print_success "Old backups cleaned up"
}

show_usage() {
    print_header
    echo "Usage: $0 {backup|list|restore|cleanup|help}"
    echo ""
    echo "Commands:"
    echo "  backup     - Create a new backup"
    echo "  list       - List all available backups"
    echo "  restore <file> - Restore from backup file"
    echo "  cleanup    - Remove old backups (keep 5 most recent)"
    echo "  help       - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup              # Create new backup"
    echo "  $0 list                # Show available backups"
    echo "  $0 restore backup_20231201_120000.tar.gz"
    echo "  $0 cleanup             # Clean old backups"
    echo ""
    echo "Backup Locations:"
    echo "  📁 Backup Directory: $BACKUP_DIR"
    echo "  📄 Config File: $CONFIG_FILE"
    echo "  📊 Data Directory: $DATA_DIR"
}

# Main script logic
case "${1:-help}" in
    "backup")
        print_header
        create_backup
        ;;
    "list")
        print_header
        list_backups
        ;;
    "restore")
        if [ -z "${2:-}" ]; then
            print_error "Please specify backup file to restore"
            echo "Usage: $0 restore <backup_file>"
            exit 1
        fi
        print_header
        restore_backup "$2"
        ;;
    "cleanup")
        print_header
        cleanup_old_backups
        ;;
    "help"|*)
        show_usage
        ;;
esac
