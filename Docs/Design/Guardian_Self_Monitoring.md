# Guardian Controls & Self-Monitoring

Design document for content moderation, parental controls, and self-monitoring features.

## Overview

Two interconnected features sharing a common database layer (`GuardianDB`):

1. **Guardian Controls** (Use Case A) — A guardian user configures content blocking/notification rules on a dependent's account
2. **Self-Monitoring** (Use Case B) — A user configures awareness notifications on their own account

Both features layer on top of the existing `ModerationService` and `TopicMonitoringService` without modifying them.

---

## Architecture

### Database: `Guardian_DB.py`

Single SQLite database per user with 7 tables:

| Table | Purpose |
|-------|---------|
| `guardian_relationships` | Guardian-dependent account links with lifecycle states |
| `supervised_policies` | Guardian-imposed content rules (block/redact/warn/notify) |
| `supervision_audit_log` | Audit trail of guardian actions |
| `governance_policies` | Named policy groups that bundle multiple rules with scheduling |
| `self_monitoring_rules` | User-defined awareness rules with escalation and cooldown |
| `self_monitoring_alerts` | Recorded alert instances with dedup tracking |
| `escalation_state` | Per-rule session/window escalation counters |

Pattern: RLock + WAL mode + FK ON (same as `Personalization_DB.py`).

### Service Layer

```
GuardianDB (storage)
    |
    +-- SupervisedPolicyEngine (supervised_policy.py)
    |       - Compiles guardian policies per-dependent (60s cache TTL)
    |       - check_text() evaluates all active policies
    |       - build_moderation_policy_overlay() for pipeline integration
    |
    +-- SelfMonitoringService (self_monitoring_service.py)
            - Compiles user rules with include/exclude patterns (30s cache TTL)
            - check_text() with phase filtering, min_context_length, dedup, escalation
            - Cooldown protection against impulsive rule disabling
            - Crisis resource integration (988 Lifeline, Crisis Text Line, SAMHSA, IASP)
```

### Governance Policy Features

Governance policies are named groups that bundle supervised policies and self-monitoring rules with schedule, scope, and transparency settings.

- **Schedule Filtering** — Each governance policy may define `schedule_start` and `schedule_end` (HH:MM), `schedule_days` (comma-separated: `mon,tue,wed,thu,fri,sat,sun`), and `schedule_timezone` (IANA identifier, default UTC). Overnight ranges are supported (e.g., 22:00–06:00 spans midnight). On parse errors the schedule fails open (policy remains active).
- **Chat-Type Scoping** — The `scope_chat_types` field accepts `"all"` (default) or a comma-separated list of chat types (e.g., `"regular,character,rag"`). Policies only evaluate when the current `chat_type` matches the scope.
- **Transparent Mode** — The `transparent` flag controls whether block messages reveal the policy. When true, blocked responses include the governance policy name and category, e.g., `[School Policy] Category: entertainment — ...`.
- **Implementation** — `governance_utils.py` provides two pure functions: `is_schedule_active()` and `chat_type_matches()`. These have no database dependencies and are used by both `SupervisedPolicyEngine` and `SelfMonitoringService` to filter policies at evaluation time.

### API Layer

| Prefix | Module | Routes |
|--------|--------|--------|
| `/api/v1/guardian` | `guardian_controls.py` | Relationships CRUD, policies CRUD, audit log |
| `/api/v1/self-monitoring` | `self_monitoring.py` | Rules CRUD, alerts, governance policies, crisis resources |

---

## Use Case A: Guardian Controls

### Relationship Lifecycle

```
pending  -->  active  -->  suspended  -->  active  -->  dissolved
  |                            ^                          ^
  +--- (accept by dependent)   |                          |
                               +-- (suspend/reactivate) --+
                               +-- (dissolve) ------------+
```

- Guardian creates a link (`pending`), dependent accepts (`active`)
- Either party can dissolve; guardian can suspend/reactivate
- Supervised policies only enforce when relationship is `active`

### Policy Configuration

