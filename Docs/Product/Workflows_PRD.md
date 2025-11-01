# Workflows PRD (v0.1)

## Objective

Add a first-class Workflows module enabling users to define, run, and monitor multi-step processes that compose existing tldw_server capabilities. Support async background (agentic) and synchronous (guided review) execution with human-in-the-loop steps. v0.1 is linear-only to ship safely with solid reliability and security foundations.

## Outcome

A minimal DSL, execution engine, APIs, and WebUI hooks to create and execute workflows that chain prompts, RAG, MCP tools, and review steps.

## Implementation Snapshot (current)

- Engine: Linear execution with per-step retries, timeouts, pause/resume, cooperative cancel, durable checkpoints, leases/heartbeats, and orphan reaper.
- Steps implemented: `prompt`, `rag_search`, `media_ingest`, `mcp_tool`, `webhook`, `wait_for_human`.
- Concurrency: In-process scheduler with per-tenant and per-workflow limits (env: `WORKFLOWS_TENANT_CONCURRENCY` default 2; `WORKFLOWS_WORKFLOW_CONCURRENCY` default 1).
- Streaming/events: WS at `/api/v1/workflows/ws` with JWT + run-level auth; HTTP polling supported; strict `event_seq` ordering.
- Storage: SQLite (WAL) in `Databases/workflows.db`; supports `DATABASE_URL_WORKFLOWS` for SQLite URIs; runs optionally record `tokens_input|tokens_output|cost_usd`.
- Subprocess lifecycle: For subprocess steps, record `pid/pgid/workdir/stdout/stderr`; engine-driven cancellation escalates process-group termination; logs tails attached to events/metadata.
- Artifacts: `workflow_artifacts` table and `GET /api/v1/workflows/runs/{run_id}/artifacts` endpoint available (v0.2 surface).
- Security: Tenant isolation on reads; definition size/step limits; webhook + HTTP ingest egress allowlist/private IP blocking; HMAC signing for webhooks; ad-hoc run rate limits.
- Sync UX: `mode=sync|async` both execute server-side; UI reattaches by `run_id` and event replay for guided flows.

## Goals

- Composable steps: Chain existing capabilities (LLM, RAG, MCP tools, webhooks).
- Dual modes: Async background runs and synchronous guided sessions.
- Human review: Explicit “wait_for_human” steps with approve/reject and input capture.
- Observability: Run/step status, event stream, logs, artifacts, and error details.
- Safety & control: AuthNZ, rate limits, retries, timeouts, idempotency, versioning.
 - Security: SSRF/egress controls for webhooks/tools; WS auth; CSRF in WebUI.

## Non-Goals (v0.1)

- Full BPMN: No complex BPMN editors or arbitrary sub-process nesting.
- Arbitrary code: No user-supplied Python execution in-process.
- Distributed workers: Single-process/default in-app worker only (pluggable later).
- Branching/parallelism: v0.1 is linear only; conditionals/parallelism in v0.2.

## Personas & Use Cases

- Researcher: Chain ingest → transcribe → summarize → RAG QA → export notes.
- Analyst (guided): Step-through document review with prompts and approvals.
- Ops (manual): Run on-demand sweep for new media → index → notify via webhook (schedules in v0.2).
- QA/Evals (manual): Small sets of prompt/tests → aggregate → export report (loops/aggregation in v0.2).

## Scope (v0.1 MVP)

- Workflow definition: JSON/YAML schema with steps and templated inputs. Linear transitions only (no branch).
- Step types (v0.1): `media_ingest`, `prompt`, `rag_search`, `mcp_tool`, `webhook`, `wait_for_human`.
- Execution modes: `mode=async|sync` with resumable state for async; session-guided sync.
- Engine: Linear pipeline with retries, timeouts, durable checkpoints, leases/heartbeats.
- APIs: Immutable versioned definitions; run, status, pause/resume/cancel; approve/reject human steps; retry failed run; event stream.
- WebUI: Minimal list/detail views, live run updates, human step approval UI with CSRF protection.

## Out of Scope (later)

- Branch step and conditionals (v0.2) with a minimal JSONLogic-like expression subset.
- STT/TTS adapters (v0.2) and artifact storage/metrics promotion to first-class.
- Parallel/foreach: Fan-out/fan-in, foreach loops (v0.2).
- Schedules/triggers: Time-based schedules, inbound webhook triggers (v0.2).
- Advanced cost controls: Budgets/quotas enforcement (v0.2).
- Graph editor: Visual DAG builder (v0.3).
- Data transformation step (sandboxed) without arbitrary code (v0.3).

## Architecture

