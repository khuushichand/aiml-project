# Sandbox

## 1. Descriptive of Current Feature Set

- Purpose: An isolated execution scaffold with sessions, queued runs, idempotency, and artifact streaming.
- Capabilities:
  - Create/destroy sessions; upload files to session
  - Queue runs with TTL and capacity limits; cancelation support
  - Stream run events via WebSocket; secure artifact download URLs
- Inputs/Outputs:
  - Inputs: JSON payloads for sessions/runs; file uploads; WS control frames
  - Outputs: run statuses, artifacts, stream frames, health states
- Related Endpoints:
  - `tldw_Server_API/app/api/v1/endpoints/sandbox.py:82` (router + endpoints: health, sessions, runs, stream, admin)
- Related Models:
  - `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - `SandboxOrchestrator` manages sessions, runs, idempotency storage via `store`; queue pruning by TTL
- Key Classes/Functions:
  - Orchestrator: `core/Sandbox/orchestrator.py:1`; Policy/config in `core/Sandbox/policy.py`; store/cache/streams modules
- Dependencies:
  - Internal: Metrics counters; Audit logging; feature flags
- Data Models & DB:
  - In-memory store by default (pluggable via `store`)
- Configuration:
  - Queue: `SANDBOX_QUEUE_MAX_LENGTH`, `SANDBOX_QUEUE_TTL_SEC`, `SANDBOX_QUEUE_ESTIMATED_WAIT_PER_RUN_SEC`
  - Idempotency TTL: `SANDBOX_IDEMPOTENCY_TTL_SEC`
- Concurrency & Performance:
  - Lock-guarded maps; minimal O(1) operations; histograms for durations
- Error Handling:
  - Idempotency conflict surfaces original id and created_at; safe streaming cleanup on exceptions
- Security:
  - Artifact path guard to prevent traversal; route class wrapper for download URLs

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Sandbox/` with `models.py`, `orchestrator.py`, `service.py`, `store.py`, `streams.py`, `policy.py`, runner stubs
- Extension Points:
  - Implement durable stores and real runners (docker/firecracker runners are stubs here)
- Coding Patterns:
  - Keep API thin; push logic into orchestrator/service; add metrics/audit labels consistently
- Tests:
  - (Scaffold) Add end-to-end tests using WS and queue limits as the module matures
- Local Dev Tips:
  - Use `/api/v1/sandbox/health` and `/api/v1/sandbox/runs` for quick validation; enable synthetic test frames in config when available
- Pitfalls & Gotchas:
  - Queue backpressure and TTL pruning; large artifact payloads
- Roadmap/TODOs:
  - Pluggable backends for store and runners; per-tenant quotas
