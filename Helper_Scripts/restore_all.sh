#!/usr/bin/env bash
# restore_all.sh - Unified restore script for tldw_server databases
#
# Restores databases from a backup created by backup_all.sh.
#
# Usage:
#   ./restore_all.sh <backup-directory> [--help]

set -euo pipefail

# -------------------------------------------------------------------------
# Colors & helpers
# -------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") <backup-directory> [OPTIONS]

Restore all tldw_server databases from a backup created by backup_all.sh.

Arguments:
  backup-directory   Path to the backup directory (e.g., Backups/full_20260314_120000)

Options:
  --help             Show this help message

IMPORTANT: Stop the tldw_server before restoring. Active database connections
           will prevent safe restoration.

The script will:
  1. Validate the backup directory structure
  2. Restore AuthNZ database (users.db)
  3. Restore each user's databases (Media_DB_v2.db, ChaChaNotes.db, etc.)
  4. Restore ChromaDB data from tar archives
  5. Report what was restored
EOF
    exit 0
}

# -------------------------------------------------------------------------
# Locate project root
# -------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# -------------------------------------------------------------------------
# Parse arguments
# -------------------------------------------------------------------------
BACKUP_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            ;;
        *)
            if [[ -z "$BACKUP_DIR" ]]; then
                BACKUP_DIR="$1"
                shift
            else
                error "Unexpected argument: $1"
                usage
            fi
            ;;
    esac
done

if [[ -z "$BACKUP_DIR" ]]; then
    error "Missing required argument: backup-directory"
    echo ""
    usage
fi

