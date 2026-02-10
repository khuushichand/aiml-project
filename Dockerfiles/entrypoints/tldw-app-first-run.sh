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
  tmp_file="${ENV_FILE}.tmp"
  if [ -f "$ENV_FILE" ]; then
    awk -v k="$key" -v v="$value" '
      BEGIN { updated = 0 }
      $0 ~ ("^" k "=") { print k "=" v; updated = 1; next }
      { print }
      END { if (!updated) print k "=" v }
    ' "$ENV_FILE" > "$tmp_file"
    mv "$tmp_file" "$ENV_FILE"
  else
    {
      echo "AUTH_MODE=single_user"
      echo "SINGLE_USER_API_KEY=$value"
      echo "DATABASE_URL=sqlite:///./Databases/users.db"
    } > "$ENV_FILE"
  fi
}

ensure_env_file() {
  if [ -f "$ENV_FILE" ]; then
    return
  fi
  mkdir -p "$(dirname "$ENV_FILE")"
  generated_key="$(generate_key)"
  cat > "$ENV_FILE" <<EOF
AUTH_MODE=single_user
SINGLE_USER_API_KEY=$generated_key
DATABASE_URL=sqlite:///./Databases/users.db
EOF
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
    python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive
    touch "$AUTH_MARKER_FILE"
    echo "[entrypoint] Auth initialization complete."
  fi
fi

exec "$@"
