Guardrails Improvements PRD v1

Summary
- Title: Guardrails-improvements-1
- Owner: Chat/Platform
- Status: Draft (v1)
- Target version: v0.1.x

Implementation Status
- [x] Streaming: always emit [DONE] on normal completion
- [x] Admin: effective policy preview and reload endpoint
- [x] Admin: blocklist append/remove with ETag/versioning
- [x] Observability: moderation metrics + audit annotations
- [x] Safety/Perf: regex validation + locks
- [x] UI: list overrides/blocklist + “Test this text”
- [x] Policy: per-pattern actions and replacements
- [x] Optional: categories + local PII rules

Context
- A rule-based moderation/guardrails layer is implemented for chat input/output with global and per-user controls. Blocklist supports regex and literals. Admin endpoints exist to CRUD per-user overrides and replace the blocklist file. Streaming redaction is supported; streaming block yields an SSE error and a graceful [DONE].
- Key files (for reference):
  - tldw_Server_API/app/core/Moderation/moderation_service.py
  - tldw_Server_API/app/api/v1/endpoints/chat.py
  - tldw_Server_API/app/core/Chat/streaming_utils.py
  - tldw_Server_API/app/api/v1/endpoints/moderation.py
  - tldw_Server_API/Config_Files/config.txt ([Moderation] section)

Problem Statement
- Moderation is effective but coarse in several places:
  - Single global redact replacement; no per-pattern actions or categories.
  - No policy inspection/reload endpoint; updates require a process restart or file replacement.
  - Streaming path does not always emit a [DONE] on normal completion for maximum client compatibility.
  - Admin UI can edit a single override and replace the blocklist, but lacks list/append/remove flows and versioning.
  - Observability lacks dedicated moderation metrics and standardized audit fields.
  - Performance and safety for very large blocklists/inputs and risky regex patterns can be improved.

Goals
- Increase policy granularity and debuggability (per-pattern actions, categories, policy preview, reload).
- Improve streaming compatibility and client experience (consistent [DONE], structured SSE errors).
- Improve admin UX for blocklist/overrides management (list, append/remove, optimistic concurrency/versioning).
- Strengthen safety and performance (regex hardening, optional local PII rules, locks and combined matchers).
- Expand observability (metrics, audit annotations) and documentation.

Non-Goals
- Integrating third‑party moderation/AI classifiers.
- Full ML classification of safety/PII beyond lightweight optional regex/heuristics.
- Changing default behavior in a breaking way; all new controls default to off or current behavior.

User Stories
- As an admin, I can view the effective moderation policy for a user to understand why text was blocked/redacted.
- As an admin, I can append or remove a blocklist entry without replacing the entire file and avoid lost updates.
- As a developer, I can reload moderation config without restarting the server.
- As a client developer, I always receive a [DONE] sentinel on streaming completion and a structured SSE error if blocked.
- As a security lead, I can enable optional PII rules and track moderation actions via metrics and audit logs.

Requirements
Must
- Per-pattern actions and optional replacement values in blocklist (block | redact | warn), backward compatible with current format.
- Effective policy preview endpoint and reload endpoint.
- Streaming: always emit [DONE] on normal completion; retain SSE error + [DONE] on transform-triggered blocks.
- Admin endpoints for blocklist append/remove with basic validation and optimistic concurrency (ETag/version).
- Metrics for moderation events (input flagged, output redacted, block counts).

Should
- Pattern categories and severity (e.g., pii, nsfw, abuse) to enable per-category toggles/overrides.
- Optional local PII detectors (email, phone, simple IDs) that can be enabled per-category.
- Regex hardening: validation and max-scan limits; prefer safe engines when available.
- Thread-safety for in-memory policy updates (locks) and combined regex matching for performance.
- Admin UI table to list overrides and entire blocklist with search/filter; simple “Test this text” tool.
- Audit annotations for moderation outcomes.

Could
- File watching for auto-reload of blocklist/overrides (still provide manual reload).
- Backoff/short-circuit when repeated streaming blocks occur per-user in a window.
- Response annotations: x-moderation header (non-stream) and event: moderation frame (stream), behind a flag.

Design Overview
1) Policy Model Enhancements
- Extend blocklist line grammar to optionally include an action and replacement and categories:
  - Literal: "forbidden term" (defaults to current global behavior)
  - Regex: "/pattern/i"
  - With action: "forbidden term -> block" or "/pattern/ -> redact:[MASK]"
- With categories: "forbidden term #pii,company_confidential"
- Resolution order:
  - Per-user overrides toggle enabled/input/output and default actions/redact string.
  - Pattern-specific action/replacement overrides global defaults when a pattern matches. (Implemented)
  - Categories allow enabling/disabling subsets via global or per-user override (e.g., categories_enabled=["pii"]).