- Core module: `tldw_Server_API/app/core/Workflows/` with engine, registry, adapters.
- DB layer: `WorkflowsDatabase` in `/app/core/DB_Management/` (SQLite default, Postgres supported). Enable SQLite WAL and durable journaling.
- API surface: `app/api/v1/endpoints/workflows.py` and `app/api/v1/schemas/workflows.py`.
- Scheduler & Engine: In-process scheduler and engine under `/app/core/Workflows/` for orchestration and event dispatch, with leases, heartbeats, and orphan reaper.
- Streaming: WebSocket at `/api/v1/workflows/ws` for run events; HTTP polling fallback. WS requires JWT and run-level authorization.
- Integrations: Use `Ingestion_Media_Processing`, `LLM_Calls`, `RAG`, `MCP_unified`, `Audio`, `Chatbooks`.
- Observability: OpenTelemetry spans (run → step → provider) and Prometheus metrics.

## Storage

- Separate database: Dedicated SQLite database `Databases/workflows.db` (or Postgres). Enable WAL + durable journaling by default. Honors `DATABASE_URL_WORKFLOWS` when using `sqlite://` URIs for custom paths.
- Rationale: Isolation from media/auth DBs improves reliability, performance, and schema evolution. Postgres supported via `DATABASE_URL_WORKFLOWS`.

## Data Model

Tables (SQLite default; Postgres supported). All include `tenant_id` for isolation:

- workflows: `id`, `tenant_id`, `name`, `version`, `owner_id`, `visibility`, `description`, `tags`, `definition_json`, `created_at`, `updated_at`, `is_active`.
- workflow_runs: `run_id`, `tenant_id`, `workflow_id`, `status` (queued|running|waiting_human|paused|succeeded|failed|cancelled), `status_reason`, `user_id`, `inputs_json`, `outputs_json`, `error`, `duration_ms`, `tokens_input`, `tokens_output`, `cost_usd`, `created_at`, `started_at`, `ended_at`, `definition_version`, `definition_snapshot_json`, `idempotency_key`, `session_id`.
- workflow_step_runs: `step_run_id`, `tenant_id`, `run_id`, `step_id`, `name`, `type`, `status`, `attempt`, `started_at`, `ended_at`, `inputs_json`, `outputs_json`, `error`, `assigned_to`, `decision` (pending|approved|rejected), `approved_by`, `approved_at`, `review_comment`, `locked_by`, `locked_at`, `lock_expires_at`, `heartbeat_at`, `pid`, `pgid`, `workdir`, `stdout_path`, `stderr_path`.
- workflow_events: `event_id`, `tenant_id`, `run_id`, `step_run_id`, `event_seq`, `event_type`, `payload_json`, `created_at`.
- workflow_artifacts: `artifact_id`, `tenant_id`, `run_id`, `step_run_id`, `type`, `uri`, `size_bytes`, `mime_type`, `checksum_sha256`, `encryption`, `owned_by`, `metadata_json`, `created_at`.

## Workflow DSL (v0.1)

- Format: Pydantic-backed JSON (YAML accepted, converted to JSON).
- Templating: Jinja SandboxedEnvironment with a strict whitelist of filters/functions; no imports; no attribute access to unsafe objects; bounded render time. Example: `{{ steps.extract_summary.outputs.text }}`.
- Transitions: Linear flow with `on_success` and optional `on_failure` to next step ids. No `branch` in v0.1.
- Controls: `retry` (max_attempts, backoff with jitter), `timeout_seconds`. Human review uses explicit `wait_for_human` step (no `requires_approval`).

Example (abridged):

```json
{
  "name": "Doc Review Guided",
  "version": 1,
  "inputs": {"doc_path": "string", "questions": ["string"]},
  "steps": [
    {"id":"ingest","type":"rag_search","config":{"query":"{{ inputs.questions[0] }}","top_k":5},"on_success":"draft"},
    {"id":"draft","type":"prompt","config":{"model":"gpt-4o-mini","prompt":"Summarize:\n{{ steps.ingest.outputs.context }}","max_tokens":512}, "on_success":"review"},
    {"id":"review","type":"wait_for_human","config":{
        "instructions":"Review the summary. Edit for clarity and approve.",
        "assigned_to_user_id":"{{ inputs.reviewer_id }}",
        "timeout_seconds":86400,
        "form_schema":{
          "final_summary": {"type":"textarea","default":"{{ steps.draft.outputs.text }}"},
          "comment": {"type":"text","label":"Reason for changes (optional)"}
        }
      },
      "on_success":"notify",
      "on_failure":"draft",
      "on_timeout":"notify_timeout"},
    {"id":"notify","type":"webhook","config":{"url":"https://example.com/hook","signing":{"type":"hmac-sha256","secret_ref":"WEBHOOK_SECRET"},"egress_policy":{"allowlist":["https://example.com"]},"timeouts":{"connect_ms":2000,"read_ms":10000},"max_bytes":1048576,"follow_redirects":false},"on_success":null}
  ]
}
```

## Step Types (v0.1)

