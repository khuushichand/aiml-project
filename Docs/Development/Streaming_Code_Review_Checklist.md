# Code Review — Streaming

Short, high-signal items for PR reviewers touching SSE/WS streaming code.

- Prefer structured sends using `SSEStream.send_json` / `SSEStream.send_event` and `WebSocketStream.send_json`.
- Raw SSE lines via `SSEStream.send_raw_sse_line` are allowed only for legacy provider pass-through during migration; add a brief code comment (e.g., "legacy pass-through; to be removed after rollout").
- Do not wrap domain WS payloads in event frames for MCP/Audio — keep JSON‑RPC (MCP) and audio partials as-is. Use standardized lifecycle only: `ping`, `error`, `done`.
- Labels must be low-cardinality (e.g., `component`, `endpoint`) — never user/session IDs.
- Close codes: map errors per PRD (e.g., `quota_exceeded` → frame + close `1008`; idle timeout → `1001`).

References
- PRD: `Docs/Design/Stream_Abstraction_PRD.md`
- Streams API: `tldw_Server_API/app/core/Streaming/streams.py`
