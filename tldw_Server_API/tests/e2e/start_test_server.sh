#!/bin/bash
# Script to start the test server with proper environment variables

# Always resolve paths relative to this script, not the caller's CWD
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "Starting test server with TEST_MODE enabled..."

# Check if server is already running
if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "⚠️  A server is already running on port 8000!"
    echo "Please stop it first with: pkill -f 'uvicorn.*8000' or find and kill the process"
    echo ""
    echo "To find the process: lsof -i :8000"
    exit 1
fi

# Set test environment variables
export TEST_MODE=true
export TESTING=true
# Use a canonical deterministic test key that matches AuthNZ defaults and test expectations
export SINGLE_USER_TEST_API_KEY="${SINGLE_USER_TEST_API_KEY:-test-api-key-12345}"
# Ensure the single-user API key used by the server matches the test key
export SINGLE_USER_API_KEY="${SINGLE_USER_API_KEY:-$SINGLE_USER_TEST_API_KEY}"
# Expose the effective test API key via /api/v1/health for E2E fixtures
export HEALTH_EXPOSE_TEST_API_KEY=true

# Use an isolated per-run USER_DB_BASE_DIR so E2E tests exercise on-disk
# persistence/locking without mutating the developer's local databases.
# This directory is cleaned up in the trap on exit.
TMP_USER_DB_BASE="$(mktemp -d "${REPO_ROOT}/Databases/user_databases_e2e_XXXXXX")"
export USER_DB_BASE_DIR="${TMP_USER_DB_BASE}"
echo "E2E USER_DB_BASE_DIR: ${USER_DB_BASE_DIR}"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down test server..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
        # Also kill any child processes
        pkill -P $SERVER_PID 2>/dev/null
    fi
    # Remove the temporary per-run USER_DB_BASE_DIR to avoid polluting the repo
    if [ -n "$TMP_USER_DB_BASE" ] && [ -d "$TMP_USER_DB_BASE" ]; then
        echo "Cleaning up E2E USER_DB_BASE_DIR: $TMP_USER_DB_BASE"
        rm -rf "$TMP_USER_DB_BASE"
    fi
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup INT TERM EXIT

# Start the server
echo "Starting server with API key: $SINGLE_USER_API_KEY"
cd "${REPO_ROOT}" || { echo "Failed to cd to repo root: ${REPO_ROOT}" >&2; exit 1; }

# Start server and capture both stdout and stderr (use full module path)
python -m uvicorn tldw_Server_API.app.main:app --reload --port 8000 2>&1 &
SERVER_PID=$!

# Give server a moment to start and check if it's actually running
sleep 2
if ! ps -p $SERVER_PID > /dev/null; then
    echo "❌ Server failed to start (process died immediately)"
    echo "Port 8000 may already be in use. Check with: lsof -i :8000"
    exit 1
fi

# Wait for server to be ready
echo "Waiting for server to be ready..."
ATTEMPTS=0
MAX_ATTEMPTS=30

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        # Verify it's our test server by checking for test_api_key in health response
        if curl -s http://localhost:8000/api/v1/health | grep -q "test_api_key"; then
            echo "✅ Test server is ready with TEST_MODE enabled!"
        else
            echo "✅ Server is ready (but TEST_MODE may not be active - API key won't be exposed)"
        fi

        echo ""
        echo "Test server is running with PID: $SERVER_PID"
        echo "API Key: $SINGLE_USER_API_KEY"
        echo ""
        echo "You can now run the E2E tests in another terminal with:"
        echo "  cd tldw_Server_API"
        echo "  python -m pytest tests/e2e/"
        echo ""
        echo "Press Ctrl+C to stop the server"
        echo ""

        # Keep the script running and wait for the server process
        wait $SERVER_PID
        exit 0
    fi

    # Check if process is still alive
    if ! ps -p $SERVER_PID > /dev/null; then
        echo ""
        echo "❌ Server process died unexpectedly"
        echo "Check if port 8000 is already in use: lsof -i :8000"
        exit 1
    fi

    echo -n "."
    sleep 1
    ATTEMPTS=$((ATTEMPTS + 1))
done

echo ""
echo "❌ Server failed to become ready within 30 seconds"
kill $SERVER_PID 2>/dev/null
exit 1
