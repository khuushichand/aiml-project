# Moderation

## 1. Descriptive of Current Feature Set

- Purpose: Centralized, configurable moderation/guardrails for chat inputs/outputs with support for redaction or blocking.
- Capabilities:
  - Global policy from config.txt ([Moderation]) with per-user runtime overrides
  - Blocklist with literals/regex, per-rule action (block|warn|redact:replacement)
  - Categories filter and optional built-in PII patterns
  - Streaming-friendly redaction and graceful block handling
- Inputs/Outputs:
  - Input: text (request/response frames)
  - Output: moderated text or block/warn signals
- Related Usage:
  - Chat endpoints depend on moderation service for pre/post filtering

## 2. Technical Details of Features

- Architecture & Data Flow:
  - `ModerationService` loads config and overrides, compiles `PatternRule`s, evaluates input/output with per-rule actions
- Key Classes/Functions:
  - `ModerationService`, `ModerationPolicy`, `PatternRule` in `moderation_service.py:1`
- Dependencies:
  - Internal: `core.config` loader; loguru
- Data Models & DB:
  - No DB; runtime overrides JSON file optional
- Configuration:
  - `[Moderation]` in config.txt; env overrides (e.g., `MODERATION_MAX_SCAN_CHARS`, `MODERATION_PII_ENABLED`)
- Concurrency & Performance:
  - Scan char limits and max replacements per pattern; optional debounce for blocklist writes
- Error Handling:
  - Fails safely, defaulting to heuristics; retains streaming behavior on errors
- Security:
  - PII rulepack (optional); user override path anchored to project root

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Moderation/moderation_service.py`
  - `Moderation/governance_utils.py` — pure utility functions for governance policy schedule/chat-type filtering; used by `supervised_policy.py` and `self_monitoring_service.py`
- Extension Points:
  - Additional rule sources (e.g., remote policy loaders); category taxonomy
  - Governance policy scheduling and chat-type scoping via `GovernancePolicy` objects linked to supervised policies and self-monitoring rules
- Coding Patterns:
  - Keep scanning O(N); guard regex with clear limits
- Tests:
  - `tldw_Server_API/tests/unit/test_moderation_blocklist_parse.py:1`
  - `tldw_Server_API/tests/unit/test_moderation_check_text_snippet.py:1`
  - `tldw_Server_API/tests/unit/test_moderation_redact_categories.py:1`
  - `tldw_Server_API/tests/Chat_NEW/integration/test_moderation.py:1`
  - `tldw_Server_API/tests/Chat_NEW/integration/test_moderation_categories.py:1`
- Local Dev Tips:
  - Start with warn-only to validate patterns; add categories incrementally
- Pitfalls & Gotchas:
  - Over-greedy regex, catastrophic backtracking; ensure replacement counts bounded
- Roadmap/TODOs:
  - Pluggable remote policy providers; metrics hooks per action
