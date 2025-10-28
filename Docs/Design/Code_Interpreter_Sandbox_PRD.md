# PRD: Code Interpreter Sandbox & LSP

Owner: tldw_server Core Team  
Status: In Progress v0.2  
Last updated: 2025-10-28

## 1) Summary

Build a secure, configurable code execution service that lets users, agents, and workflows run untrusted code snippets and full applications in isolated sandboxes. Provide an IDE-friendly LSP integration to surface diagnostics, logs, and results inline. Support both Docker containers (Linux/macOS/Windows hosts) and Firecracker microVMs (Linux-only) to balance broad compatibility with stronger isolation where available.

Primary use cases:
- Validate LLM-generated code safely, before running it locally.
- Run tests, scripts, and small apps against a provided workspace snapshot.
- Provide a standard API for agents/workflows to execute and verify code.
- Stream logs and results back to IDEs and the tldw web UI; store artifacts.


## 2) Problem Statement

Developers increasingly rely on LLMs to generate code. Executing untrusted snippets locally risks compromise, dependency pollution, and state corruption. There’s no unified, policy-controlled way to check code in-context and get actionable diagnostics inside IDEs and chat UIs. We need a safe, consistent, and observable mechanism to run code in isolation with guardrails, and to surface results where developers work.


## 3) Goals and Non‑Goals

### Goals
1. Provide a sandboxed code execution service with clear isolation guarantees.
2. Offer two runtimes: Docker (broad support) and Firecracker (stronger isolation on Linux).
3. Expose a clean REST + WebSocket API for runs, logs, and artifacts.
4. Provide an LSP bridge so IDEs can trigger runs and show diagnostics inline.
5. Support agent/workflow invocation (incl. MCP tool) with policy and approvals.
6. Capture execution metadata for auditing, reproducibility, and debugging.

### Non‑Goals (Initial)
- Full interactive remote desktops. (Future: optional Jupyter/shell sessions.)
- Long-running services with inbound ports. (Initial runs are batch-like.)
- Arbitrary outbound network access. (Default: locked down; allowlist later.)
- Managing user VPCs or complex cloud resource brokers in v0.


## 4) Personas

- Individual Developer: Uses IDE + tldw chat; wants to validate code safely.
- Agent Builder: Needs a standard tool to execute code during agent workflows.
- Team Lead / Admin: Enforces policies, quotas, and audit requirements.
- CI/Automation Engineer: Leverages API to run quick validations pre-commit.


## 5) User Stories (MVP → vNext)

MVP
- As a developer, I can submit a snippet + dependencies to run in a sandbox and get logs, exit code, and artifacts.
- As a developer, I can stream stdout/stderr while the snippet runs.
- As an IDE user, I can trigger “Run in Sandbox” and see diagnostics inline.
- As an admin, I can choose runtime (Docker/Firecracker) defaults per environment.
- As an agent, I can call sandbox.run with a command and receive outputs.

vNext
- As a developer, I can open an interactive session (Jupyter/shell) with a TTL.
- Support limited interactive runs via WS with a `stdin` channel (opt-in, TTL-bound).
- As an admin, I can define egress policies (deny by default, allowlist).
- As a user, I can mount a read-only workspace snapshot into the sandbox.
- As a team, we can reuse cached environments (warm pools) for lower latency.
- As a CI engineer, I can gate runs on approvals and budgets/quotas.


## 6) Scope

In Scope (MVP)
- Docker and Firecracker runtimes (selectable via policy or request).
- Language base images: Python, Node.js, Go, Java, .NET, plus a generic image.
- One-shot runs with tar/zip uploads or remote git clone + patch.
- Resource controls: CPU, memory, disk, wall-clock timeout.
- Default no-network; optional allowlist for essential package mirrors (future).
- REST endpoints for session/run management; WS for streaming logs.
- Artifact capture: files produced during run (size/quota limits).
- Audit logs with user, model, prompt/context, runtime, policy, and outcome.
- RBAC based on existing AuthNZ (JWT/API key) + per-user quotas + rate limits.

Out of Scope (MVP)
- GPU support, nested virtualization, or privileged containers.
- Persistent volumes beyond run TTL; long-term package caches.
- Arbitrary background daemons or exposed network services inside runs.


## 7) Requirements

### Functional Requirements
1. Runtimes
   - Docker runtime using rootless mode where possible, with seccomp/AppArmor profiles.
   - Firecracker runtime via direct Firecracker SDK/CLI; ignite is EOL. Use prebuilt microVM images/snapshots.

2. Execution
   - Create a session (ephemeral or short-lived) → upload code (tar/zip or files) → start run with command/args/env → stream logs → retrieve status and artifacts → destroy.
   - One-shot runs without persistent session (convenience path).
   - Entry command is explicit; no default execution of arbitrary scripts.

3. Inputs/Artifacts
   - Accept uploads up to configurable size; verify archive and path safety.
   - Support git clone with optional shallow depth + patch application.
   - Cloning occurs server-side (by the orchestrator) prior to sandbox start; default deny-all egress inside the sandbox prevents outbound fetches from the run environment.
   - Artifact capture with per-run quotas and retention policies.

4. LSP Integration
   - Provide a small LSP-side service/extension that calls sandbox APIs.
   - Map results and logs to diagnostics (file/line) when possible using language-aware stack trace parsers (Python/Node/Go/Java).
   - Expose custom `workspace/executeCommand` actions: `tldw.sandbox.run`, `tldw.sandbox.configure`, `tldw.sandbox.openArtifacts`.

5. Agent/Workflow Integration
   - MCP tool: `sandbox.run` with arguments (image, command, files, timeout).
   - Policy guardrails: deny/approve flows; admin-configurable runtime defaults.

