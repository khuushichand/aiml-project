#!/usr/bin/env sh
set -eu

ENV_FILE="${TLDW_ENV_FILE:-/app/tldw_Server_API/Config_Files/.env}"
AUTH_MARKER_DIR="${TLDW_AUTH_MARKER_DIR:-/app/Databases}"
AUTH_MARKER_FILE="${AUTH_MARKER_DIR}/.authnz_initialized_single_user"
RUN_AUTH_INIT_ON_START="${TLDW_RUN_AUTH_INIT_ON_START:-1}"

incoming_auth_mode="${AUTH_MODE:-}"
incoming_api_key="${SINGLE_USER_API_KEY:-}"
incoming_database_url="${DATABASE_URL:-}"

generate_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr -d '\n'
  else
    python -c "import secrets; print(secrets.token_urlsafe(32))"
  fi
}

is_invalid_key() {
  key="$1"
  case "$key" in
    ""|change-me|CHANGE_ME_TO_SECURE_API_KEY|CHANGE_ME*|changeme|default|test-key)
      return 0
      ;;
  esac
  [ "${#key}" -lt 16 ]
}

upsert_env() {
  key="$1"
  value="$2"
  mkdir -p "$(dirname "$ENV_FILE")"
  tmp_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
  chmod 600 "$tmp_file"
  if [ -f "$ENV_FILE" ]; then
    awk -v k="$key" -v v="$value" '
      BEGIN { updated = 0 }
      $0 ~ ("^" k "=") { print k "=" v; updated = 1; next }
      { print }
      END { if (!updated) print k "=" v }
    ' "$ENV_FILE" > "$tmp_file"
  else
    {
      echo "AUTH_MODE=single_user"
      echo "SINGLE_USER_API_KEY=$value"
      echo "DATABASE_URL=sqlite:///./Databases/users.db"
    } > "$tmp_file"
  fi
  mv "$tmp_file" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
}

ensure_env_file() {
  if [ -f "$ENV_FILE" ]; then
    return
  fi
  mkdir -p "$(dirname "$ENV_FILE")"
  generated_key="$(generate_key)"
  tmp_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
  chmod 600 "$tmp_file"
  cat > "$tmp_file" <<EOF
AUTH_MODE=single_user
SINGLE_USER_API_KEY=$generated_key
DATABASE_URL=sqlite:///./Databases/users.db
EOF
  mv "$tmp_file" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "[entrypoint] Created $ENV_FILE with generated SINGLE_USER_API_KEY."
}

ensure_env_file

set -a
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a

if [ -n "$incoming_auth_mode" ]; then
  AUTH_MODE="$incoming_auth_mode"
fi
if [ -n "$incoming_api_key" ]; then
  SINGLE_USER_API_KEY="$incoming_api_key"
fi
if [ -n "$incoming_database_url" ]; then
  DATABASE_URL="$incoming_database_url"
fi

AUTH_MODE="${AUTH_MODE:-single_user}"
DATABASE_URL="${DATABASE_URL:-sqlite:///./Databases/users.db}"

upsert_env "AUTH_MODE" "$AUTH_MODE"
upsert_env "DATABASE_URL" "$DATABASE_URL"

if [ "$AUTH_MODE" = "single_user" ]; then
  current_key="${SINGLE_USER_API_KEY:-}"
  if is_invalid_key "$current_key"; then
    current_key="$(generate_key)"
    echo "[entrypoint] Generated secure SINGLE_USER_API_KEY for single_user mode."
  fi
  export SINGLE_USER_API_KEY="$current_key"
  upsert_env "SINGLE_USER_API_KEY" "$current_key"
fi

# Auto-generate MCP secrets if missing or placeholder (min 32 chars each)
for mcp_var in MCP_JWT_SECRET MCP_API_KEY_SALT BYOK_ENCRYPTION_KEY; do
  eval current_val="\${$mcp_var:-}"
  case "$current_val" in
    ""|CHANGE_ME*)
      new_val="$(generate_key)"
      eval export "$mcp_var=$new_val"
      upsert_env "$mcp_var" "$new_val"
      echo "[entrypoint] Generated $mcp_var."
      ;;
  esac
done

should_run_auth_init=0
case "$*" in
  *uvicorn*|*tldw_Server_API.app.main:app*)
    should_run_auth_init=1
    ;;
esac

if [ "$AUTH_MODE" = "single_user" ] && [ "$RUN_AUTH_INIT_ON_START" != "0" ] && [ "$should_run_auth_init" = "1" ]; then
  mkdir -p "$AUTH_MARKER_DIR"
  if [ ! -f "$AUTH_MARKER_FILE" ]; then
    echo "[entrypoint] Running first-use auth initialization..."
    # Note: `if !` suppresses set -e for this command; the explicit exit 1
    # below is load-bearing — do not remove it.
    if ! python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive; then
      echo "[entrypoint] ERROR: Auth initialization failed. Fix configuration and restart." >&2
      exit 1
    fi
    touch "$AUTH_MARKER_FILE"
    echo "[entrypoint] Auth initialization complete."
  fi
fi

exec "$@"
