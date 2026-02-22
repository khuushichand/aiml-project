# Persona Interaction/Collaborator (Agent with Voice & Tools)

Status: Active (MVP scaffold implemented)

Owner: Core (LLM, Audio, MCP, AuthNZ, WebUI)

Target Version: v0.2.x (Stage 1), v0.3.x (Stage 2-3)

https://github.com/VectorSpaceLab/general-agentic-memory


## Summary

Introduce a first-class Persona agent (text + optional voice + avatar) that chats naturally, remembers context, and uses server tools (via MCP Unified) to help with ingestion, search, analysis, and exports. Actions are transparent, previewed, and require confirmation for impactful operations.

## Current Status (v0.2.x dev, verified 2026-02-09)

- Implemented (backend scaffold):
  - Feature-flag plumbing (`PERSONA_ENABLED`, persona RBAC config) and docs-info capability exposure.
  - Persona endpoints scaffolded: `GET /api/v1/persona/catalog`, `POST /api/v1/persona/session`, `WS /api/v1/persona/stream`.
  - Basic WS flow: `user_message -> tool_plan`, `confirm_plan -> tool_call/tool_result`.
  - Basic tests exist for catalog, WS smoke flow, and WS metrics.
- Partially implemented:
  - MCP tool execution integration exists with server-stored plan validation keyed by `plan_id`.
  - RBAC-style export/delete string checks exist in persona WS, but full policy/scoping behavior depends on MCP user identity.
  - WebUI/extension persona surface is wired (`/persona`), capability-gated, and supports basic stream flow (connect/session/message/plan confirm-cancel) with route parity checks, component stream-flow tests, and Playwright route/workflow checks (including a live backend WS workflow test that runs when persona capability is enabled); deep backend tool-execution scenarios remain limited.
- Not yet implemented:
  - Full voice protocol (`audio_chunk`, `partial_transcript`, `tts_audio` binary stream).
  - Persistent session/persona memory integration with personalization store.
  - Per-tool policy scopes and explicit policy objects beyond string-based export/delete checks.
- Important caveat:
  - Persona endpoints now require authentication; anonymous interaction is not allowed.

## Changelog

- v0.2.x dev
  - Added feature flag and capability exposure via `/api/v1/config/docs-info`.
  - Added scaffold persona endpoints (catalog, session) and WS stream with a naive plan → confirm → act loop.
  - Integrated scaffold MCP Unified tool execution path and basic RBAC-style export/delete checks.
  - Added minimal WS smoke and metrics tests for the scaffold flow.
  - Hardened auth contract: persona HTTP endpoints require auth; WS stream rejects unauthenticated clients.
  - Normalized disabled behavior: persona catalog/session return `404` when persona is disabled.
  - Standardized WS tool result payload on `output` (with temporary `result` compatibility alias).
- v0.1.0
  - Initial draft design with goals, architecture, and API outline.

## `tool_result.result` Deprecation Plan (set 2026-02-09)

- Canonical contract now: `tool_result.output`.
- Compatibility window: through `2026-06-30`, server continues emitting both `output` and legacy `result`.
- Client behavior during window:
  - Read `output` first.
  - Fall back to `result` only for older server compatibility.
- Planned removal window: starting `2026-07-01` (or next compatible minor/major release after that date), stop emitting `result` once WebUI/extension compatibility checks are green in CI for output-only payloads.

## Goals

- Provide a persistent chat persona with configurable style, voice, and capabilities.
- Enable tool use via MCP with a visible plan/confirm/act loop.
- Support live voice input/output using existing STT/TTS APIs.
- Integrate session and persona memory with personalization store (opt-in).
- Ensure RBAC and confirmations for any write/delete/export actions.

## Non-Goals (Initial)

- Desktop automation outside the browser (future via MCP OS tools).
- Multi-agent collaboration (future); start with a single persona.
- Rich 3D avatars/visemes (future); begin with static avatar states.