6. Admin/Policy
   - Global and per-user quotas: concurrent runs, CPU/mem limits, total runtime/day.
   - Runtime policy: choose Docker or Firecracker; enable/disable networking; allowlist domains (vNext); secrets injection policy.
   - Audit and compliance logs for every run.

### Non‑Functional Requirements
- Security/Isolation: Strong default isolation; zero host mounts; read-only base images; immutable root where possible; ephemeral writable layer; no privileged containers.
- Reliability: Orphan reaper for stuck sessions; idempotent cleanup; retries for transient runtime errors.
- Performance: P95 run start < 2s for Docker warm image, < 5s for Firecracker warm microVM; log latency < 200ms.
- Scalability: Pooling/warm images; horizontal workers; bounded queues with backpressure.
- Observability: Structured logs; metrics (runs, latency, failures, resource usage); trace IDs for correlation with chat/agents.
- Usability: Clear error messages; human-readable run summaries.


## 8) Architecture Overview

Components
- Sandbox API Service (FastAPI): REST + WS endpoints, AuthNZ, rate limits, policy checks.
- Orchestrator/Queue: Enqueues runs, assigns workers, enforces quotas.
- Runtimes:
  - Docker Runner: manages images, containers, resource limits, seccomp/AppArmor.
  - Firecracker Runner: manages microVM images/snapshots, networking policy, block devices.
- Storage:
  - Input store (uploads, git snapshots); ephemeral per-run workspace.
  - Artifact store with TTL and size quotas.
- Streaming/Logs: WebSocket for stdout/stderr; server-side ring buffer fallback.
- Policy Engine: Evaluate org/user/runtime policies (network, secrets, quotas).
- Audit/Telemetry: Persist run metadata and outcomes; export Prometheus metrics.
- Integrations: LSP bridge, MCP tool, Web UI panel.

Runtime Modes
- One-shot run: No persistent session; run starts immediately with inputs.
- Short session: Allows multiple runs against same ephemeral workspace (TTL, max runs).

Isolation
- Docker: rootless preferred; seccomp profile, no host mounts, read-only root, tmpfs overlays for writable paths, memory/cpu quotas.
- Firecracker: microVM per run/session; read-only root FS image + writable scratch; optional tap interface disabled by default; limited devices; cgroup quotas.


## 9) API Design (MVP)

Base path: `/api/v1/sandbox`

Auth: Reuse existing AuthNZ (JWT for multi-user or API key for single-user). Apply rate limits and quotas via shared dependency. Unless specified, request/response bodies use `application/json`.

Endpoints
- POST `/sessions`
  - Create a session. Body: `spec_version`, runtime (`docker`|`firecracker`), base_image, cpu/mem limits, timeout, network_policy, env (non-secret), labels.
  - Returns: `session_id`, `expires_at`, runtime info.

- POST `/sessions/{session_id}/files`
  - Upload a tar/zip or individual files. Server verifies and expands into session workspace.

- POST `/runs`
  - Start a run (one-shot or for existing session). Body: `spec_version`, session_id? base_image? command[], env, `startup_timeout_sec` (image pull/VM boot), `timeout_sec` (execution), resource overrides, network_policy, files? (optional inline small files), capture_patterns. Supports `Idempotency-Key` header to dedupe client retries.
  - Returns: `run_id`, `session_id?`.

- GET `/runs/{run_id}`
  - Status: phase (queued|starting|running|completed|failed|killed|timed_out), exit_code, started_at, finished_at, runtime, base_image, image_digest (when available), policy_hash, spec_version, and resource_usage summary.

- WS `/runs/{run_id}/stream`
  - Server→client stream of stdout/stderr and structured events. Message envelope:
    - `{ "type": "stdout"|"stderr", "encoding": "utf8"|"base64", "data": "<payload>", "seq": n }`
    - `{ "type": "event", "event": "phase"|"start"|"end"|"error", "data": { ... } }`
    - `{ "type": "heartbeat", "ts": "ISO" }`
    - `{ "type": "truncated", "reason": "log_cap" }`
  - Limits: max message size 64KB; server enforces per-run log cap (e.g., 10 MB) and backpressure with buffered ring. Implemented.

- GET `/runs/{run_id}/artifacts`
  - List artifact files with sizes and signed download URLs (or direct GET with auth).

- POST `/runs/{run_id}/cancel`
  - Request cancellation; returns best-effort confirmation.

- DELETE `/sessions/{session_id}`
  - Early destroy; reclaims resources and workspace.

- GET `/runtimes`
  - Feature discovery for host: which runtimes available, default images (with digests when possible), per-runtime limits (max CPU/mem per run), `max_upload_mb`, `workspace_cap_mb`, `artifact_ttl_hours`, and `supported_spec_versions`. Implemented.

Error Model
- All error responses use a standard envelope:
  - `{ "error": { "code": "string", "message": "human readable", "details": {"...": "..."} } }`
- Common codes: `invalid_request`, `not_found`, `unauthorized`, `forbidden`, `rate_limited`, `quota_exceeded`, `timeout`, `canceled`, `runtime_unavailable`.
 - Additional: `idempotency_conflict` when `Idempotency-Key` is replayed with a different request body.
 - Optional compatibility: if client sets `Accept: application/problem+json`, the server MAY return RFC 7807 responses mapping `code`→`type` and `message`→`title`/`detail`; `details` is preserved via problem `extensions`.

Spec Versioning

- Field: `spec_version` (string) is required in POST `/sessions` and `/runs`.
- Initial value: `"1.0"`.
- Semantics:
  - Minor (1.x): backward-compatible; server may accept a range (e.g., `1.0`–`1.2`).
  - Major (2.0): potentially breaking; server rejects unsupported majors with `invalid_spec_version`.