Each supervised policy specifies:
- **patterns** — literal strings or regex (compiled per `pattern_type`)
- **action** — `block` | `redact` | `warn` | `notify` (priority ordering)
- **phase** — `input` | `output` | `both`
- **category** — grouping label (e.g., `explicit_content`, `weapons`)
- **severity** — `info` | `warning` | `critical`
- **notify_context** — `topic_only` | `snippet` | `full_message` (privacy control)
- **governance_policy_id** — optional link to a `GovernancePolicy` that controls schedule, chat-type scope, and transparent mode for this supervised policy

### Pipeline Integration

`SupervisedPolicyEngine.build_moderation_policy_overlay()` merges supervised rules into a base `ModerationPolicy` object that is compatible with the existing moderation pipeline. Guardian and self-monitoring checks are wired into chat input moderation (`moderate_input_messages` and the chat endpoint integration); expanding this coverage to additional entry points is tracked as follow-up work.

After the overlay is built in `moderate_input_messages()`, the engine performs a direct `check_text()` evaluation and calls `dispatch_guardian_notification()` (in `supervised_policy.py`) when `notify_guardian=True` on the matched policy. This routes alerts through `NotificationService.notify_or_batch()` using the same JSONL sink and optional webhook/email pipeline as topic monitoring alerts.

The `chat_type` parameter (e.g., `"regular"`, `"character"`, `"rag"`) is now passed through the chat pipeline to both the supervised policy overlay and self-monitoring evaluation, enabling governance policy chat-type scoping at both layers.

---

## Use Case B: Self-Monitoring

### Rule Configuration

Self-monitoring rules add awareness features beyond blocking:

- **except_patterns** — false-positive exclusions (e.g., pattern `suicide` with except `prevention`)
- **notification_frequency** — `every_message` | `once_per_conversation` | `once_per_day` | `once_per_session`
- **display_mode** — `inline_banner` | `sidebar_note` | `post_session_summary` | `silent_log`
- **escalation** — session-level and rolling-window thresholds with action escalation
- **cooldown_minutes** — prevents impulsive disabling (must wait N minutes before deactivation)
- **bypass_protection** — controls how a rule can be deactivated, with four modes:
  - `none` — disable immediately with no restrictions
  - `cooldown` — must wait `cooldown_minutes` after rule creation before deactivation is allowed
  - `confirmation` — generates a one-time token; user must call `POST /rules/{id}/confirm-deactivation` with the token to complete deactivation
  - `partner_approval` — generates a one-time token; the designated `bypass_partner_user_id` must call `POST /rules/{id}/approve-deactivation` with the token to authorize deactivation
- **crisis_resources_enabled** — shows crisis helpline information when triggered

### Dedup Logic

Controlled by `notification_frequency`:
- `every_message` — always fires
- `once_per_conversation` — one alert per rule per conversation_id
- `once_per_session` — one alert per rule per session_id
- `once_per_day` — one alert per rule per 24h window

Implemented via `has_recent_alert()` in GuardianDB.

### Escalation System

Two independent thresholds per rule:
1. **Session threshold** — if alerts in current session exceed N, escalate action
2. **Window threshold** — if alerts in rolling N-day window exceed M, escalate action

Escalated action replaces base action (e.g., `notify` -> `redact` -> `block`).

### Crisis Resources

Built-in resources (not external API calls):
- 988 Suicide & Crisis Lifeline
- Crisis Text Line (text HOME to 741741)
- SAMHSA National Helpline
- International Association for Suicide Prevention

Displayed with disclaimer: *"tldw is not a mental health service..."*

---

## Scenarios

### B1: Fitness Awareness
- Pattern: `workout|exercise|diet|fitness|calories`
- Action: `notify`, display: `inline_banner`
- Frequency: `once_per_conversation`
- Optional future integration: webhook push to a fitness tracking app

### B2: Crisis/Mental Health
- Pattern: `\b(suicid|self.harm|kill myself)\b` (regex)
- Except: `prevention|hotline|awareness|research`
- Action: `notify` (with escalation to `block`), severity: `critical`
- Crisis resources: enabled
- Escalation: 3 in session -> block, 5 in 7 days -> block
- Cooldown: 1440 minutes (24h), bypass protection on

