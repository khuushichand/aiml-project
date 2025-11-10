# Persona

## 1. Descriptive of Current Feature Set

- Purpose: Scaffold for an agent-like Persona with catalog, session creation, and a basic WebSocket stream.
- Capabilities:
  - Persona catalog (static placeholder)
  - Session create/resume with basic scope list
  - WebSocket: tool-plan proposal + tool-call delegation to MCP server
- Inputs/Outputs:
  - Input: session requests and WS JSON frames (user messages, plan confirmations)
  - Output: persona info, session IDs, stream events (tool_plan, tool_result, notices)
- Related Endpoints:
  - `tldw_Server_API/app/api/v1/endpoints/persona.py:1` (catalog, session, websocket)
- Related Schemas:
  - `tldw_Server_API/app/api/v1/schemas/persona.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Endpoints guarded by feature flag; WS delegates tool calls to MCP Unified via `get_mcp_server()`
  - Optional user resolution from single-user API key; lightweight session manager in `Persona/session_manager.py`
- Key Classes/Functions:
  - `SessionManager` and `Session` dataclass; persona endpoints (catalog/session/stream)
- Dependencies:
  - Internal: MCP Unified server (`core/MCP_unified`), `feature_flags`, AuthNZ settings
- Data Models & DB:
  - No DB; in-memory sessions
- Configuration:
  - `PERSONA_ENABLED` feature flag; optional RBAC toggles for delete/export (`PERSONA_RBAC_ALLOW_*`)
- Concurrency & Performance:
  - WS loop with heartbeats and basic plan execution
- Error Handling:
  - Graceful close on disabled flag; catch and report tool errors in-frame
- Security:
  - Single-user mode optional API-key recognition for WS; future JWT integration expected

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Persona/session_manager.py`; endpoints in `api/v1/endpoints/persona.py`
- Extension Points:
  - Expand catalog/tooling; add persistence for sessions; richer plan proposal module
- Coding Patterns:
  - Keep stream protocol simple; reuse MCP request/response structure for tool invocations
- Tests:
  - (Scaffold) Add unit/integration tests as flows solidify
- Local Dev Tips:
  - Connect to `/api/v1/persona/stream` from a WS client; send `{ "type": "user_message", "text": "<query>" }`
- Pitfalls & Gotchas:
  - Ensure tools are permitted by RBAC toggles; handle WS disconnects
- Roadmap/TODOs:
  - Real catalog, persona memory, tool routing/policies
