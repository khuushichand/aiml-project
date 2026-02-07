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

### Pipeline Integration

`SupervisedPolicyEngine.build_moderation_policy_overlay()` merges supervised rules into a base `ModerationPolicy` object that is compatible with the existing moderation pipeline. Wiring this into all chat streaming callbacks is tracked as future work (P1).

---

## Use Case B: Self-Monitoring

### Rule Configuration

Self-monitoring rules add awareness features beyond blocking:

- **except_patterns** — false-positive exclusions (e.g., pattern `suicide` with except `prevention`)
- **notification_frequency** — `every_message` | `once_per_conversation` | `once_per_day` | `once_per_session`
- **display_mode** — `banner` | `toast` | `inline` | `silent`
- **escalation** — session-level and rolling-window thresholds with action escalation
- **cooldown_minutes** — prevents impulsive disabling (must wait N minutes before deactivation)
- **bypass_protection** — partner-based override requiring a second user to confirm deactivation
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

Escalated action replaces base action (e.g., `notify` -> `warn` -> `block`).

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
- Action: `notify`, display: `toast`
- Frequency: `once_per_conversation`
- Optional future integration: webhook push to a fitness tracking app

### B2: Crisis/Mental Health
- Pattern: `\b(suicid|self.harm|kill myself)\b` (regex)
- Except: `prevention|hotline|awareness|research`
- Action: `warn`, severity: `critical`
- Crisis resources: enabled
- Escalation: 3 in session -> block, 5 in 7 days -> block
- Cooldown: 1440 minutes (24h), bypass protection on

### B3: Professional Boundaries
- Pattern: client names, case numbers (user-configured regex)
- Action: `warn`, display: `inline`
- Frequency: `every_message`
- Context snippet: `topic_only` (log that alert fired, not the content)

---

## Schema: Pydantic Models

Key models in `guardian_schemas.py`:

- `GuardianRelationshipCreate/Response/List`
- `SupervisedPolicyCreate/Update/Response/List`
- `GovernancePolicyCreate/Response/List`
- `SelfMonitoringRuleCreate/Update/Response/List`
- `SelfMonitoringAlertResponse/List`
- `MarkAlertsReadRequest`
- `CrisisResource/CrisisResourceList`
- `DetailResponse`

---

## Testing

224 tests across 3 test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_guardian_db.py` | 97 | All CRUD for 7 tables, validation, cascade deletion |
| `test_supervised_policy.py` | 64 | Pattern matching, actions, phases, cache, overlay building |
| `test_self_monitoring.py` | 63 | Matching, dedup, escalation, cooldown, crisis resources |

All tests use real SQLite databases (tmp_path fixtures) — no mocks.

---

## Files

| File | Lines | Role |
|------|-------|------|
| `tldw_Server_API/app/core/DB_Management/Guardian_DB.py` | ~1708 | Database layer |
| `tldw_Server_API/app/core/Moderation/supervised_policy.py` | ~280 | Supervised policy engine |
| `tldw_Server_API/app/core/Monitoring/self_monitoring_service.py` | ~496 | Self-monitoring service |
| `tldw_Server_API/app/api/v1/schemas/guardian_schemas.py` | ~343 | Pydantic schemas |
| `tldw_Server_API/app/api/v1/endpoints/guardian_controls.py` | ~476 | Guardian REST API |
| `tldw_Server_API/app/api/v1/endpoints/self_monitoring.py` | ~417 | Self-monitoring REST API |
| `tldw_Server_API/app/api/v1/API_Deps/guardian_deps.py` | ~22 | FastAPI DI |
| `tldw_Server_API/tests/Guardian/test_guardian_db.py` | ~819 | DB tests |
| `tldw_Server_API/tests/Guardian/test_supervised_policy.py` | ~1116 | Policy engine tests |
| `tldw_Server_API/tests/Guardian/test_self_monitoring.py` | ~546 | Service tests |

---

## Future Work (P1/P2)

- **P1**: Chat pipeline integration hooks (call `check_text()` in chat streaming callbacks)
- **P1**: Notification delivery (webhook, email, trusted contact)
- **P1**: In-app notification UI
- **P2**: Age-based rule relaxation schedules
- **P2**: External crisis API integration (988 API when available)
- **P2**: Adaptive frequency (reduce alerts for topics user consistently acknowledges)
- **P2**: Multi-guardian support (divorced parents, institutional settings)
- **P2**: Coercion detection (flag if self-monitoring rules are being set by someone else)