### B3: Professional Boundaries
- Pattern: client names, case numbers (user-configured regex)
- Action: `notify`, display: `inline_banner`
- Frequency: `every_message`
- For low-interruption logging, use `display_mode = silent_log` to avoid inline UI while still recording alerts

---

## Schema: Pydantic Models

Key models in `guardian_schemas.py`:

- `GuardianRelationshipCreate/Response/List`
- `SupervisedPolicyCreate/Update/Response/List`
- `GovernancePolicyCreate/Response/List`
- `SelfMonitoringRuleCreate/Update/Response/List`
- `SelfMonitoringAlertResponse/List`
- `MarkAlertsReadRequest`
- `DeactivationConfirmRequest` — token-based confirmation for `confirmation` bypass mode
- `DeactivationApproveRequest` — token-based partner approval for `partner_approval` bypass mode
- `CrisisResource/CrisisResourceList`
- `DetailResponse`

---

## Testing

Coverage is concentrated in four dedicated test modules:

| File | Focus |
|------|-------|
| `test_guardian_db.py` | All CRUD for 7 tables, validation, cascade deletion |
| `test_supervised_policy.py` | Pattern matching, actions, phases, cache, overlay building |
| `test_self_monitoring.py` | Matching, dedup, escalation, cooldown, crisis resources |
| `test_chat_integration.py` | `moderate_input_messages` integration with supervised and self-monitoring services |

Core Guardian DB/service tests use real SQLite databases (tmp_path fixtures). The chat integration module also uses targeted fakes/mocks for moderation dependencies.

To check the current collected test count for these modules:

```bash
python3 -m pytest --collect-only -q \
  tldw_Server_API/tests/Guardian/test_chat_integration.py \
  tldw_Server_API/tests/Guardian/test_guardian_db.py \
  tldw_Server_API/tests/Guardian/test_supervised_policy.py \
  tldw_Server_API/tests/Guardian/test_self_monitoring.py
```

---

## Files

| File | Role |
|------|------|
| `tldw_Server_API/app/core/DB_Management/Guardian_DB.py` | Database layer |
| `tldw_Server_API/app/core/Moderation/supervised_policy.py` | Supervised policy engine |
| `tldw_Server_API/app/core/Moderation/governance_utils.py` | Schedule/chat-type utility functions |
| `tldw_Server_API/app/core/Monitoring/self_monitoring_service.py` | Self-monitoring service |
| `tldw_Server_API/app/api/v1/schemas/guardian_schemas.py` | Pydantic schemas |
| `tldw_Server_API/app/api/v1/endpoints/guardian_controls.py` | Guardian REST API |
| `tldw_Server_API/app/api/v1/endpoints/self_monitoring.py` | Self-monitoring REST API |
| `tldw_Server_API/app/api/v1/API_Deps/guardian_deps.py` | FastAPI DI |
| `tldw_Server_API/tests/Guardian/test_guardian_db.py` | DB tests |
| `tldw_Server_API/tests/Guardian/test_supervised_policy.py` | Policy engine tests |
| `tldw_Server_API/tests/Guardian/test_self_monitoring.py` | Service tests |
| `tldw_Server_API/tests/Guardian/test_chat_integration.py` | Chat moderation integration tests |
| `tldw_Server_API/tests/Guardian/test_governance_utils.py` | Governance utils tests |

---

## Future Work (P1/P2)

- **P1**: Expand guardian/self-monitoring enforcement to additional non-chat entry points
- **P1**: In-app notification UI
- **P2**: Age-based rule relaxation schedules
- **P2**: External crisis API integration (988 API when available)
- **P2**: Adaptive frequency (reduce alerts for topics user consistently acknowledges)
- **P2**: Multi-guardian support (divorced parents, institutional settings)
- **P2**: Coercion detection (flag if self-monitoring rules are being set by someone else)
