#!/usr/bin/env bash
set -euo pipefail

USER_NAME="${ACP_SSH_USER:-acp}"
WORKSPACE_ROOT="${ACP_WORKSPACE_ROOT:-/workspace}"

if ! id -u "${USER_NAME}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${USER_NAME}"
fi

mkdir -p "/home/${USER_NAME}/.ssh"
if [ -n "${ACP_SSH_AUTHORIZED_KEY:-}" ]; then
  printf '%s\n' "${ACP_SSH_AUTHORIZED_KEY}" > "/home/${USER_NAME}/.ssh/authorized_keys"
fi
chmod 700 "/home/${USER_NAME}/.ssh"
chmod 600 "/home/${USER_NAME}/.ssh/authorized_keys" || true
chown -R "${USER_NAME}:${USER_NAME}" "/home/${USER_NAME}/.ssh"

mkdir -p /run/sshd
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

/usr/sbin/sshd -D -e &

mkdir -p "/home/${USER_NAME}/.tldw-agent"
python3 - <<'PY' > "/home/${USER_NAME}/.tldw-agent/config.yaml"
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

print("agent:")
print(f"  command: {json.dumps(command)}")
print(f"  args: {json.dumps(args)}")
print(f"  env: {json.dumps(env)}")
print("workspace:")
print("  allowed_roots:")
print(f"    - {json.dumps(workspace_root)}")
print("terminal:")
print("  enabled: true")
PY

chown -R "${USER_NAME}:${USER_NAME}" "/home/${USER_NAME}/.tldw-agent"

export HOME="/home/${USER_NAME}"
exec su -s /bin/bash "${USER_NAME}" -c "/usr/local/bin/tldw-agent-acp"
