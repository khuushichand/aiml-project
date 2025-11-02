#!/bin/bash

# TLDW Server - WebUI Launcher
# Run from project root directory

echo "==========================================="
echo "      TLDW Server - WebUI Launcher"
echo "==========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
  cat <<USAGE
Usage: ./start-webui.sh [options]

Options:
  --host HOST         Host to bind (default: 0.0.0.0)
  --port PORT         Port to use (default: 8000)
  --no-browser        Do not open the browser automatically
  --no-reload         Disable uvicorn --reload
  --log FILE          Log file path (default: /tmp/tldw_server.log)
  --env FILE          Source environment variables from FILE before launching
  -h, --help          Show this help and exit

Environment:
  AUTH_MODE=single_user|multi_user
  SINGLE_USER_API_KEY=...   (for single_user mode)
USAGE
}

# Ensure we're in the right directory
if [ ! -f "tldw_Server_API/app/main.py" ]; then
  echo -e "${RED}Error:${NC} Run this script from the project root (contains tldw_Server_API/)."
  exit 1
fi

# Defaults
HOST="0.0.0.0"
PORT="8000"
OPEN_BROWSER=1
RELOAD=1
LOG_FILE="/tmp/tldw_server.log"
ENV_FILE=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --no-browser) OPEN_BROWSER=0; shift;;
    --no-reload) RELOAD=0; shift;;
    --log) LOG_FILE="$2"; shift 2;;
    --env) ENV_FILE="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo -e "${YELLOW}Warning:${NC} Unknown option: $1"; shift;;
  esac
done

# Optionally source env file
if [ -n "$ENV_FILE" ]; then
  if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    . "$ENV_FILE"
    echo -e "${BLUE}Env:${NC} Loaded variables from ${ENV_FILE}"
  else
    echo -e "${YELLOW}Warning:${NC} --env file not found: ${ENV_FILE}"
  fi
fi

# Dependency checks (non-fatal where possible)
command -v curl >/dev/null 2>&1 || { echo -e "${YELLOW}Note:${NC} 'curl' not found; status checks may be limited."; }
if ! command -v lsof >/dev/null 2>&1; then
  echo -e "${YELLOW}Note:${NC} 'lsof' not found; port checks may be limited."
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo -e "${YELLOW}Note:${NC} 'ffmpeg' not found. Audio/video features may not work until installed."
fi

# Detect python
PY=python
if command -v python3 >/dev/null 2>&1; then PY=python3; fi

# Check uvicorn availability
if ! $PY -c "import uvicorn" 2>/dev/null; then
  echo -e "${RED}Error:${NC} 'uvicorn' is not installed in the current Python environment."
  echo "Install dependencies first:"
  echo "  pip install -e .[dev]   # or add extras like [multiplayer]"
  exit 1
fi

# Functions
check_port() {
  if command -v lsof >/dev/null 2>&1 && lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    return 0
  else
    return 1
  fi
}