# Resolve to absolute path
if [[ ! "$BACKUP_DIR" = /* ]]; then
    BACKUP_DIR="$(cd "$BACKUP_DIR" 2>/dev/null && pwd)" || {
        error "Backup directory does not exist: $BACKUP_DIR"
        exit 1
    }
fi

# -------------------------------------------------------------------------
# Validate backup directory
# -------------------------------------------------------------------------
if [[ ! -d "$BACKUP_DIR" ]]; then
    error "Backup directory does not exist: $BACKUP_DIR"
    exit 1
fi

info "Restoring from: $BACKUP_DIR"
info "Project root  : $PROJECT_ROOT"
echo ""

RESTORE_COUNT=0
SKIP_COUNT=0

# -------------------------------------------------------------------------
# Helper: restore a single database file
# -------------------------------------------------------------------------
restore_file() {
    local src="$1"
    local dest="$2"

    if [[ ! -f "$src" ]]; then
        warn "Backup file not found, skipping: $src"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        return
    fi

    # Verify the backup is a valid SQLite database
    if ! sqlite3 "$src" "PRAGMA integrity_check;" >/dev/null 2>&1; then
        warn "Integrity check failed for $src, skipping"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        return
    fi

    local dest_dir
    dest_dir="$(dirname "$dest")"
    mkdir -p "$dest_dir"

    # Create a pre-restore backup of the existing file if it exists
    if [[ -f "$dest" ]]; then
        local pre_restore="${dest}.pre_restore_$(date +%Y%m%d_%H%M%S)"
        cp "$dest" "$pre_restore"
        info "Created pre-restore backup: $pre_restore"
    fi

    cp "$src" "$dest"

    # Also restore WAL/SHM sidecars if present in backup
    local filename
    filename="$(basename "$src")"
    local src_dir
    src_dir="$(dirname "$src")"
    for ext in -wal -shm; do
        if [[ -f "${src_dir}/${filename}${ext}" ]]; then
            cp "${src_dir}/${filename}${ext}" "${dest}${ext}"
        fi
    done

    RESTORE_COUNT=$((RESTORE_COUNT + 1))
    success "Restored: $dest"
}

# -------------------------------------------------------------------------
# 1. AuthNZ database
# -------------------------------------------------------------------------
info "--- AuthNZ Database ---"
AUTHNZ_BACKUP="$BACKUP_DIR/authnz/users.db"
AUTHNZ_DEST="$PROJECT_ROOT/Databases/users.db"
if [[ -f "$AUTHNZ_BACKUP" ]]; then
    restore_file "$AUTHNZ_BACKUP" "$AUTHNZ_DEST"
else
    warn "No AuthNZ backup found at $AUTHNZ_BACKUP"
fi

# -------------------------------------------------------------------------
# 2. Evaluations database
# -------------------------------------------------------------------------
info "--- Evaluations Database ---"
EVAL_BACKUP="$BACKUP_DIR/evaluations/evaluations.db"
EVAL_DEST="$PROJECT_ROOT/Databases/evaluations.db"
if [[ -f "$EVAL_BACKUP" ]]; then
    restore_file "$EVAL_BACKUP" "$EVAL_DEST"
else
    warn "No evaluations backup found (may not have existed)"
fi

# -------------------------------------------------------------------------
# 3. Per-user databases
# -------------------------------------------------------------------------
info "--- User Databases ---"
USER_BACKUP_BASE="$BACKUP_DIR/user_databases"
USER_DB_DEST="$PROJECT_ROOT/Databases/user_databases"

if [[ -d "$USER_BACKUP_BASE" ]]; then
    for user_dir in "$USER_BACKUP_BASE"/*/; do
        if [[ ! -d "$user_dir" ]]; then
            continue
        fi
        user_id="$(basename "$user_dir")"
        info "Restoring user: $user_id"

        for db_file in "$user_dir"/*.db; do
            if [[ ! -f "$db_file" ]]; then
                continue
            fi
            db_name="$(basename "$db_file")"
            dest_path="$USER_DB_DEST/$user_id/$db_name"
            restore_file "$db_file" "$dest_path"
        done
    done
else
    warn "No user databases found in backup"
fi

# -------------------------------------------------------------------------
# 4. ChromaDB storage
# -------------------------------------------------------------------------
info "--- ChromaDB Storage ---"
CHROMA_BACKUP="$BACKUP_DIR/chromadb"

if [[ -d "$CHROMA_BACKUP" ]]; then
    for tar_file in "$CHROMA_BACKUP"/*.tar.gz; do
        if [[ ! -f "$tar_file" ]]; then
            continue
        fi
        tar_name="$(basename "$tar_file")"

        # Determine destination based on the tar name
        # Format: parentdir_chroma_storage.tar.gz
        # Extract the parent dir name (everything before _chroma_storage)
        parent_hint="${tar_name%%_chroma_storage.tar.gz}"

        # Try to find the right destination
        dest_parent=""
        case "$parent_hint" in
            Databases)
                dest_parent="$PROJECT_ROOT/Databases"
                ;;
            tldw_Server_API)
                dest_parent="$PROJECT_ROOT/tldw_Server_API"
                ;;
            *)
                dest_parent="$PROJECT_ROOT"
                ;;
        esac

        if [[ -n "$dest_parent" ]]; then
            info "Extracting $tar_name -> $dest_parent/"

            # Back up existing chroma_storage if present
            if [[ -d "$dest_parent/chroma_storage" ]]; then
                pre_restore="${dest_parent}/chroma_storage.pre_restore_$(date +%Y%m%d_%H%M%S)"
                mv "$dest_parent/chroma_storage" "$pre_restore"
                info "Moved existing ChromaDB to: $pre_restore"
            fi

            tar -xzf "$tar_file" -C "$dest_parent" 2>/dev/null || {
                warn "Failed to extract $tar_name"
                SKIP_COUNT=$((SKIP_COUNT + 1))
                continue
            }
            RESTORE_COUNT=$((RESTORE_COUNT + 1))
            success "Restored ChromaDB: $dest_parent/chroma_storage"
        fi
    done
else
    warn "No ChromaDB backups found"
fi

# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------
echo ""
info "========================================"
info "Restore Summary"
info "========================================"
info "Source          : $BACKUP_DIR"
info "Files restored  : $RESTORE_COUNT"
info "Files skipped   : $SKIP_COUNT"
info "========================================"

if [[ $RESTORE_COUNT -eq 0 ]]; then
    warn "No files were restored. Check the backup directory structure."
    exit 1
fi

success "Restore complete. Start the server to verify."