- prompt: Calls `LLM_Calls` with template; supports streaming in sync mode; limits via `max_tokens` and `max_output_bytes`.
- rag_search: Uses `RAG` to fetch contexts; configurable top_k, rerank.
- mcp_tool: Calls MCP tool by `tool_name` with JSON args; returns result payload. Sensitive tools may require explicit allowlisting per workflow.
- webhook: POST to external HTTP endpoint with payload; records response. Enforce HTTPS, allowlist, HMAC signing, timeouts, no redirects by default.
- wait_for_human: Blocks until approval/reject with optional edited payload. Supports `form_schema`, `assigned_to_user_id`, and `on_timeout`. Default behavior in v0.1 is to wait indefinitely until action, unless a `timeout_seconds` is configured.
- media_ingest: Downloads/ingests URLs or local paths via `/app/core/Ingestion_Media_Processing/`; extracts text/metadata, chunks, and optionally indexes into RAG.

Note: `branch`, `tts`, and `transcribe_audio` are targeted for v0.2.

## Execution Semantics

- Sync runs: Executes steps inline; streams partial results; returns final output when finished.
- Async runs: Enqueue and execute via in-process worker; persist after each step; resumable.
- Retries/timeouts: Per-step policy; exponential backoff with jitter (configurable base/max).
- Checkpoints: Save `inputs/outputs/status` pre- and post-step; resume safely after restarts.
- Leases & heartbeats: On step start, acquire a lease (`locked_by`, `lock_expires_at`) and heartbeat until completion; a reaper re-queues stale steps.
- Idempotency (API): `Idempotency-Key` header scoped to `(tenant_id, owner_id, workflow_id)` with 24h TTL; duplicates return prior run id/result.
- Outbound idempotency: Include `X-Workflow-Id`, `X-Run-Id`, `X-Step-Id`, `X-Attempt` in webhook/tool requests.
- Pause/Cancel: `pause` takes effect between steps; `cancel` sets a cooperative flag that steps must poll and honor.
- Completion webhooks: Optional `on_completion_webhook` receives terminal run payload on `succeeded|failed|cancelled`.
- Ingestion steps may be long-running; checkpoint after each source; obey global and per-step timeouts.

### Sync UX & Recovery

- Synchronous (“guided”) runs are not tied to the client connection; they are regular runs with the UI subscribed to their event stream.
- If a browser/tab disconnects, the run continues server-side. The user can reattach using `run_id` (+ JWT) via:
  - `GET /api/v1/workflows/runs/{run_id}` to fetch current state
  - `GET /api/v1/workflows/runs/{run_id}/events?since=event_seq` or `WS /api/v1/workflows/ws?run_id=...` to resume live updates
- A `session_id` is stored on the run when created; the UI uses it to restore context. No work is lost; human-wait steps remain in `waiting_human` until acted on or timed out.

### Cancellation & Termination

- Cooperative cancel: Steps poll a cancellation flag; engine marks step/run `cancelled` and stops scheduling next steps.
- Forceful termination: For subprocess-backed steps (e.g., `media_ingest` with `yt-dlp/ffmpeg`), the engine spawns processes in their own process group and on cancel escalates: SIGTERM → grace period → SIGKILL of the group. Outputs from killed steps are discarded.
- Non-subprocess steps: If not killable, cancel marks the step as `cancelled`; late results are ignored and logged. Always enforce per-step timeouts as a backstop.

#### Cancellation Plumbing (Subprocess Steps)

- Process model:
  - Wrap subprocess work in a `SubprocessTask` with fields: `pid`, `pgid` (POSIX), `job_handle` (Windows), `start_ts`, `stdout_path`, `stderr_path`.
  - Engine records `step_run_id`, `pid`, `pgid/job`, and `workdir` in DB at start; heartbeat includes child liveness.
  - All subprocess steps must launch via a common helper to ensure consistent lifecycle handling.

- Launch
  - POSIX: `subprocess.Popen([...], start_new_session=True)` to create a new process group. Capture stdout/stderr to rotating files and tail them to events.
  - Windows: `creationflags=CREATE_NEW_PROCESS_GROUP`. Prefer Job Objects for group termination (if available). Fallback to `psutil` recursive kill.

- Cancel path (server)
  - Set run + step cancel flags; emit `cancel_requested` event with `attempt` and `ts`.
  - POSIX: `os.killpg(pgid, SIGTERM)`, wait `grace_ms` (default 5000), then `os.killpg(pgid, SIGKILL)` if still alive.
  - Windows: If using Job Objects, `TerminateJobObject`; else send `CTRL_BREAK_EVENT` to group, wait `grace_ms`, then recurse kill children via `psutil` with `kill()`.
  - After termination, mark step `cancelled`, attach truncated logs (last N KB), and clean temporary files.

- Timeouts & hangs
  - A watchdog monitors `timeout_seconds` per step. On timeout, follow the same escalation as cancel.
  - If heartbeat misses > `lock_expires_at`, reaper attempts termination of stray processes for that step (using stored pid/pgid/job).

- Orphan process reaping
  - On engine startup, scan DB for any `running`/`queued` steps without active leases; if stored `pid/pgid/job` still alive, apply termination escalation and mark step `failed` with `status_reason=orphan_reaped`.