- Backward compatibility: lines without directives behave exactly as today. (Implemented)

2) Detection & Safety
- Optional PII rules: lightweight regex for common PII (email, phone, basic ID formats), controlled by policy.
- Regex hardening:
  - On pattern load: validate for dangerous constructs; log/skip failing ones.
  - Per-message scanning budget: cap number of matches and max input length scanned.
  - Prefer re2 when available (optional dependency); fallback to stdlib re.
- Context awareness (optional): lower aggressiveness within fenced code blocks; configurable.
- Attachment notes: for image parts with alt text, run text checks; never decode external URLs.

3) Streaming & SSE
- Always emit "data: [DONE]" at normal end of stream to maximize client compatibility.
- Maintain current behavior when a transform triggers a block: emit SSE error payload and then [DONE].
- Optional: emit "event: error" with error payload while keeping OpenAI-compatible data frames; default off.

Current Implementation Notes
- Extended blocklist grammar supported in loader:
  - literal
  - /regex/
  - literal -> block|warn
  - literal -> redact:REPL
  - /regex/ -> block|warn|redact:REPL
- New PatternRule structure stores compiled regex and optional per-pattern action/replacement.
- evaluate_action(text, policy, phase) used by chat input, streaming, non-streaming output to honor per-pattern actions.
 - Categories: blocklist rules may include a categories suffix (e.g., #pii,confidential). Global/per-user categories_enabled filter gates which rules are active. (Implemented)
 - Built-in PII: optional pii_enabled adds redact rules for common PII patterns using PIIDetector when available; defaults to off. (Implemented)
- Implemented in tldw_Server_API/app/core/Chat/streaming_utils.py
  - Added handler.done_sent flag to avoid duplicate [DONE].
  - safe_stream_generator now yields event: stream_end and then data: [DONE] if not already sent.
  - Orchestrator safety net yields [DONE] only if not already sent.

4) API Changes (Admin)
- GET /api/v1/moderation/policy/effective?user_id=U
  - Returns the effective policy snapshot for U (merged global + per-user).
- POST /api/v1/moderation/reload
  - Reloads moderation config, blocklist, and overrides from disk.
- Blocklist management (versioned):
  - GET /api/v1/moderation/blocklist/managed → { version, items: [{id, line}] } (also sets ETag)
  - POST /api/v1/moderation/blocklist/append { line } (requires If-Match header)
  - DELETE /api/v1/moderation/blocklist/{id} (requires If-Match header)
  - PUT /api/v1/moderation/blocklist (replace) continues to work; returns new version via subsequent GET.
- Responses include ETag/version for optimistic concurrency.

5) Admin UI Enhancements
- Moderation tab improvements:
  - Table of blocklist entries with add/remove and search. (Implemented via managed list with ETag)
  - Render list of per-user overrides; quick load into editor. (Implemented)
  - “Test this text”: show matched rule, action, and sample result (redacted or blocked) for a selected user. (Implemented)

Current Implementation Notes
- New endpoints used by UI:
  - GET /api/v1/moderation/blocklist/managed, POST /moderation/blocklist/append, DELETE /moderation/blocklist/{id}
  - GET /api/v1/moderation/users
  - POST /api/v1/moderation/test
  - GET /api/v1/moderation/settings, PUT /api/v1/moderation/settings (runtime overrides)
- UI locations: tldw_Server_API/WebUI/tabs/admin_content.html under Moderation tab.

6) Observability & Audit
- Metrics (Prometheus/registry):
  - moderation_input_flag_total{user_id, category}
  - moderation_output_redact_total{user_id, category}
  - moderation_output_block_total{user_id, category}
  - moderation_stream_block_total
- Audit: include moderation_action, categories, matched_pattern (hash or id) in audit events where applicable.
- Optional response annotations (flagged off by default):
  - Non-stream: add x-moderation: {action, categories}
  - Stream: emit event: moderation {action, categories}

Current Implementation Notes
- Metrics added to ChatMetricsCollector and wired into chat input/output moderation paths, including streaming transform. Labels include user_id, action, category (default), and streaming where applicable.
- Audit events emitted via UnifiedAuditService with event_type=SECURITY_VIOLATION and metadata {phase, action, pattern, streaming}. Blocks mark result=failure; redactions result=success.
 - Category label favors a specific subtype (e.g., pii_email) over generic 'pii' when available.