## User Stories

- As a user, I open the Persona dock, speak or type, and get streaming responses.
- As a user, the persona proposes a plan to ingest a URL and summarize; I confirm steps.
- As a user, I see transcripts and tool call results in the chat timeline for auditability.
- As a user, I choose a different persona style/voice per project.

## Architecture Overview

- Persona config stored per persona; session-scoped chat with tool execution over MCP.
- WebSocket stream multiplexes chat text, interim transcripts, tool call previews, and TTS audio.
- Memory integration pulls in top-k user memories (if personalization is enabled) and saves persona-specific notes.

## Key Components

- Persona Catalog & Config
  - Location: `tldw_Server_API/app/core/Persona/`
  - Model: name, description, system_prompt, voice, avatar_url, capabilities, default_tools.

- Session Manager
  - Location: `tldw_Server_API/app/core/Persona/session_manager.py`
  - Tracks `session_id`, user_id, persona_id, last N turns, tool outcomes, and scopes.

- Tool Adapter (MCP)
  - Use existing MCP Unified endpoints under `tldw_Server_API/app/core/MCP_unified/`.
  - Provide a thin wrapper to list tools, propose plans, execute with confirmation, and stream results.

- Voice I/O
  - STT: reuse `/api/v1/audio/stream/transcribe` for live captions.
  - TTS: reuse `/api/v1/audio/speech` to stream audio chunks with timing hints.

## API Design

Base path: `/api/v1/persona`

- `GET /catalog`
  - Auth: required (Bearer token or `X-API-KEY`)
  - Disabled behavior: `404 { "detail": "Persona disabled" }`
  - Res: `[ { id, name, description, voice, avatar_url, capabilities, default_tools } ]`

- `POST /session`
  - Auth: required (Bearer token or `X-API-KEY`)
  - Disabled behavior: `404 { "detail": "Persona disabled" }`
  - Req: `{ persona_id, project_id?, resume_session_id? }`
  - Res: `{ session_id, persona: {...}, scopes: [...] }`

- `GET /sessions`
  - Auth: required
  - Disabled behavior: `404 { "detail": "Persona disabled" }`
  - Query: `persona_id?`, `limit?`
  - Res: `[ { session_id, persona_id, created_at, updated_at, turn_count, pending_plan_count, preferences } ]`

- `GET /sessions/{session_id}`
  - Auth: required
  - Disabled behavior: `404 { "detail": "Persona disabled" }`
  - Query: `limit_turns?`
  - Res: `{ session_id, persona_id, created_at, updated_at, turn_count, pending_plan_count, preferences, turns: [...] }`

- `WS /stream` (bi-directional)
  - Auth: required before interaction (`Authorization: Bearer ...`, `X-API-KEY`, or `token`/`api_key` query params)
  - Missing/invalid auth: connection is closed (`1008` policy violation)
  - Client → Server messages (JSON):
    - `user_message`: `{ session_id, text, use_memory_context?, memory_top_k? }`
    - `audio_chunk`: `{ session_id, audio_format, bytes_base64 }`
    - `confirm_plan`: `{ session_id, plan_id, approved_steps: [idx...] }`
    - `cancel`: `{ session_id, reason? }`
  - Server → Client events (JSON frames; audio in separate binary frames if supported):
    - `assistant_delta`: `{ session_id, text_delta }`
    - `partial_transcript`: `{ session_id, text_delta }`
    - `tool_plan`: `{ session_id, plan_id, steps: [ { idx, tool, args, description, policy } ], memory?: { enabled, requested_top_k, applied_count } }`
    - `tool_call`: `{ session_id, step_idx, tool, args }`
    - `tool_result`: `{ session_id, step_idx, ok, output, error? }`
      - Compatibility: `result` may also be present temporarily as an alias for `output`.
    - `tts_audio`: `{ session_id, audio_format, chunk_id }` (binary follows)
    - `notice`: `{ session_id, level, message }`

