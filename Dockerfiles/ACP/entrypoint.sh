#!/usr/bin/env bash
set -euo pipefail

USER_NAME="${ACP_SSH_USER:-acp}"
AGENT_COMMAND="${ACP_AGENT_COMMAND:-}"
SSH_PORT="${ACP_SSH_PORT:-2222}"

if ! id -u "${USER_NAME}" >/dev/null 2>&1; then
  echo "ACP SSH user '${USER_NAME}' does not exist in this image." >&2
  echo "Build the image with the user pre-created (default: acp)." >&2
  exit 1
fi

if [ -n "${AGENT_COMMAND}" ] && [ "$(basename "${AGENT_COMMAND}")" = "tldw-agent-acp" ]; then
  echo "Invalid AGENT_COMMAND='${AGENT_COMMAND}'." >&2
  echo "AGENT_COMMAND must point to a downstream ACP-compatible coding agent (for example: claude, codex, opencode)." >&2
  echo "Do not set AGENT_COMMAND to tldw-agent-acp; that recursively launches the runner and exhausts process limits." >&2
  exit 64
fi

case "${SSH_PORT}" in
  ''|*[!0-9]*)
    echo "Invalid ACP_SSH_PORT='${SSH_PORT}' (must be numeric)." >&2
    exit 64
    ;;
esac
if [ "${SSH_PORT}" -lt 1 ] || [ "${SSH_PORT}" -gt 65535 ]; then
  echo "Invalid ACP_SSH_PORT='${SSH_PORT}' (must be 1-65535)." >&2
  exit 64
fi

USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
if [ -z "${USER_HOME}" ]; then
  USER_HOME="/home/${USER_NAME}"
fi
RUNTIME_HOME="${ACP_RUNTIME_HOME:-${USER_HOME}}"
RUNTIME_HOME="${RUNTIME_HOME%/}"
if [ -z "${RUNTIME_HOME}" ]; then
  RUNTIME_HOME="/workspace/.acp-home"
fi
RUNTIME_HOME="${RUNTIME_HOME}/"
RUNTIME_HOME="${RUNTIME_HOME%/}"
if [ "${RUNTIME_HOME}" = "/" ]; then
  echo "ACP runtime home cannot be '/'." >&2
  exit 64
fi
mkdir -p "${RUNTIME_HOME}"
if [ ! -w "${RUNTIME_HOME}" ]; then
  echo "ACP runtime home '${RUNTIME_HOME}' is not writable." >&2
  exit 1
fi

SSHD_RUNTIME_DIR="${ACP_SSH_RUNTIME_DIR:-/tmp/acp-sshd}"
mkdir -p "${SSHD_RUNTIME_DIR}"
if [ ! -w "${SSHD_RUNTIME_DIR}" ]; then
  echo "ACP ssh runtime dir '${SSHD_RUNTIME_DIR}' is not writable." >&2
  exit 1
fi

AUTH_KEYS_DIR="${RUNTIME_HOME}/.ssh"
AUTH_KEYS_FILE="${AUTH_KEYS_DIR}/authorized_keys"
mkdir -p "${AUTH_KEYS_DIR}"
if [ -n "${ACP_SSH_AUTHORIZED_KEY:-}" ]; then
  if [ ! -f "${AUTH_KEYS_FILE}" ] || ! grep -Fxq -- "${ACP_SSH_AUTHORIZED_KEY}" "${AUTH_KEYS_FILE}"; then
    printf '%s\n' "${ACP_SSH_AUTHORIZED_KEY}" >> "${AUTH_KEYS_FILE}"
  fi
fi
chmod 700 "${AUTH_KEYS_DIR}"
if [ -f "${AUTH_KEYS_FILE}" ]; then
  chmod 600 "${AUTH_KEYS_FILE}"
fi

HOST_KEY="${SSHD_RUNTIME_DIR}/ssh_host_ed25519_key"
if [ ! -f "${HOST_KEY}" ]; then
  ssh-keygen -q -t ed25519 -N "" -f "${HOST_KEY}"
fi
chmod 600 "${HOST_KEY}"

SSHD_CONFIG="${SSHD_RUNTIME_DIR}/sshd_config"
cat <<SSHD > "${SSHD_CONFIG}"
Port ${SSH_PORT}
ListenAddress 0.0.0.0
Protocol 2
UsePAM no
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile ${AUTH_KEYS_FILE}
PermitUserEnvironment yes
AllowUsers ${USER_NAME}
HostKey ${HOST_KEY}
PidFile ${SSHD_RUNTIME_DIR}/sshd.pid
StrictModes no  # Container-mounted volumes/runtime dirs may have UID/GID ownership drift; trade-off is weaker sshd permission enforcement, mitigated by key-only auth, non-root SSH user, limited exposure, and documented volume-ownership expectations.
Subsystem sftp internal-sftp
SSHD