- Discovery: GET `/runtimes` includes `supported_spec_versions` (e.g., `["1.0", "1.1"]`).
- Validation errors include `details.supported` with accepted versions.

Runtime Limits Normalization

- `resources.cpu` maps to:
  - Docker: `--cpus=<float>` (CPUQuota/CPUPeriod). Example: `cpu=1.5` ≈ 1.5 cores.
  - Firecracker: rounded-up vCPUs. Example: `cpu=1.5` → `vCPU=2`.
- `resources.memory_mb` maps to:
  - Docker: `--memory=<bytes>`; swap disabled.
  - Firecracker: microVM RAM size (rounded to supported increment).
- Example normalization:
  - Request: `{ "cpu": 0.75, "memory_mb": 512 }`
  - Docker: `--cpus=0.75`, `--memory=512m`
  - Firecracker: `vCPU=1`, `RAM=512MiB`

Admin (future)
- GET `/policies` | PUT `/policies`
- GET `/quotas` | PUT `/quotas`

Content Types & Limits

| Endpoint | Method | Content-Type | Max Upload | Max Files | Max Depth | Notes |
|---|---|---|---|---|---|---|
| `/sessions` | POST | `application/json` | n/a | n/a | n/a | Accepts `spec_version`, runtime/image, limits, policies |
| `/sessions/{id}/files` | POST | `multipart/form-data` (files[]) or `application/x-tar` | configurable (default 64 MB) | configurable (default 1,000) | configurable (default 10) | Safe extraction: no `..`, no absolute paths, symlinks/hardlinks/device nodes rejected |
| `/runs` | POST | `application/json` | inline files only (base64) up to 1 MB total | n/a | n/a | Supports `Idempotency-Key` header; `spec_version`, startup/execution timeouts |
| `/runs/{id}` | GET | `application/json` | n/a | n/a | n/a | Returns status and `resource_usage` block |
| `/runs/{id}/stream` | WS | text frames (UTF-8 JSON envelopes) | n/a | n/a | n/a | Max message 64 KB; server log cap (default 10 MB); heartbeats every 10s |
| `/runs/{id}/artifacts` | GET | `application/json` | n/a | n/a | n/a | Lists artifacts with sizes and types |
| `/runs/{id}/artifacts/{path}` | GET | varies (by file) | n/a | n/a | n/a | Supports HTTP Range; content-type detection; path normalized |
| `/runs/{id}/cancel` | POST | `application/json` | n/a | n/a | n/a | Graceful cancel with SIGTERM→SIGKILL |
| `/runtimes` | GET | `application/json` | n/a | n/a | n/a | Includes per-runtime maxima, supported `spec_versions`, `workspace_cap_mb`, and `artifact_ttl_hours` |

WebSocket Protocol Details
- Auth: same bearer/JWT or API key as REST. Optionally a short-lived signed token via `?token=...` may be provided.
- Endpoint: `WS /runs/{run_id}/stream` with `run_id` path param; no additional subprotocol required.
- Frames: UTF‑8 JSON envelopes. `stdout`/`stderr` payloads base64-encoded when binary; plain strings allowed for UTF‑8 text.
- Heartbeats: server sends `{type:"heartbeat"}` every 10s; clients should disconnect after 30s of silence unless keepalive traffic observed.
  - Future (vNext): optional client→server frames when interactive runs are enabled: `{ "type": "stdin", "encoding": "utf8"|"base64", "data": "<payload>" }`.

Example: Start a one-shot Python run
```json
POST /api/v1/sandbox/runs
{
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "spec_version": "1.0",
  "command": ["python", "-c", "print('hello')"],
  "startup_timeout_sec": 20,
  "timeout_sec": 20,
  "resources": {"cpu": 1, "memory_mb": 512},
  "network_policy": "deny_all"
}
```

State Machine (Runs)

- Phases: `queued` → `starting` → `running` → `completed` | `failed` | `timed_out` | `killed`.
- Transitions:
  - `queued` → `starting`: worker assigned; provisioning begins (image pull/VM boot).
  - `starting` → `running`: command launched; stdout/stderr available via WS.
  - `running` → `completed`: exit_code == 0.
  - `running` → `failed`: exit_code != 0 or unrecoverable runtime error.
  - `starting|running` → `timed_out`: startup or execution timeout exceeded.
  - `starting|running` → `killed`: user cancel or policy kill; message=`canceled_by_user` or reason code.
- Failure `reason_code` examples: `image_pull_failed`, `provision_failed`, `policy_denied`, `exec_failed`, `oom_killed`, `log_cap_exceeded`.

Resource Usage Reporting

- GET `/runs/{run_id}` includes:
  - `resource_usage`: {
    - `cpu_time_sec`: total CPU time used (sum across processes),
    - `wall_time_sec`: execution duration,
    - `peak_rss_mb`: peak resident set size,
    - `max_open_files`: peak file descriptors used,
    - `log_bytes`: total bytes streamed to logs,
    - `artifact_bytes`: total bytes of captured artifacts,
    - `pids`: peak concurrent processes/threads,
    - `limits`: { `cpu`, `memory_mb`, `pids`, `nofile`, `startup_timeout_sec`, `timeout_sec` }
  - }
  - On denial or early failures, `resource_usage` may be partial or omitted.

Idempotency

- POST `/runs` and `/sessions` honor `Idempotency-Key` (opaque, up to 128 chars).
- TTL window: 10 minutes (configurable). Within window, replays with same key and identical body return the original response.
- Mismatch behavior: same key with different body returns 409 Conflict with details referencing original `id`.
- Responses include `idempotency_key_echo` and `idempotency_status` in `details` for audit.


## 10) LSP Integration

Approach: Provide a thin IDE extension that communicates with the Sandbox API and maps results to LSP diagnostics. Where custom actions are needed, use `workspace/executeCommand` with well-known command IDs.

