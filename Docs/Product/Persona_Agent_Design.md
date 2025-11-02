# Persona Interaction/Collaborator (Agent with Voice & Tools)

Status: Active (MVP scaffold implemented)

Owner: Core (LLM, Audio, MCP, AuthNZ, WebUI)

Target Version: v0.2.x (Stage 1), v0.3.x (Stage 2-3)

## Summary

Introduce a first-class Persona agent (text + optional voice + avatar) that chats naturally, remembers context, and uses server tools (via MCP Unified) to help with ingestion, search, analysis, and exports. Actions are transparent, previewed, and require confirmation for impactful operations.

## Current Status (v0.2.x dev)

- Feature flag: endpoints/WS are gated; disabled state returns empty catalog/404 and WS notice.
  - Config: `[persona] enabled=true` in `tldw_Server_API/Config_Files/config.txt`.
  - Exposed at runtime via `GET /api/v1/config/docs-info` under `capabilities.persona`.
- Endpoints: `GET /catalog`, `POST /session`, `WS /stream` implemented (scaffold).
  - WS loop: plan → confirm → act using MCP tools; naive plan heuristics; per-step confirmations expected from client.
  - RBAC: allow_export/allow_delete gates enforced server-side per step.
- MCP Unified: tool calls use existing unified server with user-scoped execution.
- WebUI: Persona tab (preview) and basic dock wiring; visibility follows capabilities.
- Tests: basic WS plan/confirm smoke test.

## Changelog

- v0.2.x dev
  - Feature flag gating and capability exposure via `/api/v1/config/docs-info`.
  - Implemented persona endpoints (catalog, session) and WS stream with plan → confirm → act loop and RBAC guards.
  - Integrated MCP Unified tool calls; added WebUI tab visibility based on capabilities.
  - Added minimal WS smoke test for plan/confirm flow.
- v0.1.0
  - Initial draft design with goals, architecture, and API outline.

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
  - Res: `[ { id, name, description, voice, avatar_url, capabilities, default_tools } ]`

- `POST /session`
  - Req: `{ persona_id, project_id?, resume_session_id? }`
  - Res: `{ session_id, persona: {...}, scopes: [...] }`

- `WS /stream` (bi-directional)
  - Client → Server messages (JSON):
    - `user_message`: `{ session_id, text }`
    - `audio_chunk`: `{ session_id, audio_format, bytes_base64 }`
    - `confirm_plan`: `{ session_id, plan_id, approved_steps: [idx...] }`
    - `cancel`: `{ session_id, reason? }`
  - Server → Client events (JSON frames; audio in separate binary frames if supported):
    - `assistant_delta`: `{ session_id, text_delta }`
    - `partial_transcript`: `{ session_id, text_delta }`
    - `tool_plan`: `{ session_id, plan_id, steps: [ { idx, tool, args, description } ] }`
    - `tool_call`: `{ session_id, step_idx, tool, args }`
    - `tool_result`: `{ session_id, step_idx, ok, output, error? }`
    - `tts_audio`: `{ session_id, audio_format, chunk_id }` (binary follows)
    - `notice`: `{ session_id, level, message }`

- Optional: `POST /tools/execute` for non-WS flows; prefer WS for streaming.

Schemas live under: `tldw_Server_API/app/api/v1/schemas/persona.py`

Implementation notes:
- WS accepts `token`/`api_key` similar to MCP; resolves single-user id when applicable.
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
