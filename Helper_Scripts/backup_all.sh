#!/usr/bin/env bash
# backup_all.sh - Unified backup script for all tldw_server databases
#
# Backs up:
#   1. Per-user content DBs and ChaChaNotes.db
#   2. AuthNZ users.db
#   3. ChromaDB data directories (tar archive)
#
# Usage:
#   ./backup_all.sh [--output-dir /path/to/backups] [--help]

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
Usage: $(basename "$0") [OPTIONS]

Back up all tldw_server databases into a timestamped directory.

Options:
  --output-dir DIR   Base directory for backups (default: <project>/Backups)
  --help             Show this help message

The script creates a subdirectory named full_YYYYMMDD_HHMMSS/ under the
output directory containing copies of every database file and a tar archive
of ChromaDB storage.
EOF
    exit 0
}

# -------------------------------------------------------------------------
# Locate project root (parent of Helper_Scripts/)
# -------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# -------------------------------------------------------------------------
# Parse arguments
# -------------------------------------------------------------------------
OUTPUT_BASE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_BASE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            error "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$OUTPUT_BASE" ]]; then
    OUTPUT_BASE="$PROJECT_ROOT/Backups"
fi

# -------------------------------------------------------------------------
# Create timestamped backup directory
# -------------------------------------------------------------------------
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$OUTPUT_BASE/full_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

info "Backup destination: $BACKUP_DIR"

FILE_COUNT=0
TOTAL_BYTES=0

# -------------------------------------------------------------------------
# Helper: copy a single file and track stats
# -------------------------------------------------------------------------
backup_file() {
    local src="$1"
    local dest_subdir="$2"

    if [[ ! -f "$src" ]]; then
        warn "File not found, skipping: $src"
        return
    fi

    local dest_dir="$BACKUP_DIR/$dest_subdir"
    mkdir -p "$dest_dir"

    local filename
    filename="$(basename "$src")"
    cp "$src" "$dest_dir/$filename"

    # Also copy WAL/SHM sidecars if present (for hot-copy consistency)
    for ext in -wal -shm; do
        if [[ -f "${src}${ext}" ]]; then
            cp "${src}${ext}" "$dest_dir/${filename}${ext}"
        fi
    done

    local size
    size="$(stat -f%z "$dest_dir/$filename" 2>/dev/null || stat --printf='%s' "$dest_dir/$filename" 2>/dev/null || echo 0)"
    TOTAL_BYTES=$((TOTAL_BYTES + size))
    FILE_COUNT=$((FILE_COUNT + 1))
    success "Backed up: $src -> $dest_subdir/$filename ($size bytes)"
}

# -------------------------------------------------------------------------
# 1. AuthNZ database
# -------------------------------------------------------------------------
AUTHNZ_DB="$PROJECT_ROOT/Databases/users.db"
if [[ -f "$AUTHNZ_DB" ]]; then
    backup_file "$AUTHNZ_DB" "authnz"
else
    warn "AuthNZ database not found at $AUTHNZ_DB"
fi

# -------------------------------------------------------------------------
# 2. Evaluations database
# -------------------------------------------------------------------------
EVAL_DB="$PROJECT_ROOT/Databases/evaluations.db"
if [[ -f "$EVAL_DB" ]]; then
    backup_file "$EVAL_DB" "evaluations"
else
    warn "Evaluations database not found at $EVAL_DB (may not exist yet)"
fi

# -------------------------------------------------------------------------
# 3. Per-user databases
# -------------------------------------------------------------------------
USER_DB_BASE="$PROJECT_ROOT/Databases/user_databases"
if [[ -d "$USER_DB_BASE" ]]; then
    for user_dir in "$USER_DB_BASE"/*/; do
        if [[ ! -d "$user_dir" ]]; then
            continue
        fi
        user_id="$(basename "$user_dir")"

        # ChaChaNotes DB
        CHACHA_DB="$user_dir/ChaChaNotes.db"
        if [[ -f "$CHACHA_DB" ]]; then
            backup_file "$CHACHA_DB" "user_databases/$user_id"
        fi

        # Prompts DB (if exists)
        PROMPTS_DB="$user_dir/prompts.db"
        if [[ -f "$PROMPTS_DB" ]]; then
            backup_file "$PROMPTS_DB" "user_databases/$user_id"
        fi

        # Any other .db files in user directory
        for other_db in "$user_dir"/*.db; do
            if [[ ! -f "$other_db" ]]; then
                continue
            fi
            other_name="$(basename "$other_db")"
            # Skip ones we already handled
            case "$other_name" in
                ChaChaNotes.db|prompts.db)
                    continue
                    ;;
            esac
            backup_file "$other_db" "user_databases/$user_id"
        done
    done
else
    warn "User databases directory not found at $USER_DB_BASE"
fi

# -------------------------------------------------------------------------
# 4. ChromaDB storage
# -------------------------------------------------------------------------
CHROMA_DIRS=()
# Check common locations
for candidate in \
    "$PROJECT_ROOT/chroma_storage" \
    "$PROJECT_ROOT/Databases/chroma_storage" \
    "$PROJECT_ROOT/tldw_Server_API/chroma_storage"; do
    if [[ -d "$candidate" ]]; then
        CHROMA_DIRS+=("$candidate")
    fi
done

if [[ ${#CHROMA_DIRS[@]} -gt 0 ]]; then
    for chroma_dir in "${CHROMA_DIRS[@]}"; do
        chroma_name="$(basename "$chroma_dir")"
        parent_name="$(basename "$(dirname "$chroma_dir")")"
        tar_name="${parent_name}_${chroma_name}.tar.gz"
        tar_dest="$BACKUP_DIR/chromadb/$tar_name"
        mkdir -p "$BACKUP_DIR/chromadb"

        info "Archiving ChromaDB: $chroma_dir -> chromadb/$tar_name"
        tar -czf "$tar_dest" -C "$(dirname "$chroma_dir")" "$chroma_name" 2>/dev/null || {
            warn "Failed to archive ChromaDB at $chroma_dir"
            continue
        }
        size="$(stat -f%z "$tar_dest" 2>/dev/null || stat --printf='%s' "$tar_dest" 2>/dev/null || echo 0)"
        TOTAL_BYTES=$((TOTAL_BYTES + size))
        FILE_COUNT=$((FILE_COUNT + 1))
        success "Archived ChromaDB: $tar_dest ($size bytes)"
    done
else
    warn "No ChromaDB storage directories found"
fi

# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------
echo ""
info "========================================"
info "Backup Summary"
info "========================================"
info "Destination : $BACKUP_DIR"
info "Files backed up : $FILE_COUNT"

# Human-readable size
if [[ $TOTAL_BYTES -ge 1073741824 ]]; then
    HR_SIZE="$(echo "scale=2; $TOTAL_BYTES / 1073741824" | bc) GB"
elif [[ $TOTAL_BYTES -ge 1048576 ]]; then
    HR_SIZE="$(echo "scale=2; $TOTAL_BYTES / 1048576" | bc) MB"
elif [[ $TOTAL_BYTES -ge 1024 ]]; then
    HR_SIZE="$(echo "scale=2; $TOTAL_BYTES / 1024" | bc) KB"
else
    HR_SIZE="$TOTAL_BYTES bytes"
fi
info "Total size      : $HR_SIZE"
info "========================================"

if [[ $FILE_COUNT -eq 0 ]]; then
    warn "No files were backed up. Check that databases exist."
    exit 1
fi

success "Backup complete."