Key UX
- “Run in Sandbox” from editor/codelens.
- Inline diagnostics: exit code summary; map stack-trace frames to workspace files when paths match; otherwise link to sandbox file view.
- Log panel streaming; “Open in tldw” deep link; artifacts browser.

Protocol Hooks
- `tldw.sandbox.run`
  - Args: file list or tar stream reference, working directory, runtime/image, command, env, startup_timeout_sec, timeout_sec, capture patterns.
  - Resp: run_id, initial status; client opens WS to stream logs.
- `tldw.sandbox.configure`
  - Configure defaults (runtime/image, policy hints) per workspace.
- `tldw.sandbox.openArtifacts`
  - Open artifacts panel for last run or by run_id.

Workspace Sync
- Preferred: client sends tar stream of changed files since last run; fallback: list of individual files with base64 content.
- Path mapping: sandbox CWD mirrors workspace root; relative paths preserved.
- Client caches last run spec to enable quick re-run with minor edits.
 - Ignore patterns: `.gitignore`-style patterns exclude VCS, build artifacts, and binaries by default; whitelists can allow specific binaries.

Diagnostics Mapping
- Prioritize the first stack frame that maps to a workspace file; otherwise show a sandbox path with a “reveal in artifacts” link.

Large Logs
- IDE truncates long logs and shows a “View full logs in Web UI” link to `/webui/sandbox/runs/{id}`.

VS Code/JetBrains: initial extension(s) scaffolded with minimal UI, leveraging existing auth from tldw session or API key.

End-to-End Example (Session → Upload → Run → Artifact)

1) Create session
```
POST /api/v1/sandbox/sessions
Content-Type: application/json

{
  "spec_version": "1.0",
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "timeout_sec": 60,
  "network_policy": "deny_all"
}
```
Response
```
{
  "session_id": "3a9e0e5e-...",
  "expires_at": "2025-10-27T12:00:00Z",
  "runtime": "docker"
}
```

2) Upload files (multipart)
```
POST /api/v1/sandbox/sessions/3a9e0e5e-.../files
Content-Type: multipart/form-data; boundary=---BOUNDARY

-----BOUNDARY
Content-Disposition: form-data; name="files"; filename="main.py"
Content-Type: text/x-python

print("Hello from sandbox")
-----BOUNDARY--
```
Response
```
{ "session_id": "3a9e0e5e-...", "bytes_received": 29, "file_count": 1 }
```

3) Start run (referencing session)
```
POST /api/v1/sandbox/runs
Idempotency-Key: 5c2d1a9a-...
Content-Type: application/json

{
  "spec_version": "1.0",
  "session_id": "3a9e0e5e-...",
  "command": ["python", "main.py"],
  "timeout_sec": 20
}
```
Response
```
{
  "run_id": "a1b2c3d4-...",
  "phase": "starting"
}
```

4) Stream logs (WS)
```
GET ws://host/api/v1/sandbox/runs/a1b2c3d4-.../stream
```
Messages
```
{ "type": "stdout", "encoding": "base64", "data": "SGVsbG8gZnJvbSBzYW5kYm94XG4=", "seq": 1 }
{ "type": "event", "event": "end", "data": { "exit_code": 0 } }
```

5) List artifacts
```
GET /api/v1/sandbox/runs/a1b2c3d4-.../artifacts
```
Response
```
{ "items": [ { "path": "results.json", "size": 42, "download_url": "/api/v1/sandbox/runs/a1b2c3d4-.../artifacts/results.json" } ] }
```

6) Download artifact (with Range)
```
GET /api/v1/sandbox/runs/a1b2c3d4-.../artifacts/results.json
Range: bytes=0-1023
```
Response headers include `206 Partial Content`, `Content-Type`, and `Content-Range`.


## 11) MCP Integration

Expose an MCP tool named `sandbox.run` with schema:
```json
{
  "name": "sandbox.run",
  "input_schema": {
    "type": "object",
    "properties": {
      "runtime": {"enum": ["docker", "firecracker"]},
      "session_id": {"type": "string"},
      "base_image": {"type": "string"},
      "command": {"type": "array", "items": {"type": "string"}},
      "files": {"type": "array", "items": {"type": "object", "properties": {"path": {"type": "string"}, "content_b64": {"type": "string"}}}},
      "timeout_sec": {"type": "integer"},
      "env": {"type": "object"}
    },
    "oneOf": [
      { "required": ["session_id", "command"] },
      { "required": ["base_image", "command"] }
    ]
  }
}
```
Policy and RBAC are enforced server-side; agent invocations are auditable. When `session_id` is not provided, `base_image` is required; when `session_id` is provided, `base_image` is derived from the session. Responses include `run_id`, optional `log_stream_url` (WS), and may include `policy_hash` for reproducibility across environments.

Implementation (stub)
- MCP Unified module now exposes `sandbox.run` (management tool) via a stub Sandbox module.
- Tool schema with `oneOf` is returned by MCP; module validates arguments (session vs one‑shot) and executes via internal SandboxService.
- Result includes `policy_hash` and `image_digest` when available. For logs and artifacts, use REST/WS endpoints directly.
- Enable module at runtime with `MCP_ENABLE_SANDBOX_MODULE=1`.


## 12) Security Model

Threats
- Malicious code attempts container/VM breakout, disk exhaustion, CPU/mem DoS, egress to internal services, secrets exfiltration.

