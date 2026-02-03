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
cat <<CFG > "/home/${USER_NAME}/.tldw-agent/config.yaml"
agent:
  command: "${ACP_AGENT_COMMAND:-}"
  args: ${ACP_AGENT_ARGS_JSON:-[]}
  env: ${ACP_AGENT_ENV_JSON:-{}}
workspace:
  allowed_roots:
    - "${WORKSPACE_ROOT}"
terminal:
  enabled: true
CFG

chown -R "${USER_NAME}:${USER_NAME}" "/home/${USER_NAME}/.tldw-agent"

export HOME="/home/${USER_NAME}"
exec su -s /bin/bash "${USER_NAME}" -c "/usr/local/bin/tldw-agent-acp"