- Safety & isolation
  - Never kill by name; only target recorded `pgid/job` (or pid tree) associated with the `step_run_id`.
  - Subprocesses run in an isolated workdir under `tmp/workflows/{run_id}/{step_id}`. On cancel/fail, recursively delete the workdir (best-effort), preserving small tail logs.
  - Enforce max output/log size per step; truncate when attaching to events.

- Adapters contract
  - Subprocess-backed step adapters must use the common launcher and return a `SubprocessTask` handle.
  - Adapters must honor the engine’s cancellation by exiting promptly on SIGTERM/CTRL_BREAK and flushing outputs to disk before exit.
  - For tools that support graceful signals (e.g., `ffmpeg -nostdin`), configure flags to improve shutdown behavior.

- Cross-platform notes
  - POSIX: Use `start_new_session=True` and `os.killpg` for reliable group signaling.
  - Windows: Prefer Job Objects when available; otherwise `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` + `psutil` child recursion.

- Telemetry
  - Emit `step_cancelled` events with `elapsed_ms`, `grace_ms`, `forced_kill` (bool), and `orphan_reaped` (bool) where applicable.
  - Record `stdout_tail`/`stderr_tail` (redacted) for debugging.

## API Design

- Create definition: `POST /api/v1/workflows` (body: definition v1)
- Create new version: `POST /api/v1/workflows/{workflow_id}/versions` (body: definition)
- List definitions: `GET /api/v1/workflows?owner_id=...&page=...&limit=...&sort=...`
- Get definition: `GET /api/v1/workflows/{workflow_id}` and `GET /api/v1/workflows/{workflow_id}/versions/{version}`
- Delete definition: `DELETE /api/v1/workflows/{workflow_id}` (soft delete)
- Run (saved): `POST /api/v1/workflows/{workflow_id}/run?mode=async|sync` (body: inputs)
- Run (ad-hoc): `POST /api/v1/workflows/run?mode=async|sync` (body: {definition, inputs}) - stricter rate limits; can be disabled via config.
  - API gateway limits: Enforce `max_definition_bytes` (default 256 KB), `max_steps` (default 50), and `max_step_config_bytes` (default 32 KB per step). Reject with 413/422. Validate unknown step types are disallowed.
- Run status: `GET /api/v1/workflows/runs/{run_id}`
- Run events: `GET /api/v1/workflows/runs/{run_id}/events?since=event_seq` (poll) and `WS /api/v1/workflows/ws?run_id=...` (JWT required)
- Pause/resume/cancel: `POST /api/v1/workflows/runs/{run_id}/{action}`
- Retry failed run: `POST /api/v1/workflows/runs/{run_id}/retry`
- Approve/reject human step: `POST /api/v1/workflows/runs/{run_id}/steps/{step_id}/{approve|reject}` (body: optional edits)
- (v0.2) Reassign/expire human step: `POST /api/v1/workflows/runs/{run_id}/steps/{step_id}/reassign|expire`
- Artifacts: `GET /api/v1/workflows/runs/{run_id}/artifacts`
- Options discovery: `GET /api/v1/workflows/options/chunkers` - returns the chunker registry (names, versions, parameter schemas, defaults) from `Ingestion_Media_Processing`.
  - Versioning: Response includes `name`, `versions` (semver), and parameter schemas per version. Workflow definitions must pin `chunker.name` and `chunker.version` exactly in v0.1.
 - Options discovery: `GET /api/v1/workflows/options/chunkers` - returns the chunker registry (names, versions, parameter schemas, defaults) from `Ingestion_Media_Processing`.
 - Options discovery: Reuse `GET /api/v1/rag/capabilities` to populate builder UI with supported search modes, strategies, and defaults; no extra workflows-specific endpoint needed.

## Schemas (key Pydantic models)

- WorkflowDefinition: `id`, `tenant_id`, `name`, `version`, `inputs`, `steps`, `metadata`, optional `on_completion_webhook`.
- WorkflowRun: `run_id`, `tenant_id`, `workflow_id`, `status`, `status_reason`, `inputs`, `outputs`, `duration_ms`, `tokens_input`, `tokens_output`, `cost_usd`, `definition_version`, `definition_snapshot_json`.
- Step: `id`, `name`, `type`, `config`, `on_success`, `on_failure`, `retry`, `timeout_seconds`.
- HumanReviewPayload: `comment`, `edited_fields`, `decision` (approve|reject).

## WebUI (v0.1)

- Definitions: CRUD list/detail; JSON editor with schema validation and templates.
- Runs: List with filters; run detail with step timeline, logs, metrics (duration/tokens/cost minimal), and event replay.
- Live updates: Subscribe to run events; handle reconnect with backoff; de-duplicate by `event_seq`.
- Review: Human step panel to approve/reject and edit fields; CSRF protection; anti-clickjacking headers; signed WS tokens.
- Debugging: Each step view shows final `inputs_json`, `outputs_json`, and any `error` messages.

## Security & Permissions