Controls (MVP)
- Default deny egress; no inbound network; optional allowlist (future) with explicit domain/IP rules; DNS resolution pinned at run start.
- No host mounts; ephemeral workspace only; read-only root FS where possible; writable tmpfs workdir mounted with `noexec,nodev,nosuid`.
- Resource quotas per run and per user; hard wall-clock timeouts; pids limit; enforced `ulimit` values (`nofile`, `nproc`); swap disabled; optional per-process CPU time cap.
- Docker: rootless engine if supported; hardened seccomp profile; AppArmor; drop all capabilities; `no-new-privileges`; read-only root.
- Firecracker: one microVM per run/session; minimal device exposure; cgroups; snapshot-based immutable root; no tap interface by default.
- Secrets: Not injected by default. If enabled later, mount via tmpfs at well-known path `/run/secrets`; scoped to run; lifecycle-bound; redact values in logs; denylist `/run/secrets/**` from artifact capture.
- Validation: verify archives; prevent path traversal; enforce max files, max depth; block symlinks/hardlinks/device nodes; defend against zip/tar bombs.

Operational Safeguards
- Orphaned resource reaper; periodic cleanup; rate limiting; backpressure.
- Comprehensive audit logs with user, origin (IDE/agent), and model context.

User Identity & Default Limits
- Processes run as non-root random UID/GID per run; no supplemental groups.
- Default hard limits (configurable): `pids=256`, `nofile=1024`, `nproc=512`, `max_log_bytes=10MB`.
  - Docker runner enforces `--ulimit nofile=1024:1024`, `--ulimit nproc=512:512`, and `--ulimit core=0:0`.
- CPU time cap: enforce RLIMIT_CPU ≈ `timeout_sec + 2s grace` when available.


## 13) Images, Languages, and Environments

Curated base images (initial)
- `python:3.11-slim`, `node:20-alpine` (Node.js), `golang:1.22-alpine`, `eclipse-temurin:17-jre`, `mcr.microsoft.com/dotnet/sdk:8.0`.
- A generic BusyBox/Ubuntu image for shell scripts.

Image hardening
- Read-only root; essential build tools optional via build variants; pinned digests where feasible; vulnerability scanning in CI; signed images where supported.

Workspace inputs
- Tar/zip upload, safe extract; optional git clone (shallow) + patch; server-side `.dockerignore`-like filtering.
 - Artifact capture never follows symlinks; symlinks are listed as zero-length metadata entries, not dereferenced.


## 14) Storage & Artifacts

- Per-run ephemeral workspace with size cap (e.g., 256 MB by default, configurable).
- Artifact capture by glob allowlist (e.g., `dist/**`, `coverage/**`, `results.json`).
- Persistence: artifacts are copied back and stored on disk under `tmp_dir/sandbox/<user_id>/runs/<run_id>/artifacts/`.
- Byte caps: per-run and per-user total artifact bytes enforced via `SANDBOX_MAX_ARTIFACT_BYTES_PER_RUN_MB` and `SANDBOX_MAX_ARTIFACT_BYTES_PER_USER_MB`.
- Retention policy: default 24h; admin-configurable; hard max size per user/day.
- Download via authorized URLs; support HTTP Range for resumable/partial downloads; server-side streaming for large artifacts; gzip-compress text artifacts on the fly when accepted by client.

Storage Layout (reference)
- Root: `<sandbox_root>/` (configurable)
- Per-user: `<sandbox_root>/<user_id>/`
- Per-session: `<sandbox_root>/<user_id>/sessions/<session_id>/workspace/`
- Per-run: `<sandbox_root>/<user_id>/runs/<run_id>/{workspace,artifacts,logs}/`
- GC: periodic sweeper deletes expired sessions/runs; deletes are scoped to these roots with strict path normalization.

Store & Metadata (current)
- Default pluggable store: SQLite (`SANDBOX_STORE_BACKEND=sqlite`) persists runs and idempotency; `memory` backend for dev/tests.
- SQLite path defaults to `<PROJECT_ROOT>/tmp_dir/sandbox/meta/sandbox_store.db` (override with `SANDBOX_STORE_DB_PATH`).
- Stored fields: run id, owner, spec_version, runtime, base_image, phase, exit_code, timestamps, message, image_digest, policy_hash; idempotency fingerprints with TTL.


## 15) Observability

Metrics
- Runs started/completed/failed; queue wait time; start latency; runtime; resource usage; cancellations; timeouts; artifact sizes; per-runtime breakdown.
- Sandbox metrics (current):
  - `sandbox_sessions_created_total{runtime}`
  - `sandbox_runs_started_total{runtime}`
  - `sandbox_runs_completed_total{runtime,outcome}`
  - `sandbox_run_duration_seconds{runtime,outcome}` (histogram)
  - `sandbox_upload_bytes_total{kind}` and `sandbox_upload_files_total{kind}`

Logs
- Structured JSON logs with trace_id, user_id, run_id, runtime, image, command, exit_code, error class, and policy decisions.

Tracing
- Optional OpenTelemetry spans for API → orchestrator → runtime; link to originating chat/thread and LSP session.
 - Reproducibility: persist base image digest, runtime version, policy hash, and `spec_version` with run metadata.

Auditing
- API request/response audit events include policy and reproducibility metadata. Run completion events record `policy_hash` and `image_digest` when available (both sync and background paths).


## 16) Performance Targets (MVP)

- P95 run start (Docker warm): < 2s; Firecracker warm: < 5s.
- P99 log delivery latency: < 200ms.
- Max concurrent runs per node: configurable; default 8 (subject to host resources).
- Queue fairness: simple per-user concurrency caps to avoid starvation.

Backpressure & Queueing
- Defaults: max queue length=100 (configurable), queue TTL=120s. When full, return 429 with `Retry-After`; when queued, return `queued` phase and include `estimated_start_time`.

Warm Pools & Caching
- Docker: pre-pull base images; avoid paused containers for security/complexity reasons.
- Firecracker: use VM snapshots for fast boot; pin kernel/version; rebuild snapshots on image updates or security patches.


