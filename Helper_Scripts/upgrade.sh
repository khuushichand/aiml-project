#!/usr/bin/env bash
# ===========================================================================
# upgrade.sh — Automated upgrade script for tldw_server
#
# Usage:
#   ./Helper_Scripts/upgrade.sh [OPTIONS]
#
# Options:
#   --dry-run            Run pre-flight checks only; make no changes
#   --target-version TAG Pull a specific git tag/branch instead of latest
#   --help               Show this help and exit
# ===========================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Colour

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${BOLD}==> $*${NC}"; }

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DRY_RUN=false
TARGET_VERSION=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${REPO_ROOT}/Backups/upgrade_${TIMESTAMP}"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --target-version)
            TARGET_VERSION="${2:-}"
            if [[ -z "$TARGET_VERSION" ]]; then
                log_error "--target-version requires a value"
                exit 1
            fi
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--target-version TAG] [--help]"
            echo ""
            echo "Options:"
            echo "  --dry-run            Run pre-flight checks only; make no changes"
            echo "  --target-version TAG Pull a specific git tag/branch instead of latest"
            echo "  --help               Show this help and exit"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Run $0 --help for usage."
            exit 1
            ;;
    esac
done

cd "${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Step 1: Pre-flight checks
# ---------------------------------------------------------------------------
log_step "Step 1/7: Running pre-upgrade checks"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" &>/dev/null; then
    log_error "Python not found. Set PYTHON= to your interpreter."
    exit 1
fi

# Run the upgrade helpers module; it exits 0 if can_proceed, 1 otherwise.
if "$PYTHON" -m Helper_Scripts.upgrade_helpers --json > /tmp/tldw_upgrade_checks.json 2>&1; then
    log_info "All pre-upgrade checks passed."
else
    log_error "Pre-upgrade checks failed:"
    cat /tmp/tldw_upgrade_checks.json
    exit 1
fi

# Pretty-print the summary
"$PYTHON" -c "
import json, pathlib
data = json.loads(pathlib.Path('/tmp/tldw_upgrade_checks.json').read_text())
print(f\"  Summary: {data['summary']}\")
for c in data['checks']:
    icon = {'ok':'✓','warn':'!','fail':'✗'}.get(c['status'],'?')
    print(f\"    [{icon}] {c['name']}: {c.get('message','')}\")
"

if $DRY_RUN; then
    log_info "Dry-run mode — stopping here. No changes were made."
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 2: Record current state for rollback
# ---------------------------------------------------------------------------
log_step "Step 2/7: Recording current state"

CURRENT_COMMIT="$(git rev-parse HEAD)"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log_info "Current commit: ${CURRENT_COMMIT}"
log_info "Current branch: ${CURRENT_BRANCH}"

# ---------------------------------------------------------------------------
# Step 3: Create backup
# ---------------------------------------------------------------------------
log_step "Step 3/7: Creating backup"

mkdir -p "${BACKUP_DIR}"

# Save rollback info
cat > "${BACKUP_DIR}/rollback_info.txt" <<ROLLBACK
# tldw_server upgrade rollback information
# Created: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT=${CURRENT_COMMIT}
BRANCH=${CURRENT_BRANCH}

# To rollback, run:
#   cd ${REPO_ROOT}
#   git checkout ${CURRENT_COMMIT}
#   cp -a ${BACKUP_DIR}/Databases/ ${REPO_ROOT}/Databases/
#   pip install -e .
ROLLBACK

# Backup databases if they exist
if [[ -d "${REPO_ROOT}/Databases" ]]; then
    log_info "Backing up Databases/ ..."
    cp -a "${REPO_ROOT}/Databases" "${BACKUP_DIR}/Databases"
    log_info "Database backup complete: ${BACKUP_DIR}/Databases/"
else
    log_info "No Databases/ directory found — skipping backup."
fi

log_info "Backup saved to ${BACKUP_DIR}/"

# ---------------------------------------------------------------------------
# Step 4: Pull latest code
# ---------------------------------------------------------------------------
log_step "Step 4/7: Pulling latest code"

if [[ -n "$TARGET_VERSION" ]]; then
    log_info "Fetching and checking out target: ${TARGET_VERSION}"
    git fetch --tags origin
    git checkout "${TARGET_VERSION}"
else
    log_info "Pulling latest from origin/${CURRENT_BRANCH}"
    git pull origin "${CURRENT_BRANCH}"
fi

NEW_COMMIT="$(git rev-parse HEAD)"
log_info "Now at commit: ${NEW_COMMIT}"

# ---------------------------------------------------------------------------
# Step 5: Install dependencies
# ---------------------------------------------------------------------------
log_step "Step 5/7: Installing dependencies"

if "$PYTHON" -m pip install -e . 2>&1; then
    log_info "Dependencies installed successfully."
else
    log_error "pip install failed. See output above."
    log_warn "Rollback instructions are in ${BACKUP_DIR}/rollback_info.txt"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 6: Database migrations
# ---------------------------------------------------------------------------
log_step "Step 6/7: Database migrations"
log_info "Migrations run automatically at server startup (ensure_authnz_schema_ready_once)."
log_info "Skipping explicit migration step — start the server to apply."

# ---------------------------------------------------------------------------
# Step 7: Post-upgrade validation
# ---------------------------------------------------------------------------
log_step "Step 7/7: Post-upgrade validation"

if "$PYTHON" -m Helper_Scripts.upgrade_helpers 2>&1; then
    log_info "Post-upgrade checks passed."
else
    log_warn "Post-upgrade checks reported issues — review output above."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}Upgrade complete!${NC}"
echo ""
echo "  Previous commit: ${CURRENT_COMMIT}"
echo "  Current commit:  ${NEW_COMMIT}"
echo "  Backup location: ${BACKUP_DIR}/"
echo ""
echo -e "${BOLD}Rollback instructions:${NC}"
echo "  1. cd ${REPO_ROOT}"
echo "  2. git checkout ${CURRENT_COMMIT}"
echo "  3. cp -a ${BACKUP_DIR}/Databases/ ${REPO_ROOT}/Databases/"
echo "  4. pip install -e ."
echo "  5. Restart the server"
echo ""
echo "See ${BACKUP_DIR}/rollback_info.txt for details."
