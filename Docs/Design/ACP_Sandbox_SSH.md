# ACP in Sandbox + Web SSH

## Summary
Run ACP runner and downstream agent inside a sandbox VM/container and provide browser-based SSH access via a WebSocket SSH proxy. The ACP WebUI gets a dedicated Workspace terminal tab with strong isolation and session lifecycle management.

## Goals
- ACP agent and downstream agent execute inside sandbox container/VM.
- Provide web SSH access for users in ACP Workspace.
- Workspace files persist per ACP session (bind-mounted from sandbox session workspace).
- Secure, auditable, and deterministic session lifecycle.

## Non-Goals
- Full multi-runtime parity (v1 targets Docker only; Firecracker/Lima follow).
- General-purpose container orchestration beyond ACP use.

## High-Level Architecture

```
WebUI (ACP Playground)
  ├─ ACP WS (/api/v1/acp/sessions/{id}/stream)
  └─ SSH WS (/api/v1/acp/sessions/{id}/ssh)

tldw_server
  ├─ ACP API (session lifecycle)
  ├─ ACP Sandbox Bridge (ACP over sandbox WS)
  └─ SSH Proxy (asyncssh → container SSH)

Sandbox
  ├─ Session workspace dir (host)
  └─ Docker runner (bind-mount workspace, run tldw-agent + sshd)
```

## Data Flow

### ACP Session Create
1. Client calls `/api/v1/acp/sessions/new`.
2. Server creates sandbox session (`/api/v1/sandbox/sessions`) and a long-running sandbox run.
3. Sandbox run command launches `sshd` + `tldw-agent-acp`.
4. Server returns ACP session id plus SSH connection metadata.

### ACP Traffic
- ACP WebSocket connects to `/api/v1/acp/sessions/{id}/stream`.
- Server bridges ACP JSON-RPC lines to sandbox run WS stdin.
- Stdout/stderr frames from sandbox run WS are parsed into ACP responses/notifications.

### SSH Web Proxy
- Client connects to `/api/v1/acp/sessions/{id}/ssh` (WebSocket).
- Server uses `asyncssh` to connect to container’s sshd (key-based auth) and streams data to the browser terminal.

## Container Image
New Dockerfile builds an ACP runtime image:
- OS base: `debian:bookworm-slim` (or `ubuntu:22.04`)
- Installs: openssh-server, ca-certificates, git, bash, curl
- Copies `tldw-agent` binary + config tools
- Entrypoint runs `sshd` and `tldw-agent-acp`

## Sandbox Runner Changes (Docker)
- Add bind-mount for session workspace path to `/workspace`.
- Allow exposing container SSH port to host (host-only, not public).
- Provide container ID + SSH host/port to ACP bridge.

## New Server Components

### ACP Sandbox Bridge
- `ACPSandboxClient`: speaks ACP over sandbox run WS (stdin/stdout frames).
- Maintains per-session mapping: ACP session → sandbox session/run + SSH info.
- Handles reconnects and ensures ACP messages are line-delimited JSON.

### SSH Proxy Endpoint
- WebSocket endpoint `/api/v1/acp/sessions/{id}/ssh`.
- Uses `asyncssh` to open a PTY channel in the container.
- Emits raw bytes to client; receives bytes from client.

## APIs

### ACP Session Create Response
Add fields:
- `sandbox_session_id`
- `sandbox_run_id`
- `ssh_ws_url` (browser WS for SSH)
- `workspace_path` (optional for display)

### ACP Session Close
Closes ACP session and destroys sandbox session/run.

## Security
- SSH keys generated per ACP session; private key never leaves server.
- SSH proxy uses server-side private key to connect to container.
- Container SSH exposed only to host network.
- Workspace is isolated per user/session via sandbox session workspace.
- Audit events for session create/close, SSH connect/disconnect.

## Config
- `ACP_SANDBOX_RUNTIME` (default `docker`)
- `ACP_SANDBOX_BASE_IMAGE` (ACP runtime image)
- `ACP_SSH_ENABLED` (default true)
- `ACP_SSH_USER` (default `acp`)
- `ACP_SSH_HOST` (default `127.0.0.1`)
- `ACP_SSH_PORT_MIN/MAX` (dynamic host port allocation)
- `SANDBOX_ENABLE_EXECUTION` must be true

## Rollout Plan
1. Implement Docker-only support.
2. Integrate ACP bridge and SSH proxy.
3. Add UI terminal.
4. Extend to Firecracker/Lima.