7) Performance & Reliability
- Combined matcher: compile a union/alternation for literals and maintain separate compiled regex for complex rules; short-circuit on first match when appropriate. (Planned)
- Thread-safety: protect policy reload and setters with a lock; ensure streaming transforms read a consistent snapshot. (Implemented via RLock)
- Scan budgets: cap max characters scanned per text and max replacements per pattern to avoid pathological costs. (Implemented defaults: max_scan_chars=200000, max_replacements_per_pattern=1000; configurable via [Moderation])
- Regex validation: skip dangerous regexes (nested quantifiers, excessive groups) and length caps; log and continue. (Implemented)
- Optional file watchers to auto-reload; exponential backoff on repeated streaming blocks per-user to limit churn. (Planned)

8) Data Model
- Keep file-backed blocklist as primary for single-user/local setups.
- Add optional DB-backed per-user overrides (AuthNZ DB) with versioning and RBAC; file overrides still supported and merged.
- Add a lightweight moderation_events table (user_id, conversation_id, action, category, pattern_id/hash, ts) for optional retention and dashboards.

9) Security & Privacy
- Never log raw content; log pattern ids/hashes and categories only.
- Strictly validate admin inputs (pattern syntax, action enums, category whitelist).
- Rate-limit moderation admin endpoints; enforce require_admin dependency.

10) Compatibility & Migration
- Existing blocklist and overrides continue to work.
- Extended line grammar is additive; lines without directives keep today’s semantics.
- All new features off by default via [Moderation] and per-user settings.

11) Testing Strategy
- Policy
  - Backward compatibility on simple literal/regex lines.
  - Per-pattern action precedence over global defaults.
  - Category enables/disables and per-user overrides precedence.
- Detection & streaming
  - Multiple user message parts; image+text; tool calls untouched.
  - Very large messages; time-bounded scanning; correctness of redaction.
  - Streaming multi-frame chunks; error emission followed by [DONE]; normal completion emits [DONE].
- Admin/API
  - Append/remove with version conflicts; ETag honored; replace still works.
  - Effective policy endpoint reflects merged state; reload picks up file changes.
- Observability
  - Metrics increment paths; audit events include moderation fields.

12) Rollout Plan
- Phase 1 (server-only):
  - Implement always-[DONE], reload endpoint, metrics, and locks.
  - Add effective policy endpoint.
- Phase 2 (admin UX):
  - Append/remove APIs with versioning and Admin UI table + tester.
- Phase 3 (policy extensions):
  - Pattern actions/replacements, categories, and optional PII rules (default off).
- Feature flags in config.txt ([Moderation]) for categories_enabled, pii_enabled, emit_moderation_headers, sse_event_error.

13) Success Metrics
- P0: 0 client regressions for streaming; “always [DONE]” verified across providers.
- P1: Admins can append/remove blocklist without full file replace; version conflicts handled.
- P1: Moderation metrics present and stable; audit entries enriched.
- P2: Optional PII/category features used in at least one deployment without material perf degradation.

14) Risks & Mitigations
- Risk: Regex ReDoS or slow patterns. Mitigation: validation, budgets, and safe engines.
- Risk: Client dependence on exact SSE shape. Mitigation: configurable emission of event names; default stays OpenAI-compatible data frames.
- Risk: Race conditions on reload/update. Mitigation: locks and snapshot reads for streaming transforms.
- Risk: False positives from PII rules. Mitigation: category toggles, warn-only mode, and per-user overrides.

15) Open Questions
- Should we migrate blocklist from text to a JSON schema for first‑class actions/categories? Proposed: keep text with extended grammar now; revisit JSON later.
- Should categories be hierarchical (e.g., pii.email vs pii)? Start flat; add hierarchy only if demanded.
- Should we emit moderation metadata to clients by default? Default off; admin opt-in.

Appendix A: Extended Blocklist Line Grammar (proposal)
- Literal line (backward compatible):
  - forbidden term
- Regex, case-insensitive:
  - /forbidden\s+term/i
- With action and replacement:
  - forbidden term -> redact:[REDACTED]
  - /secret(\d+)/ -> redact:[MASK]
  - /leak/i -> block
  - /minor issue/ -> warn
- With categories (comma-separated; optional):
  - /ssn[^\d]?(\d{3}[- ]?\d{2}[- ]?\d{4})/ -> redact:[SSN] #pii
  - confidential project #company_confidential
Current Implementation Notes
- Endpoints implemented:
  - GET /api/v1/moderation/policy/effective
  - POST /api/v1/moderation/reload
  - GET /api/v1/moderation/blocklist/managed (sets ETag)
  - POST /api/v1/moderation/blocklist/append (If-Match required)
  - DELETE /api/v1/moderation/blocklist/{id} (If-Match required)
- Version is SHA-256 of normalized lines; responses set/return version for optimistic concurrency.
