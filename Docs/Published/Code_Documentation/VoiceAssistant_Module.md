# Voice Assistant Module

## Overview

The Voice Assistant module orchestrates a text-first voice command pipeline:

- Input text (typically STT output) is parsed into an intent.
- The intent is executed via MCP tools, workflows, custom handlers, or LLM chat.
- A concise response is produced for TTS.
- Session context and analytics can be persisted when a DB is provided.

Core code lives under `tldw_Server_API/app/core/VoiceAssistant/` and is exposed via
`tldw_Server_API.app.core.VoiceAssistant`.

## Module Map

```
VoiceAssistant/
├── schemas.py          # Core data models (commands, intents, sessions, results)
├── registry.py         # Command loading + matching (YAML + DB + runtime)
├── intent_parser.py    # Multi-stage intent parsing cascade
├── session.py          # In-memory session lifecycle + cleanup loop
├── router.py           # Pipeline orchestration + action execution
├── workflow_handler.py # Voice → workflows bridge + templates
└── db_helpers.py       # Persistence + analytics helpers
```

## End-to-End Flow (Core Pipeline)

Primary entrypoint: `VoiceCommandRouter.process_command(...)` in
`tldw_Server_API/app/core/VoiceAssistant/router.py`.

High-level stages:

1. Session bootstrap
   - Starts the session cleanup loop.
   - Gets or creates a `VoiceSessionContext`.
2. State + history updates
   - Moves the session to `processing`.
   - Appends the user turn to session history.
3. Intent parsing
   - Calls `IntentParser.parse(text, user_id, context)`.
   - Context includes whether the prior state was `awaiting_confirmation`.
4. Action execution
   - Routes by `ActionType`: MCP tool, workflow, custom handler, or LLM chat.
   - Confirmation-required intents are staged instead of executed immediately.
5. Response + persistence
   - Appends the assistant turn and last action result to the session.
   - Sets the session state:
     - `awaiting_confirmation` if a pending intent exists
     - `idle` on success
     - `error` on failure
   - When a DB is provided:
     - Records a `voice_command_events` analytics row.
     - Persists the session snapshot to `voice_sessions`.

Note: The module is STT/TTS agnostic. STT streaming and TTS audio generation are
handled by the Voice Assistant API endpoints.

## Key Components

### Schemas (`schemas.py`)

Key models:

- `VoiceCommand`: phrases → action mapping with priority and confirmation flags.
- `VoiceIntent` + `ParsedIntent`: parsed intent plus match metadata.
- `VoiceSessionContext` + `VoiceSessionState`: stateful session context.
- `ActionResult`: normalized action execution result.

`VoiceSessionContext.get_context_messages(max_turns=...)` provides a compact
conversation window for LLM calls.

### Command Registry (`registry.py`)

`VoiceCommandRegistry` merges three sources:

- YAML defaults from `tldw_Server_API/Config_Files/voice_commands.yaml`
- User commands from the database via `refresh_user_commands(...)`
- Runtime registrations via `register_command(...)`

Matching behavior:

- Prefix matching against each command phrase.
- Score favors exact matches and longer prefix coverage.
- Results are sorted by `(score, priority)` descending.

### Intent Parser (`intent_parser.py`)

`IntentParser.parse(...)` uses a staged cascade:

1. Confirmation detection when `awaiting_confirmation` is true
2. Keyword/prefix matching via the registry
3. Pattern/entity extraction
4. LLM parse fallback (when enabled)
5. Default fallback to `ActionType.LLM_CHAT`

The parser always returns a `ParsedIntent`. Callers should read
`parsed.intent.action_type` (not `parsed.action_type`).

### Session Manager (`session.py`)

`VoiceSessionManager` is intentionally simple and in-memory:

- Session timeout: 30 minutes of inactivity
- Max sessions per user: 5 (oldest is evicted)
- Background cleanup: runs every 60 seconds

The session manager does not automatically restore state from `voice_sessions`
on restart. Persistence is primarily for analytics, monitoring, and debugging.

### Router + Action Execution (`router.py`)

`VoiceCommandRouter` coordinates parsing, state, and execution.

Built-in custom handlers include:

- `stop`, `cancel`, `help`, `repeat`
- `confirmation` (yes/no resolution)
- `empty_input`
- `workflow_status`, `workflow_cancel`

Action routing:

- `MCP_TOOL`: uses `MCPProtocol._handle_tools_call(...)`
- `WORKFLOW`: delegates to `VoiceWorkflowHandler.execute_workflow(...)`
- `CUSTOM`: dispatches to registered handlers
- `LLM_CHAT`: uses `chat_api_call_async(...)` with a voice-specific system prompt

### Workflow Handler (`workflow_handler.py`)

`VoiceWorkflowHandler` bridges voice intents to the Workflows engine:

- Lazy-initializes the workflows DB + engine
- Supports sync and async execution modes
- Provides voice-friendly workflow templates via `get_voice_workflow_templates()`

Included templates:

- `search_and_summarize`
- `analyze_topic`
- `daily_briefing`

### Persistence + Analytics (`db_helpers.py`)

DB helpers centralize voice-related persistence:

- Voice commands: `save_voice_command`, `get_voice_command`, `delete_voice_command`
- Sessions: `save_voice_session`, `get_voice_session`, `cleanup_old_sessions`
- Analytics: `record_voice_command_event` + aggregate queries

Write operations use `with db.transaction():` to ensure consistent behavior with
the existing DB abstractions and triggers.

## Data Model Notes (ChaChaNotes DB)

Voice assistant tables are created via migrations in
`tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`:

- `voice_commands`: command definitions (soft-delete via `deleted`)
- `voice_sessions`: session snapshots (includes `conversation_id` FK)
- `voice_command_events`: analytics event log

`voice_commands` also has sync-log triggers that write into `sync_log(entity, ...)`
using the current sync schema.

## Extension Patterns

### Add a new default command (system-level)

1. Edit `tldw_Server_API/Config_Files/voice_commands.yaml`
2. Ensure `action_type` and `action_config` match an implemented route
3. Reload the registry (or restart the server)

### Add a user command (DB-level)

- Use the REST endpoint or `save_voice_command(db, VoiceCommand(...))`
- Ensure the registry is refreshed from DB:
  - `registry.refresh_user_commands(db, user_id=..., include_disabled=...)`

### Add a custom action handler

Register a handler at runtime:

```python
from tldw_Server_API.app.core.VoiceAssistant import get_voice_command_router
from tldw_Server_API.app.core.VoiceAssistant.schemas import ActionResult, ActionType


async def handle_ping(intent, session):
    return ActionResult(
        success=True,
        action_type=ActionType.CUSTOM,
        response_text="pong",
        result_data={"echo": intent.raw_text},
    )


router = get_voice_command_router()
router.register_custom_handler("ping", handle_ping)
```

Then create a command with:

- `action_type: custom`
- `action_config: {"action": "ping"}`

## Testing Notes

Relevant tests live under `tldw_Server_API/tests/VoiceAssistant/`.

Fast, targeted commands:

- REST endpoints:
  - `python -m pytest -q tldw_Server_API/tests/VoiceAssistant/test_rest_endpoints.py`
- Core pipeline behavior:
  - `python -m pytest -q tldw_Server_API/tests/VoiceAssistant/test_e2e_pipeline.py`

Important: voice routes are not mounted when `MINIMAL_TEST_APP=1`. For voice
endpoint tests, set `MINIMAL_TEST_APP=0` (and reload `tldw_Server_API.app.main`
if the module is already imported).

