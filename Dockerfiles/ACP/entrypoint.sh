#!/usr/bin/env bash
set -euo pipefail

USER_NAME="${ACP_SSH_USER:-acp}"

if ! id -u "${USER_NAME}" >/dev/null 2>&1; then
  echo "ACP SSH user '${USER_NAME}' does not exist in this image." >&2
  echo "Build the image with the user pre-created (default: acp)." >&2
  exit 1
fi

USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
if [ -z "${USER_HOME}" ]; then
  USER_HOME="/home/${USER_NAME}"
fi

mkdir -p /run/sshd
ssh-keygen -A
cat <<SSHD > /etc/ssh/sshd_config
Port 22
ListenAddress 0.0.0.0
Protocol 2
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PermitUserEnvironment yes
AllowUsers ${USER_NAME}
Subsystem sftp /usr/lib/openssh/sftp-server
SSHD

# Under --cap-drop ALL, root cannot bypass DAC into user-owned homes.
# The image grants root group-write access to USER_HOME during build.
mkdir -p "${USER_HOME}/.ssh"
if [ -n "${ACP_SSH_AUTHORIZED_KEY:-}" ]; then
  printf '%s\n' "${ACP_SSH_AUTHORIZED_KEY}" > "${USER_HOME}/.ssh/authorized_keys"
fi
chmod 700 "${USER_HOME}/.ssh"
if [ -f "${USER_HOME}/.ssh/authorized_keys" ]; then
  chmod 600 "${USER_HOME}/.ssh/authorized_keys"
fi

/usr/sbin/sshd -D -e &

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

mkdir -p "${USER_HOME}/.tldw-agent"
cat "${tmp_cfg}" > "${USER_HOME}/.tldw-agent/config.yaml"
rm -f "${tmp_cfg}"
trap - EXIT
chown "${USER_NAME}" "${USER_HOME}/.tldw-agent" "${USER_HOME}/.tldw-agent/config.yaml"
chmod 600 "${USER_HOME}/.tldw-agent/config.yaml"

export HOME="${USER_HOME}"
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