- AuthNZ: Respect `single_user` and `multi_user` modes; JWT roles for definitions vs runs.
- Tenant isolation: All tables include `tenant_id`; every query enforces row-level checks and WS run-level authorization.
- Rate limits: Per-user/per-tenant workflow run creation and step-external calls; stricter for ad-hoc runs.
- Secrets: No secrets in logs; redact provider keys; template sandbox for Jinja.
- ACLs: Definitions owned by creator; visibility `private` in v0.1.
- External calls: Enforce HTTPS, egress allowlists, DNS/IP checks blocking RFC1918/link-local ranges, TLS verification, HMAC signing, max bytes, timeouts, and no redirects.
- Prompt/tool safety: `mcp_tool` invocations require per-workflow capability scopes; sensitive tools can require human approval.
- CORS/CSRF: WebUI POSTs protected with CSRF tokens; set CSP and frame-busting headers.

## Secrets Management

- Definitions reference secrets via `{{ secrets.NAME }}`. Values are resolved at runtime from secure env/vault and redacted from logs and DB.

## Error Handling

- Step-level: Capture exception, increment attempt, apply backoff with jitter, mark failed if exhausted.
- Run-level: Mark as failed on terminal error; include context; continue on `on_failure` route if set.
- HTTP responses: Normalize upstream errors into structured codes (`timeout`, `throttle`, `auth`, `bad_request`, `internal`, `upstream_5xx`).
- Logging/Tracing: Loguru with correlation ids (run_id, step_run_id) and OpenTelemetry spans.

### Resuming from Failure

- When a run is `failed`, `POST /api/v1/workflows/runs/{run_id}/retry` re-queues from the last failed step, using the same inputs. If successful, the workflow continues from that point.

## Performance & Limits

- Max steps: Default 50 per workflow (configurable).
- Payload size: 8 MB per step input/output (configurable). Prefer artifacts for large blobs (v0.2).
- Concurrency: Per-tenant and per-workflow concurrency and queue depth with fair scheduling. Defaults: 2 async runs per tenant, 1 per workflow (configurable via `WORKFLOWS_TENANT_CONCURRENCY` and `WORKFLOWS_WORKFLOW_CONCURRENCY`).
- Timeouts: Default 300s per step; 1h per run (configurable). Adapters can override.
- Ingestion: Default `max_download_mb=2048`, `max_duration_sec=14400`, and 1 concurrent source per step in v0.1.

## Dependencies & Integrations

- Reuse modules: `Ingestion_Media_Processing`, `LLM_Calls`, `RAG`, `MCP_unified`, `Audio`, `Chatbooks`.
 - RAG: Integrate with the unified pipeline now (FTS/vector/hybrid, reranking, caching, table processing, citations, sibling inclusion). Parent expansion, grouped hierarchical returns, and hierarchical scoring are planned for v0.2 and will be exposed via the same step type when available.

## RAG Integration (Implementation Notes)

- Builder defaults (WebUI):
  - On builder load, fetch `GET /api/v1/rag/capabilities` to populate supported search modes, strategies, default weights, and limits. Cache per session with a short TTL (e.g., 5 minutes).
  - Fallback: if the endpoint is unavailable, use static defaults embedded in the WebUI (hybrid enabled, `hybrid_alpha=0.7`, `top_k_max=100`, rerank strategies `flashrank|cross_encoder|hybrid`).

- Server-side validation (Workflows engine):
  - Define `WorkflowRAGConfig` (Pydantic) for the `rag_search` step with a strict whitelist that maps 1:1 to the unified RAG API:
    - sources, search_mode, hybrid_alpha, top_k, min_score
    - expand_query, expansion_strategies, spell_check
    - enable_cache, cache_threshold, adaptive_cache
    - enable_table_processing, table_method
    - include_sibling_chunks, sibling_window
    - enable_reranking, reranking_strategy, rerank_top_k
    - enable_citations, citation_style, include_page_numbers
    - enable_generation, generation_model, generation_prompt, max_generation_tokens
    - enable_security_filter, detect_pii, redact_pii, sensitivity_level, content_filter
  - Reject unknown/extra fields (Pydantic `extra=forbid`). Enforce bounds (e.g., `0<=hybrid_alpha<=1`, `1<=top_k<=100`).
  - Normalize enums to the API’s accepted values (e.g., `reranking_strategy in {flashrank,cross_encoder,hybrid,none}`, `citation_style in {apa,mla,chicago,harvard,ieee}`).
  - Harden inputs: length caps for strings (e.g., `generation_model` <= 128 chars), sanitize text fields, and drop null/empty arrays.

- Execution mapping:
  - Translate validated `WorkflowRAGConfig` directly to the unified RAG request object and call the internal pipeline (preferred) or the API endpoint if running out of process.
  - Use `include_sibling_chunks`/`sibling_window` as the only hierarchy-related controls in v0.1; ignore/defer parent-expansion options until v0.2.