## 17) Admin & Policy

- Runtime selection policy: Docker default on macOS/Windows; Firecracker allowed on supported Linux hosts (direct integration).
- Quotas: per-user daily CPU-seconds cap; concurrent run cap; total artifacts size/day.
- Network policy: deny_all default; allowlist domains (vNext) per policy; domain wildcards controlled via config.
- Approvals: optional manual approval gates for large runs or network-enabled runs.
 - Audit retention: default 30 days (configurable). Redact sensitive file names/paths in audit logs if policy requires; never log secrets.

Configuration Keys (examples)
- `SANDBOX_DEFAULT_RUNTIME` (docker|firecracker)
- `SANDBOX_NETWORK_DEFAULT` (deny_all|allowlist)
- `SANDBOX_MAX_UPLOAD_MB`
- `SANDBOX_ARTIFACT_TTL_HOURS`
- `SANDBOX_MAX_CONCURRENT_RUNS`
- `SANDBOX_MAX_LOG_BYTES`
- `SANDBOX_PIDS_LIMIT`
- `SANDBOX_MAX_CPU` / `SANDBOX_MAX_MEM_MB`
- `SANDBOX_WORKSPACE_CAP_MB`
- `SANDBOX_SUPPORTED_SPEC_VERSIONS`
- `SANDBOX_IDEMPOTENCY_TTL_SEC`
- `SANDBOX_ENABLE_EXECUTION` (false by default)
- `SANDBOX_BACKGROUND_EXECUTION` (false by default)
- `SANDBOX_DOCKER_SECCOMP` (path to seccomp JSON)
- `SANDBOX_DOCKER_APPARMOR_PROFILE`
- `SANDBOX_ULIMIT_NOFILE` (default 1024)
- `SANDBOX_ULIMIT_NPROC` (default 512)
- `SANDBOX_MAX_ARTIFACT_BYTES_PER_RUN_MB` (default 32)
- `SANDBOX_MAX_ARTIFACT_BYTES_PER_USER_MB` (default 128)
- `SANDBOX_STORE_BACKEND` (sqlite|memory; default sqlite)
- `SANDBOX_STORE_DB_PATH` (optional explicit SQLite path)

Feature Discovery Payload (example)
```
GET /api/v1/sandbox/runtimes
{
  "runtimes": [
    {
      "name": "docker",
      "available": true,
      "default_images": [
        "python:3.11-slim@sha256:...",
        "node:20-alpine@sha256:..."
      ],
      "max_cpu": 4.0,
      "max_mem_mb": 8192,
      "max_upload_mb": 64,
      "max_log_bytes": 10485760,
      "workspace_cap_mb": 256,
      "artifact_ttl_hours": 24,
      "supported_spec_versions": ["1.0", "1.1"],
      "notes": null
    },
    {
      "name": "firecracker",
      "available": false,
      "default_images": ["python:3.11-slim"],
      "max_cpu": 4.0,
      "max_mem_mb": 8192,
      "max_upload_mb": 64,
      "max_log_bytes": 10485760,
      "workspace_cap_mb": 256,
      "artifact_ttl_hours": 24,
      "supported_spec_versions": ["1.0"],
      "notes": "Direct Firecracker; enable on supported Linux hosts"
    }
  ]
}
```

Network Allowlist Rules (vNext)
- Rule format:
  - Exact host: `example.com`
  - Wildcard subdomains: `*.example.com`
  - CIDR blocks: `203.0.113.0/24`
- DNS pinning: resolve allowed hostnames at run start; pin IPs for duration to avoid TOCTOU; re-resolution disallowed mid-run.
- Path/port rules: out of scope for v0; only egress domain/IP controls.


## 18) IDE/Web UI Experience

- IDE: command palette “Run in Sandbox”; code lens over main() or test files; diagnostics showing exit code and error lines; logs panel; open artifacts.
- Web UI: panel in tldw WebUI to submit code, view live logs, download artifacts, and copy reproducible run spec.

LSP / VS Code Stub
- A minimal VS Code extension stub is provided at `Helper_Scripts/IDE/vscode-sandbox/`.
- Command: `tldw.sandbox.run` prompts for a command array and posts to `/sandbox/runs`.
- Configure `tldw.sandbox.serverUrl` and `tldw.sandbox.apiKey`.

Stack Trace Mapping
- Python: parse Traceback frames; map to workspace files by relative path; otherwise show sandbox path hint.
- Node.js: parse V8 stack traces; support source maps when uploaded; map to workspace if paths match.
- Go/Java: parse standard stack formats; map by file:line.


## 19) Rollout Plan

Phase 0: Design & Stubs (this PRD)
- API contracts stabilized; mock endpoints; sample LSP extension stub.

Phase 1: Docker MVP
- One-shot runs, uploads, logs streaming, artifacts, quotas, audit.
- Admin toggles and basic policy.

Phase 2: Firecracker Support
- Linux hosts with Firecracker; microVM images; feature discovery endpoint.

Phase 3: Sessions & Caching
- Short-lived sessions; warm pools; optional read-only network allowlists.

Phase 4: Approvals & Secrets (opt‑in)
- Manual approval gates; scoped secret mounts; enhanced auditing.


## 20) Acceptance Criteria (MVP)

- Endpoints implemented under `/api/v1/sandbox/*` with auth, rate limiters, and meaningful errors.
- Docker runs complete with resource limits, timeouts, and artifact capture.
- WS log streaming works with defined message envelope; clients handle reconnect, heartbeats, and tail; server enforces log cap.
- IDE extension can trigger a run and render logs + a diagnostic summary.
- Idempotency for POST /runs and /sessions via Idempotency-Key header.
- Tests: unit (runners, policy), integration (happy paths, timeouts, quotas), and security (archive traversal prevention, resource caps enforced).
- Documentation: API reference, IDE setup, admin policy examples.