find_free_port() {
  local base=${1:-8000}
  for p in $(seq "$base" $((base+10))); do
    if ! lsof -Pi :"$p" -sTCP:LISTEN -t >/dev/null 2>&1; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

# Check if API server is already running
echo "Checking API server status..."
http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
if [ "$http_code" = "200" ]; then
  echo -e "${GREEN}✓${NC} API server is already running on port ${PORT}"
  SERVER_PID=""
else
  echo -e "${YELLOW}○${NC} API server is not running on port ${PORT}"
  echo ""

  # Check if requested port is in use
  if check_port; then
    echo -e "${RED}Warning:${NC} Port ${PORT} is in use but API did not respond to /health."
    alt_port=$(find_free_port "$PORT")
    if [ -n "$alt_port" ] && [ "$alt_port" != "$PORT" ]; then
      read -p "Use free port ${alt_port} instead? (Y/n) " -r
      echo
      if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        PORT="$alt_port"
      else
        echo "You may need to stop the existing process before continuing."
      fi
    fi
  fi

  echo "Starting API server..."

  # Start server in background
  UVICORN_ARGS=("tldw_Server_API.app.main:app" "--host" "$HOST" "--port" "$PORT")
  if [ "$RELOAD" = "1" ]; then UVICORN_ARGS+=("--reload"); fi

  AUTH_MODE="${AUTH_MODE:-single_user}" SINGLE_USER_API_KEY="${SINGLE_USER_API_KEY}" \
    $PY -m uvicorn "${UVICORN_ARGS[@]}" > "$LOG_FILE" 2>&1 &
  SERVER_PID=$!

  echo -e "API server starting (PID: ${SERVER_PID})..."

  # Wait for server
  echo -n "Waiting for API to be ready"
  for i in {1..40}; do
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
      echo -e " ${GREEN}✓${NC}"
      break
    fi
    echo -n "."
    sleep 1
  done

  # Verify start success
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
  if [ "$http_code" != "200" ]; then
    echo -e " ${RED}✗${NC}"
    echo ""
    echo -e "${RED}Error:${NC} Failed to start API server (HTTP: $http_code)."
    echo "Check logs: $LOG_FILE"
    exit 1
  fi
fi

echo ""
echo "==========================================="
echo -e "${GREEN}Server Status:${NC}"
echo "==========================================="
echo ""

# Determine setup vs webui target
OPEN_PATH="/webui/"
setup_json=$(curl -s "http://localhost:${PORT}/api/v1/setup/status" 2>/dev/null || echo "")
if echo "$setup_json" | grep -q '"enabled"\s*:\s*true'; then
  if echo "$setup_json" | grep -q '"needs_setup"\s*:\s*true'; then
    OPEN_PATH="/setup"
    echo -e "${YELLOW}Setup:${NC} First-time setup is enabled; opening the setup wizard."
  fi
fi

# Display URLs
echo -e "${BLUE}Access URLs:${NC}"
echo -e "  WebUI:    ${GREEN}http://localhost:${PORT}${OPEN_PATH}${NC}"
echo -e "  API Docs: ${GREEN}http://localhost:${PORT}/docs${NC}"
echo -e "  ReDoc:    ${GREEN}http://localhost:${PORT}/redoc${NC}"
echo ""

# Display authentication info
if [ -n "$SINGLE_USER_API_KEY" ]; then
  echo -e "${BLUE}Authentication:${NC}"
  echo -e "  Mode: ${GREEN}Single-User (Auto-configured)${NC}"
  echo -e "  The WebUI will automatically use your API key."
  echo ""
  KEY_PREVIEW="${SINGLE_USER_API_KEY:0:10}..."
  echo -e "  API Key Preview: ${YELLOW}${KEY_PREVIEW}${NC}"
elif [ "${AUTH_MODE}" = "multi_user" ]; then
  echo -e "${BLUE}Authentication:${NC}"
  echo -e "  Mode: ${YELLOW}Multi-User${NC}"
  echo -e "  Register/login via the WebUI to obtain a token:"
  echo -e "    ${GREEN}http://localhost:${PORT}/webui/auth.html${NC}"
else
  echo -e "${BLUE}Authentication:${NC}"
  echo -e "  Mode: ${YELLOW}Manual Configuration Required${NC}"
  echo ""
  echo "  To enable auto-configuration:"
  echo -e "    ${YELLOW}export SINGLE_USER_API_KEY='your-api-key'${NC}"
  echo -e "    ${YELLOW}./start-webui.sh${NC}"
fi

echo ""
echo "==========================================="
echo ""

# Open browser unless disabled
if [ "$OPEN_BROWSER" = "1" ]; then
  echo -e "${GREEN}Opening WebUI in your default browser...${NC}"
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "http://localhost:${PORT}${OPEN_PATH}" 2>/dev/null &
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:${PORT}${OPEN_PATH}" 2>/dev/null &
  elif [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    start "http://localhost:${PORT}${OPEN_PATH}" 2>/dev/null &
  else
    echo "Please open: http://localhost:${PORT}${OPEN_PATH}"
  fi
else
  echo -e "${YELLOW}Note:${NC} --no-browser set; not opening the browser."
fi

echo ""

# If we started the server, offer simple management tips
if [ -n "$SERVER_PID" ]; then
  echo "==========================================="
  echo -e "${YELLOW}Server Management:${NC}"
  echo "==========================================="
  echo ""
  echo "The API server is running in the background."
  echo ""
  echo -e "To stop the server:  ${YELLOW}kill $SERVER_PID${NC}"
  echo -e "To view logs:        ${YELLOW}tail -f ${LOG_FILE}${NC}"
  echo ""
  echo "Press Ctrl+C to exit this launcher (server will keep running)."
  echo ""
  trap "echo ''; echo 'Launcher exiting. Server still running (PID: $SERVER_PID)'; exit 0" INT
  while true; do sleep 1; done
else
  echo "==========================================="
  echo -e "${YELLOW}Server Status:${NC}"
  echo "==========================================="
  echo ""
  echo "The API server was already running."
  echo ""
  echo -e "Options:"
  echo -e "  ${YELLOW}1${NC} - View server logs (if available)"
  echo -e "  ${YELLOW}2${NC} - Check server health"
  echo -e "  ${YELLOW}3${NC} - Open WebUI in browser"
  echo -e "  ${YELLOW}Ctrl+C${NC} - Exit launcher"
  echo ""
  trap "echo ''; echo 'Launcher exiting.'; exit 0" INT
  while true; do
    read -t 1 -n 1 key
    if [[ $key = "1" ]]; then
      echo ""
      echo "Checking for server logs..."
      if [ -f "$LOG_FILE" ]; then
        echo "Showing last 20 lines of server log (press Ctrl+C to stop):"
        echo "==========================================="
        tail -f "$LOG_FILE"
      else
        echo "No log file found at $LOG_FILE"
        echo "The server may have been started differently."
      fi
      echo ""
    elif [[ $key = "2" ]]; then
      echo ""
      echo "Checking server health..."
      curl -s "http://localhost:${PORT}/health" | $PY -m json.tool 2>/dev/null || echo "Health check failed"
      echo ""
    elif [[ $key = "3" ]]; then
      echo ""
      echo "Opening WebUI in browser..."
      if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://localhost:${PORT}${OPEN_PATH}" 2>/dev/null &
      elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "http://localhost:${PORT}${OPEN_PATH}" 2>/dev/null &
      fi
      echo ""
    fi
  done
fi