- Error handling:
  - On validation error, fail the step with a 422-style error and a precise message listing invalid fields.
  - On pipeline errors (timeout, reranker missing), apply the step’s retry policy; surface normalized error codes in step output.

- Tests:
  - Unit: validation accepts allowed fields and rejects unknown; bounds enforced; enum normalization.
  - Integration: run a workflow with `rag_search` covering fts|vector|hybrid, reranking on/off, citations on/off, sibling inclusion on/off.

- Telemetry:
  - Log a sanitized `rag_config_validated` event per step run (no secrets, no long strings), and include key flags (mode, reranking, citations, sibling inclusion).

## Observability & Ops

- Metrics: Prometheus counters/histograms for `runs_started`, `runs_succeeded`, `runs_failed`, `step_latency_ms{type}`, `retries`, `timeouts`, `cost_usd_total`.
- Event ordering: `workflow_events` are append-only with monotonic `event_seq`. Poll API supports `since=event_seq` for replay.
- Dead letter: Repeatedly failing runs can be moved to a DLQ with tooling to inspect and requeue.
 - Cost/tokens: v0.1 records tokens/cost opportunistically when providers return them (e.g., LLM_Calls, rerankers). Values are informational and not used for billing/enforcement yet.

## Compliance & Data Hygiene

- Retention: Configurable retention for runs, events, and artifacts; GDPR deletion by `owner_id` and tenant; log redaction pipeline.
- Storage: Use existing `Databases/` with new `workflows.db` (or shared Postgres) via `WorkflowsDatabase`.
- Artifacts: Store under `Databases/artifacts/` or external URI; track in `workflow_artifacts`.

## Testing

- Unit: Engine step execution, retries/timeouts, branch evaluation, templating sandbox.
- Integration: End-to-end run of sample workflows (mock external providers).
- API tests: CRUD, run lifecycle, human approval endpoints, event stream.
- Property-based: Step graph validation (no cycles for v0.1).
- Markers: `unit`, `integration`, `external_api` where applicable.
 - Sync recovery: Simulate WS disconnect/reconnect; ensure event replay via `since=event_seq` and UI resubscribe restores state.
 - Cancellation: Verify cooperative cancel and forceful termination of subprocess-backed steps; ensure no orphan processes.
 - Ad-hoc limits: Definition size/step count enforcement at API; reject oversize with 413/422.
 - Chunker registry: Pinning to `name@version` resolves; unknown versions rejected; params validated against schema.

## Rollout Plan

- Stage 1 (MVP): Linear workflows, prompt/rag/mcp_tool/wait_for_human/webhook, async+sync, APIs, minimal UI.
- Stage 2: Branch step, tts/transcribe adapters, artifacts, metrics (tokens/cost), templates.
- Stage 3: Triggers (on media ingest, schedule), foreach/parallel (limited), budgets/quotas.

## Success Metrics

- Adoption: ≥5 real workflows created and run in test environments.
- Reliability: ≥95% successful completion rate for non-external-failing runs.
- Latency: Sync guided step transitions under 500ms (excluding model calls).
- Quality: >80% test coverage for engine and API endpoints.

## Risks & Mitigations

- DSL complexity: Start minimal; validate via templates; strict schema validation.
- Long-running tasks: Timeouts and checkpoints; resumable runs; clear cancellation.
- External failures: Retries with backoff; cooldowns per provider if needed.
- Security of templating: Sandboxed Jinja; no attribute access to dangerous objects.

## Open Questions

- Storage strategy: Separate `workflows.db` vs extend `Media_DB_v2.db`?
- Public definitions: Allow shared templates now or keep private until v0.2?
- Cost tracking: Standardize token/cost reporting across providers for accurate metrics?
- Eventing: SSE vs WebSocket vs both for WebUI live updates?
 - Sources: RSS/Atom feed expansion to URL lists? MediaWiki API vs dump-only?
 - Storage: Allow external object storage (S3/GCS) targets for large downloads in v0.1?
- Naming: Follow existing repository naming (`tldw_Server_API`) for now; standardize later.
 - Chunker registry: Surface parameter schemas with versioning; how to handle upgrades without breaking saved definitions?

## Example Templates (v0.1)

- Doc Review Guided:
  - Steps: `rag_search` → `prompt(draft)` → `wait_for_human(edit/approve)` → `webhook(notify)`.
- Prompt Studio Micro Eval (manual):
  - Steps: `prompt(test case)` → `mcp_tool(score|compare)` → `webhook(report)`.
- URL → Ingest → Summarize:
  - Steps: `media_ingest(urls)` → `prompt(summarize extracted text)` → `wait_for_human(optional)` → `webhook(notify)`.

### Media Ingestion/Download Step (spec)

