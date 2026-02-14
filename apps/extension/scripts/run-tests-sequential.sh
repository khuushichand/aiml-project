#!/bin/bash
# Run real-server-workflows tests sequentially (one at a time)
#
# Usage:
#   ./scripts/run-tests-sequential.sh                    # Run all tests
#   ./scripts/run-tests-sequential.sh -g "quick ingest"  # Run specific test
#   ./scripts/run-tests-sequential.sh --headed           # Run with browser visible

set -e

cd "$(dirname "$0")/.."

echo "Running real-server-workflows tests sequentially..."
npx playwright test tests/e2e/real-server-workflows.spec.ts --workers=1 "$@"