if ! /usr/sbin/sshd -t -f "${SSHD_CONFIG}"; then
  echo "sshd config validation failed for '${SSHD_CONFIG}'." >&2
  exit 1
fi

/usr/sbin/sshd -D -e -f "${SSHD_CONFIG}" &
SSHD_PID=$!
sleep 1

if ! ps -p "${SSHD_PID}" >/dev/null 2>&1; then
  echo "sshd failed to stay running (config: '${SSHD_CONFIG}', pid: '${SSHD_PID}')." >&2
  exit 1
fi

PORT_CHECK_PERFORMED=false
PORT_BOUND=false
if command -v ss >/dev/null 2>&1; then
  PORT_CHECK_PERFORMED=true
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${SSH_PORT}$"; then
    PORT_BOUND=true
  fi
elif command -v netstat >/dev/null 2>&1; then
  PORT_CHECK_PERFORMED=true
  if netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${SSH_PORT}$"; then
    PORT_BOUND=true
  fi
elif command -v lsof >/dev/null 2>&1; then
  PORT_CHECK_PERFORMED=true
  if lsof -nP -iTCP:"${SSH_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    PORT_BOUND=true
  fi
fi

if [ "${PORT_CHECK_PERFORMED}" = true ] && [ "${PORT_BOUND}" != true ]; then
  if ps -p "${SSHD_PID}" >/dev/null 2>&1; then
    kill "${SSHD_PID}" >/dev/null 2>&1 || true
  fi
  echo "sshd started but did not bind port '${SSH_PORT}' (config: '${SSHD_CONFIG}')." >&2
  exit 1
fi

tmp_cfg="$(mktemp)"
cleanup_tmp_cfg() {
  rm -f "${tmp_cfg}"
}
trap cleanup_tmp_cfg EXIT

python3 - <<'PY' > "${tmp_cfg}"
import json
import os
import sys


def load_json(name: str, default: str):
    raw = os.environ.get(name, default)
    if raw == "":
        raw = default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON for {name}: {exc}", file=sys.stderr)
        sys.exit(1)


args = load_json("ACP_AGENT_ARGS_JSON", "[]")
if not isinstance(args, list):
    print("ACP_AGENT_ARGS_JSON must be a JSON array.", file=sys.stderr)
    sys.exit(1)

env = load_json("ACP_AGENT_ENV_JSON", "{}")
if not isinstance(env, dict):
    print("ACP_AGENT_ENV_JSON must be a JSON object.", file=sys.stderr)
    sys.exit(1)

command = os.environ.get("ACP_AGENT_COMMAND", "")
workspace_root = os.environ.get("ACP_WORKSPACE_ROOT", "/workspace")
env_list = [f"{k}={v}" for k, v in env.items()]

print("agent:")
print(f"  command: {json.dumps(command)}")
print(f"  args: {json.dumps(args)}")
print(f"  env: {json.dumps(env_list)}")
print("workspace:")
print(f"  default_root: {json.dumps(workspace_root)}")
print("execution:")
print("  enabled: true")
PY

mkdir -p "${RUNTIME_HOME}/.tldw-agent"
cat "${tmp_cfg}" > "${RUNTIME_HOME}/.tldw-agent/config.yaml"
rm -f "${tmp_cfg}"
trap - EXIT
chmod 600 "${RUNTIME_HOME}/.tldw-agent/config.yaml"

export HOME="${RUNTIME_HOME}"
CURRENT_UID="$(id -u)"
TARGET_UID="$(id -u "${USER_NAME}" 2>/dev/null || true)"
if [ "${CURRENT_UID}" -eq 0 ]; then
  chown -R "${USER_NAME}" "${RUNTIME_HOME}"
fi
if [ -n "${TARGET_UID}" ] && [ "${CURRENT_UID}" -eq "${TARGET_UID}" ]; then
  exec /usr/local/bin/tldw-agent-acp
fi

if [ "${CURRENT_UID}" -eq 0 ]; then
  if command -v gosu >/dev/null 2>&1; then
    exec gosu "${USER_NAME}" /usr/local/bin/tldw-agent-acp
  elif command -v su-exec >/dev/null 2>&1; then
    exec su-exec "${USER_NAME}" /usr/local/bin/tldw-agent-acp
  elif command -v runuser >/dev/null 2>&1; then
    exec runuser -u "${USER_NAME}" --preserve-environment -- /usr/local/bin/tldw-agent-acp
  else
    echo "No privilege-drop tool available (gosu, su-exec, or runuser)." >&2
    exit 1
  fi
fi

echo "ACP entrypoint running as uid=${CURRENT_UID}; launching agent without user switch." >&2
exec /usr/local/bin/tldw-agent-acp