- Config (selected):
  - sources: Array of objects `{ uri, kind?, media_type? }` where `uri` supports `http(s)://`, `file://` (local), and MediaWiki dump paths; `kind` defaults to `auto` (`url|local|mediawiki`); `media_type` defaults to `auto` (`video|audio|pdf|epub|docx|html|markdown|xml|mediawiki_dump`).
  - download: `{ enabled: true, ydl_format?: string, prefer_best?: true, max_filesize_mb?: 2048, cookies_file?: string, proxy?: string, retries?: 3 }` (safe subset passed to yt-dlp).
  - ffmpeg: `{ start_time?: "00:00:00", duration?: null, audio_bitrate?: "128k", sample_rate?: 16000 }` (applies when relevant).
  - extraction: `{ extract_text: true, ocr?: false, language?: "auto", include_images?: false }`.
  - chunking: Either a preset or a registry-based chunker:
    - Preset: `{ strategy: "token|sentence|semantic|page|markdown|html_dom|regex|none", max_tokens?, overlap? }`
    - Registry: `{ name: "<registered_chunker>", version: "x.y.z", params: { ... } }` where `<registered_chunker>` is any chunker exposed by the registry. Parameters validated against the schema for the pinned version.
    - Hierarchical: `{ strategy: "hierarchical", hierarchical: { levels: [ { strategy?: "token|sentence|semantic|page|markdown|html_dom|regex|none", name?: "<registered_chunker>", version?: "x.y.z", params?: {...} }, ... ], link_parents?: true, embed_level?: "leaf|all" } }`
  - indexing: `{ index_in_rag: true, embedding_model?: string, batch_size?: 64, collection?: string, preserve_hierarchy?: true, embed_level?: "leaf|all", expand_parents_on_retrieval?: true }`.
  - transcribe: `{ enabled?: false, engine?: "faster_whisper|nemo|qwen2audio", language?: "auto", diarize?: false }` (if audio/video; can also be separate step).
  - metadata: `{ title?: string, tags?: [string], source?: string, author?: string }`.
  - dedupe: `{ mode: "by_url|by_hash|none", skip_existing: true }`.
  - limits: `{ allowed_mime_types?: [string], max_download_mb?: 2048, max_duration_sec?: 14400 }`.
  - safety: `{ allowed_domains?: [string], sanitize_html?: true }`.

- Outputs:
  - media_ids: Array of IDs stored in `Media_DB_v2.db` (or equivalent) for the ingested items.
  - text: Concatenated plaintext (optional, when `extraction.extract_text` is true).
  - chunks: Array of chunk descriptors (and/or payload) if chunked; descriptor includes `id`, `level` (if hierarchical), `parent_id` (nullable), `order`, `chunker_name`, `chunker_version`, and `metadata` produced by the chunker.
  - rag_indexed: Boolean indicating whether indexing occurred; collection name.
  - transcripts: Transcript artifact URIs/IDs when `transcribe.enabled`.
  - metadata: Per-source extracted and normalized metadata.

- Behavior:
  - Processes `sources` sequentially in v0.1 (no parallel fan-out yet), aggregates outputs.
  - Respects `dedupe` policy before downloading or re-extracting.
  - On partial failures, records per-source errors and proceeds if `continue_on_error: true` (optional flag), otherwise fails the step.

- Validation & Safety:
  - Enforce `allowed_domains` (if provided) and allowed schemes; reject unknown/unsafe schemes.
  - Enforce size/duration caps; fail early with clear error codes.
  - Sanitize HTML if requested; strip active content.
  - Never execute arbitrary yt-dlp `--exec` or shell hooks; whitelist options only.
  - Chunkers must come from the ingestion chunker registry; unknown names are rejected; `params` validated against the registry schema (no code execution).

- Example config:

```json
{
  "id": "ingest_media",
  "type": "media_ingest",
  "config": {
    "sources": [
      { "uri": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "media_type": "video" },
      { "uri": "file:///docs/report.pdf", "media_type": "pdf" }
    ],
    "download": { "enabled": true, "ydl_format": "bestvideo+bestaudio/best", "max_filesize_mb": 1500 },
    "transcribe": { "enabled": true, "engine": "faster_whisper", "language": "auto" },
    "extraction": { "extract_text": true },
    "chunking": { "name": "markdown_headings", "params": { "min_level": 2, "max_gap_tokens": 1200 } },
    "indexing": { "index_in_rag": true, "collection": "news_daily" },
    "metadata": { "tags": ["news", "briefing"], "source": "workflow" },
    "dedupe": { "mode": "by_url", "skip_existing": true },
    "limits": { "max_download_mb": 1500 },
    "safety": { "allowed_domains": ["youtube.com", "youtu.be"] }
  },
  "on_success": "summarize"
}
```

- Additional example: hierarchical chunking

```json
{
  "id": "ingest_hier",
  "type": "media_ingest",
  "config": {
    "sources": [ { "uri": "file:///docs/handbook.pdf", "media_type": "pdf" } ],
    "extraction": { "extract_text": true },
    "chunking": { "strategy": "hierarchical", "hierarchical": {
      "levels": [
        { "label": "section", "name": "markdown_headings", "params": { "min_level": 2 } },
        { "label": "passage", "strategy": "semantic", "max_tokens": 800, "overlap": 80 }
      ],
      "link_parents": true,
      "embed_level": "leaf"
    }},
    "indexing": { "index_in_rag": true, "preserve_hierarchy": true, "expand_parents_on_retrieval": true }
  },
  "on_success": "summarize"
}
```

