# Chat `/skills` and `/skill` Slash Commands Design

Date: 2026-02-26
Status: Approved
Owner: Codex + user

## Problem Statement

Add chat slash commands that let users:

- discover invocable skills
- invoke a specific skill directly from chat

The implementation must align with the existing Skills module and existing slash-command pipeline.

## Goals

- Add `/skills` command to list available user-invocable skills.
- Add `/skill <name> [args]` command to execute one skill.
- Keep command discovery unified via `GET /api/v1/chat/commands`.
- Reuse existing Skills services/execution paths.
- Respect RBAC, rate limits, injection modes, and existing command metrics/audit paths.

## Non-Goals

- No frontend-only command execution path.
- No replacement of existing LLM Skill tool-calling behavior.
- No new standalone skills discovery endpoint for slash commands.

## Chosen Approach

Implement both commands inside `command_router` (same pattern as `/time` and `/weather`).

Why:

- Single source of truth for slash command registry and discovery.
- Works across all chat surfaces already consuming `/api/v1/chat/commands`.
- Preserves existing command parsing, rate limiting, truncation, moderation, and audit behavior in chat preprocessing.

## Command Semantics

### `/skills [filter]`

- Lists only skills where:
  - `user_invocable = true`
  - `disable_model_invocation = false`
- Optional `filter` narrows by name/description/argument hint.
- Returns concise, deterministic command output for injection.
- If no matches, returns a friendly "no invocable skills" response.

### `/skill <name> [args]`

- Parses first token as `skill_name`, remaining text as `args`.
- Executes via existing Skills execution logic (inline/fork preserved).
- Uses existing skill name normalization/validation rules.
- Fails with explicit deterministic messages for:
  - missing name
  - non-existent skill
  - non-invocable skill
  - execution error

## Architecture and Integration

### Backend Components

- `tldw_Server_API/app/core/Chat/command_router.py`
  - Register `skills` and `skill` command specs.
  - Add handlers for list + execute flows.
- Existing chat command discovery endpoint (`/api/v1/chat/commands`) remains unchanged structurally.
- Existing chat preprocessing in `tldw_Server_API/app/api/v1/endpoints/chat.py` remains the injection owner.

### Skills Module Reuse

- Reuse `SkillsService` for listing/getting skills.
- Reuse skill execution pipeline (`SkillExecutor` / context integration helpers) for `/skill` command execution.
- Do not duplicate skill parsing/storage logic inside chat module.

### Injection Behavior

Both new commands inherit existing command injection modes:

- `system`
- `preface`
- `replace`

No new mode added.

## Permissions and Security

### RBAC

Add per-command permissions and enforce exactly as existing command router behavior:

- `chat.commands.skills`
- `chat.commands.skill`

### Existing Guardrails Reused

- per-user/global command rate limits
- output truncation (`CHAT_COMMANDS_MAX_CHARS`)
- slash command moderation/audit pipeline in chat endpoint
- request-level auth/scope dependencies already on `/api/v1/chat/commands` and chat completion endpoints

## API/Discovery Contract

`GET /api/v1/chat/commands` includes:

- `skills`
  - `usage`: `/skills [filter]`
  - `args`: `["filter"]`
- `skill`
  - `usage`: `/skill <name> [args]`
  - `args`: `["name", "args"]`

RBAC filtering behavior remains unchanged when command permissions are enforced.

## Error Handling

- Missing `/skill` name -> usage/help response.
- Unknown/non-invocable skill -> explicit deny/not-found response.
- Execution exceptions -> bounded error content + metadata reason.
- `/skills` backend failure -> safe failure content (no stack leakage).

## Testing Strategy

### Unit

`tests/Chat_NEW/unit/test_command_router.py`

- command metadata includes `skills` and `skill`
- `/skills` lists only invocable skills
- `/skills` filtering behavior
- `/skill` success for inline and fork contexts
- `/skill` missing name / not found / non-invocable paths
- RBAC deny paths for new command permissions

### Integration

`tests/Chat_NEW/integration/test_chat_commands_endpoint.py`

- discovery endpoint returns new commands when enabled
- RBAC filtering excludes commands when permissions denied

`tests/Chat_NEW` slash-injection integration coverage

- `/skill` behaves consistently across `system` / `preface` / `replace`

### Regression

- Existing Skills API tests remain green (`tests/Skills/...`).
- Existing `/time` and `/weather` command behavior remains unchanged.

## Rollout Notes

- Feature remains behind existing `CHAT_COMMANDS_ENABLED` flag.
- No frontend migration required for basic discoverability/autocomplete.
- Workspace chat surface may optionally migrate to shared slash-command hook later for consistency, but this is not required for backend command support.

## Risks and Mitigations

- Risk: command-router dependency on Skills internals grows.
  - Mitigation: keep integration through existing service/executor APIs.
- Risk: hidden/background skills accidentally exposed.
  - Mitigation: enforce `user_invocable=true` and `disable_model_invocation=false` in handler logic and tests.
- Risk: large skill output floods prompt.
  - Mitigation: existing command output truncation remains enforced.