- Optional: `POST /tools/execute` for non-WS flows; prefer WS for streaming.

Schemas live under: `tldw_Server_API/app/api/v1/schemas/persona.py`

Implementation notes:
- WS accepts auth via headers and query params, and requires successful auth before stream interaction.
- For compatibility with HTTP auth behavior, single-user/non-JWT bearer values are treated as API keys.
- Tool name → module mapping is minimal; error messages returned for unknown/forbidden tools.
- Client is responsible for rendering plan steps and sending back approvals.

## Tool Use Loop (Plan → Confirm → Act → Review)

1. Persona drafts a short plan (1-3 steps max by default) with tools and inputs.
2. UI shows the plan for user confirmation (per step approvals allowed).
3. On confirmation, server calls MCP tools with scoped tokens; streams results.
4. Persona summarizes outcomes and proposes next steps.

Guardrails:

- Never call write/delete/export tools without explicit confirmation.
- Enforce `max_tool_steps` per session/persona from config.
- Attach `why`/audit metadata to each tool invocation.

## Memory & Personalization Integration

- Session Memory: last N turns + tool outcomes (persisted with `session_id`).
- Persona Memory (per user/persona): saved as semantic memories via personalization store.
- Retrieval: before responding, fetch top-k relevant user memories for grounding if enabled.

## WebUI Additions

- Persona Dock: mic button (push-to-talk), live captions, avatar with speaking/listening states.
- Action Preview: shows tool plan steps with toggles; confirm/cancel buttons.
- Transcript Panel: interleaves messages with tool calls/results; downloadable.
- Persona Selector: choose persona/voice within session.
- Visibility controlled by capability map from `GET /api/v1/config/docs-info` (`capabilities.persona`).

## Configuration

`tldw_Server_API/Config_Files/config.txt`

```
[persona]
enabled = true
default_persona = "Research Assistant"
voice = "default"
stt = "faster_whisper"
max_tool_steps = 3

[persona.rbac]
allow_export = false
allow_delete = false
```

Runtime capability surface:
- `GET /api/v1/config/docs-info` → includes `capabilities` and `supported_features` maps (for backward compatibility).

## Security & Permissions

- AuthNZ: Sessions tied to `user_id`; RBAC governs tool access and scope.
- WS persona interactions require authentication; anonymous sessions are not permitted.
- Confirmations required for destructive actions; audit log entries for all tool calls.
- Rate limiting on WS messages and tool executions; backpressure handling on TTS.

## Testing Strategy

- Unit
  - Session manager state transitions; plan merging/approvals; step caps.
  - Tool adapter request/response normalization.

- Integration
  - WS flow: connect → chat → plan → confirm → execute → stream TTS.
  - Permissions: attempts to call restricted tools are denied/logged.
  - Voice pipeline: STT partials drive interim captions; TTS emits playable chunks.
  - WS smoke tests for plan/confirm path.

- Mocks/Fixtures
  - Mock MCP tools with deterministic outputs.
  - Fake TTS generator for byte chunks; STT stub emitting partials.

## Milestones

- Stage 1 (MVP)
  - Persona catalog + session; WS chat; tool plan/confirm loop (text only).

- Stage 2
  - Voice I/O (STT/TTS) and avatar states; transcript timeline with tool logs.

- Stage 3
  - Multi-persona selection per project; scheduled jobs (e.g., daily brief); per-tool RBAC policies.

## Open Questions

- Default toolset priority for MVP (ingest_url, rag_search, summarize, notes)?
- Policy: any hard “never-do” actions beyond delete/export without confirmation?
- Do we require visemes/lip-sync at v1, or ship later?

## Risks & Mitigations

- Tool misuse → strict confirmations, RBAC scopes, and audit logs.
- Latency in voice mode → stream partials early; bound TTS chunk sizes.
- Context bloat → limit session turns and injected memories; prune aggressively.