### RAG Search Step (spec)

- Config (maps to unified RAG API):
  - query: String or template for the user query.
  - sources: ["media_db", "notes", "characters", "chats"] (default: ["media_db"]).
  - search_mode: "fts" | "vector" | "hybrid" (default: "hybrid").
  - hybrid_alpha: Number in [0,1] that blends FTS vs vector in hybrid (default: 0.7).
  - top_k: Max results (default: 10). min_score: 0.0-1.0 threshold.
  - expand_query: bool; expansion_strategies: ["acronym", "synonym", "domain", "entity"]. spell_check: bool.
  - enable_cache: bool; cache_threshold: float (0-1); adaptive_cache: bool.
  - enable_table_processing: bool; table_method: "markdown" | "html" | "hybrid".
  - Context & hierarchy: include_sibling_chunks: bool; sibling_window: int.
    - enable_parent_expansion, include_parent_document, parent_max_tokens exist in API but are not wired end-to-end in v0.1; sibling inclusion is implemented.
    - enable_enhanced_chunking and chunk_type_filter are exposed in schema; full pipeline wiring is planned for v0.2.
  - Reranking: enable_reranking: bool; reranking_strategy: "flashrank" | "cross_encoder" | "hybrid" | "none"; rerank_top_k: int.
  - Citations: enable_citations: bool; citation_style: "apa" | "mla" | "chicago" | "harvard" | "ieee"; include_page_numbers: bool.
  - Generation: enable_generation: bool; generation_model: string; generation_prompt: string; max_generation_tokens: int.
  - Security: enable_security_filter: bool; detect_pii: bool; redact_pii: bool; sensitivity_level: "public" | "internal" | "confidential" | "restricted"; content_filter: bool.

- Outputs:
  - documents: Array of { id, content, metadata, score } from the unified pipeline.
  - citations: When enabled, `citations` plus `academic_citations` and `chunk_citations` in metadata.
  - timings: Per-stage timings, including `retrieval`, `reranking`, `citation_generation`, and `total`.

- Behavior:
  - Executes FTS/vector/hybrid per `search_mode`; blends FTS/vector with `hybrid_alpha`.
  - Optional reranking using FlashRank/cross-encoder/hybrid; limits to `rerank_top_k`.
  - Optional sibling inclusion around retrieved chunks via `include_sibling_chunks` and `sibling_window`.
  - Optional table processing, caching, security filtering, citations, and answer generation.
  - Parent document expansion and grouped hierarchical returns are deferred to v0.2.

- Example config:

```json
{
  "id": "search_docs",
  "type": "rag_search",
  "config": {
    "query": "{{ inputs.question }}",
    "sources": ["media_db", "notes"],
    "search_mode": "hybrid",
    "hybrid_alpha": 0.6,
    "top_k": 12,
    "enable_reranking": true,
    "reranking_strategy": "flashrank",
    "include_sibling_chunks": true,
    "sibling_window": 1,
    "enable_citations": true,
    "enable_generation": false
  },
  "on_success": "draft"
}
```

## Acceptance Criteria

- Engine: Implemented - linear workflows with retries, timeouts, durable checkpoints, leases/heartbeats, and safe resume; pause/cancel semantics enforced.
- APIs: Implemented - versioned immutable definitions; run lifecycle; retry failed runs; events with `event_seq`; WS with JWT and run-level auth; idempotency key support.
- Media ingest: Workflows support all chunking options exposed by `Ingestion_Media_Processing` via a chunker registry (including hierarchical); pass-through `params` validated against registry; outputs include hierarchy links.
- Chunking registry: Chunker discovery endpoint returns versioned schemas; workflow definitions pin `name` and `version`; engine persists `chunker_version` in outputs.
- Sync UX: Guided sync runs are re-attachable after disconnect via `run_id` and event replay; no progress lost while waiting for human action.
- Cancellation: Implemented - subprocess-backed steps record pid/pgid and are terminated via process-group escalation; non-killable steps honor cancellation flag and timeouts.
- Ad-hoc security: Implemented - size/steps/config limits; endpoint can be disabled via config; stricter rate limits applied.
- RAG: `rag_search` integrates with the unified RAG API: supports FTS/vector/hybrid with `hybrid_alpha`, reranking (flashrank/cross_encoder/hybrid), caching, table processing, citations, and sibling inclusion (`include_sibling_chunks`). Parent expansion/grouped hierarchical returns are targeted for v0.2.
- Security: Webhook/tool SSRF protections, egress allowlists, HMAC signing, and idempotency headers; CSRF and CSP in WebUI.
- WebUI: Pending - API/WS ready; run detail timeline, approvals, and live updates supported server-side.
- Docs: This PRD and quickstart examples added under Docs/Design when implemented.