Implementation Status (v0.2)
- Implemented: `/sessions` (Idempotency-Key), `/sessions/{id}/files` (safe tar/zip/plain; traversal protection; workspace cap), `/runs` (Idempotency-Key), `/runs/{id}`, `WS /runs/{id}/stream`, `/runs/{id}/artifacts`, `/runs/{id}/artifacts/{path}`, `/runtimes`.
- Runner: Docker create → cp (workspace + inline) → start → logs (WS) → wait → cp artifacts → remove; read-only root, drop caps, `no-new-privileges`, tmpfs workdir, non-root user, deny_all by default; optional seccomp/AppArmor and enforced ulimits.
- Idempotency: Persistent via default SQLite store (TTL 600s); conflicting replay returns 409 `idempotency_conflict`.
- WS streaming: heartbeats, backpressure, log caps, start/end events; fake-exec test added. Sequence numbers planned.
- Discovery: Includes `workspace_cap_mb`, `artifact_ttl_hours`, `supported_spec_versions`.
- Artifacts: Persisted to filesystem; per-run and per-user byte caps enforced; list and download endpoints; new test covers list+download.
- Policy hash included in run status; image digest collected best-effort post-run.
- Background: Optional via `SANDBOX_BACKGROUND_EXECUTION`; background run completion now emits audit events with policy_hash/image_digest.
- Store: Pluggable store for runs/idempotency (default SQLite, dev memory) with optional DB path override.

Known Limitations (v0.2)
- Cancel endpoint is a stub; killing active runs not wired to Docker yet.
- WS frames do not include `seq` yet; schema includes it for vNext.
- Startup vs execution timeout split not fully enforced (single `timeout_sec` in runner).
- Orchestrator store is single-node SQLite; multi-worker scaling requires a shared DB and artifact bucket.


## 21) Risks & Mitigations

- Container/VM breakout: Hardened configs; least privilege; Firecracker recommended for untrusted code on Linux; regular CVE scanning.
- Resource exhaustion: Strict quotas; backpressure; per-user concurrency caps.
- Complexity of multi-runtime support: Clear abstraction layer for runners; feature discovery endpoint.
- Host variability: Docker rootless not always available; detect and degrade gracefully.
- Developer UX friction: Provide reproducible specs; fast feedback; warm pools.


## 22) Decisions

- Languages/images for v0: Python and Node.js prioritized (`python:3.11-slim`, `node:20-alpine`).
- Firecracker integration: Direct Firecracker SDK/CLI (ignite is EOL); snapshots for fast boot.
- Network policy: Deny-all by default; configurable allowlist in policy.
- MVP IDEs: VS Code first; JetBrains next.
- Artifact retention: default 24h with org-level overrides.


## 23) Implementation Notes (tldw_server)

