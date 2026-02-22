#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-tldw_Server_API/Config_Files/.env}"
TEMPLATE_FILE="${2:-tldw_Server_API/Config_Files/.env.quickstart}"

generate_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr -d '\n'
  else
    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  fi
}

read_var() {
  local key="$1"
  if [[ -f "$ENV_FILE" ]]; then
    awk -F= -v k="$key" '$1 == k { val = substr($0, index($0, "=") + 1) } END { if (val != "") print val }' "$ENV_FILE"
  fi
}

upsert_var() {
  local key="$1"
  local value="$2"
  mkdir -p "$(dirname "$ENV_FILE")"
  local tmp="${ENV_FILE}.tmp"
  if [[ -f "$ENV_FILE" ]]; then
    awk -v k="$key" -v v="$value" '
      BEGIN { updated = 0 }
      $0 ~ ("^" k "=") { print k "=" v; updated = 1; next }
      { print }
      END { if (!updated) print k "=" v }
    ' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf "%s=%s\n" "$key" "$value" > "$ENV_FILE"
  fi
}

is_invalid_key() {
  local key="$1"
  if [[ -z "$key" || "${#key}" -lt 16 ]]; then
    return 0
  fi
  case "$key" in
    change-me|CHANGE_ME*|CHANGE_ME_TO_SECURE_API_KEY|changeme|default|test-key)
      return 0
      ;;
  esac
  return 1
}

if [[ ! -f "$ENV_FILE" ]]; then
  mkdir -p "$(dirname "$ENV_FILE")"
  if [[ -f "$TEMPLATE_FILE" ]]; then
    cp "$TEMPLATE_FILE" "$ENV_FILE"
    echo "[docker-bootstrap] Created $ENV_FILE from template."
  else
    cat > "$ENV_FILE" <<'EOF'
AUTH_MODE=single_user
SINGLE_USER_API_KEY=CHANGE_ME_TO_SECURE_API_KEY
DATABASE_URL=sqlite:///./Databases/users.db
EOF
    echo "[docker-bootstrap] Created $ENV_FILE with defaults."
  fi
fi

auth_mode="$(read_var AUTH_MODE)"
auth_mode="${auth_mode:-single_user}"
upsert_var AUTH_MODE "$auth_mode"

database_url="$(read_var DATABASE_URL)"
database_url="${database_url:-sqlite:///./Databases/users.db}"
upsert_var DATABASE_URL "$database_url"

if [[ "$auth_mode" == "single_user" ]]; then
  api_key="$(read_var SINGLE_USER_API_KEY)"
  if is_invalid_key "$api_key"; then
    api_key="$(generate_key)"
    upsert_var SINGLE_USER_API_KEY "$api_key"
    echo "[docker-bootstrap] Generated and persisted SINGLE_USER_API_KEY in $ENV_FILE."
  else
    echo "[docker-bootstrap] Existing SINGLE_USER_API_KEY in $ENV_FILE looks valid."
  fi
fi