- Location
  - Endpoints: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`
  - Core: `tldw_Server_API/app/core/Sandbox/` with `runners/docker_runner.py`, `runners/firecracker_runner.py`, `models.py`, `policy.py`.
  - Schemas: `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py`
  - Tests: `tldw_Server_API/tests/sandbox/` (unit + integration with mocked runtimes).

- Dependencies
  - Reuse existing AuthNZ, rate limits, logging (loguru), and error handling patterns.
  - No external network calls in tests; mock runners.
  - Execution behind `SANDBOX_ENABLE_EXECUTION`; CI uses fake exec (`TLDW_SANDBOX_DOCKER_FAKE_EXEC=1`).

- Config
  - Add config keys under `Config_Files/config.txt` and/or env vars: runtime defaults, quotas, artifact TTLs, max upload size.
  - Additional keys: `SANDBOX_WORKSPACE_CAP_MB`, `SANDBOX_SUPPORTED_SPEC_VERSIONS`, `SANDBOX_IDEMPOTENCY_TTL_SEC`, `SANDBOX_ENABLE_EXECUTION`, `SANDBOX_BACKGROUND_EXECUTION`, `SANDBOX_DOCKER_SECCOMP`, `SANDBOX_DOCKER_APPARMOR_PROFILE`, `SANDBOX_ULIMIT_NOFILE`, `SANDBOX_ULIMIT_NPROC`, `SANDBOX_MAX_ARTIFACT_BYTES_PER_RUN_MB`, `SANDBOX_MAX_ARTIFACT_BYTES_PER_USER_MB`, `SANDBOX_STORE_BACKEND`, `SANDBOX_STORE_DB_PATH`.

Local Run (Dev)
- Enable execution (optional fake mode):
  - `export SANDBOX_ENABLE_EXECUTION=true`
  - Optional background: `export SANDBOX_BACKGROUND_EXECUTION=true`
- CI/dev without Docker: `export TLDW_SANDBOX_DOCKER_FAKE_EXEC=1`
- Hardened defaults shipped:
  - Seccomp: `tldw_Server_API/Config_Files/sandbox/seccomp_default.json`. Enable via `export SANDBOX_DOCKER_SECCOMP=.../seccomp_default.json` (enabled by default when present).
  - AppArmor (example): `tldw_Server_API/Config_Files/sandbox/apparmor/tldw-sandbox.profile`. Load with `apparmor_parser` and set `SANDBOX_DOCKER_APPARMOR_PROFILE=tldw-sandbox`.
  - Egress is denied by default (`--network none`).
- Launch API:
  - `python -m uvicorn tldw_Server_API.app.main:app --reload`
- Typical flow:
  - `POST /api/v1/sandbox/sessions` (store returned `session_id`)
  - `POST /api/v1/sandbox/sessions/{session_id}/files` (tar/zip/plain)
  - `POST /api/v1/sandbox/runs` with `{ session_id, command, capture_patterns }`
  - `WS /api/v1/sandbox/runs/{run_id}/stream` for live logs and events
  - `GET /api/v1/sandbox/runs/{run_id}/artifacts` → download via `/artifacts/{path}`

Testing
- Run sandbox tests only:
  - `pytest -q tldw_Server_API/tests/sandbox`
- WS stream (fake exec) verifies start/end events:
  - Test: `tests/sandbox/test_ws_stream_fake.py`
- Idempotency behavior (sessions/runs):
  - Tests: `tests/sandbox/test_sandbox_api.py` (replay same key/body returns original; conflict → 409)
- Docker fake execution path:
  - Test: `tests/sandbox/test_docker_runner_fake.py`


## 24) Firecracker vs Docker (Appendix)

- Docker
  - Pros: Ubiquitous; easy local dev on macOS/Windows/Linux; large image ecosystem.
  - Cons: Weaker isolation vs microVMs; rootless varies by host; relies on kernel features and profiles for defense-in-depth.

- Firecracker
  - Pros: Stronger isolation via microVMs; smaller attack surface; snapshotting for fast boot.
  - Cons: Linux-only; operationally more complex; image management pipeline required.

MVP Strategy: Default to Docker where Firecracker isn’t available; expose a feature discovery endpoint so clients can adapt.


## 25) Appendix: Example Run Specs

Python (inline script)
```json
{
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "spec_version": "1.0",
  "command": ["python", "-c", "print('HI!')"],
  "timeout_sec": 15,
  "resources": {"cpu": 1, "memory_mb": 512},
  "network_policy": "deny_all"
}
```

Node.js (inline script)
```json
{
  "runtime": "docker",
  "base_image": "node:20-alpine",
  "spec_version": "1.0",
  "command": ["node", "-e", "console.log('HI!')"],
  "timeout_sec": 10,
  "network_policy": "deny_all"
}
```

Runner Interface (reference)
- `prepare(spec)`: provision workspace, resolve image/VM snapshot.
- `execute(spec)`: start process; attach logs; enforce limits.
- `collect(spec)`: capture artifacts by allowlist; compute metadata.
- `cleanup(spec)`: teardown workspace/container/VM; ensure no leaks.

---

End of PRD v0.2
 
## 26) Admin: Inspecting the SQLite Store (Appendix)

This section provides quick, copy‑paste snippets to inspect the default SQLite store used by the sandbox service.

Defaults
- Location (default): `<PROJECT_ROOT>/tmp_dir/sandbox/meta/sandbox_store.db`
- Override via: `SANDBOX_STORE_DB_PATH`

Open the DB
```
sqlite3 tmp_dir/sandbox/meta/sandbox_store.db
```

List recent runs (last 20)
```
SELECT id, user_id, runtime, base_image, phase, exit_code, started_at, finished_at
FROM sandbox_runs
ORDER BY COALESCE(finished_at, started_at) DESC
LIMIT 20;
```

Show a single run (by id)
```
SELECT * FROM sandbox_runs WHERE id = '<run_id>';
```

Count idempotency entries (by endpoint)
```
SELECT endpoint, COUNT(*) AS entries
FROM sandbox_idempotency
GROUP BY endpoint
ORDER BY entries DESC;
```

Inspect idempotency fingerprint (one row)
```
SELECT endpoint, user_key, key, LENGTH(response_body) AS resp_bytes, datetime(created_at, 'unixepoch') AS created
FROM sandbox_idempotency
ORDER BY created_at DESC
LIMIT 5;
```

Per‑user artifact bytes
```
SELECT user_id, artifact_bytes FROM sandbox_usage ORDER BY artifact_bytes DESC;
```

Cleanup expired idempotency (manual)
```
-- TTL enforcement runs automatically; to force cleanup:
DELETE FROM sandbox_idempotency WHERE created_at < strftime('%s','now') - 600; -- 600s or match SANDBOX_IDEMPOTENCY_TTL_SEC
```

Notes
- The store is single‑node and intended for a single server process. For multi‑worker or multi‑node, migrate to a shared SQL database and a shared artifact bucket.
- Timestamps in `sandbox_runs` are ISO‑8601 strings; prefer lexicographical order for recency.

## 27) Store Data Model (Appendix)

Tables (current)
- `sandbox_runs`
  - Keys: `id` (PK)
  - Columns: `user_id`, `spec_version`, `runtime`, `base_image`, `phase`, `exit_code`, `started_at`, `finished_at`, `message`, `image_digest`, `policy_hash`.
  - Purpose: Authoritative run status/metadata; updated on transitions and completion.

- `sandbox_idempotency`
  - Keys: `(endpoint, user_key, key)` (PK)
  - Columns: `fingerprint` (SHA‑256 of canonical request body), `object_id` (run/session id), `response_body` (JSON), `created_at` (epoch seconds).
  - Purpose: Dedupe client retries across `/sessions` and `/runs`.
  - TTL: Old rows pruned by TTL (config: `SANDBOX_IDEMPOTENCY_TTL_SEC`).

- `sandbox_usage`
  - Keys: `user_id` (PK)
  - Columns: `artifact_bytes` (cumulative snapshot updated by orchestrator).
  - Purpose: Enforce per‑user artifact byte caps.

Relationships & Notes
- `sandbox_runs.user_id` is a string identifier; no foreign key to an auth table.
- Idempotency rows are independent; `object_id` may reference `sandbox_runs.id` or a session id.
- Cleanup jobs should combine DB row deletion with on‑disk artifact retention policy (`SANDBOX_ARTIFACT_TTL_HOURS`).
- For HA scenarios, use a shared SQL DB and a shared filesystem/object store for artifacts.
