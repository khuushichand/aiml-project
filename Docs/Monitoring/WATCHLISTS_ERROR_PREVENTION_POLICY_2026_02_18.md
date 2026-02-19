# Watchlists Error Prevention Policy

## Scope

Applies to `/watchlists` prevention guardrails in Feeds, Monitors, and Groups workflows.

## Validation Rules and Thresholds

1. Scope required (`job_form`):
- Monitor save is blocked when no feeds, groups, or tags are selected.
- User message: `watchlists:jobs.form.scopeRequired`.
- Remediation: select at least one scope target.

2. Schedule minimum interval (`job_form`, `schedule_picker`):
- Minimum allowed cadence is every `5` minutes (`MIN_SCHEDULE_INTERVAL_MINUTES`).
- Guard applies in both monitor save and advanced cron apply flows.
- User message: `watchlists:jobs.form.scheduleTooFrequent` / `watchlists:schedule.tooFrequent`.
- Remediation: increase cron interval to at least the minimum threshold.

3. Email recipient format (`job_form`):
- Monitor save is blocked when email recipients include invalid addresses.
- User message: `watchlists:jobs.form.emailRecipientsInvalidSubmit` plus inline invalid list.
- Remediation: remove or correct invalid recipients.

4. Group hierarchy cycle prevention (`groups_tree`):
- Group edit/reparent blocks assigning self or descendant as parent.
- User message: `watchlists:groups.parentCycleError`.
- Remediation: choose a non-descendant parent group.

5. Dependency warnings before destructive actions (`sources`):
- Single/bulk feed delete surfaces active monitor impact summary before confirm.
- User can still proceed, but warning text makes impact explicit.

## Telemetry Schema

Storage key:
- `tldw:watchlists:preventionTelemetry`

Event type:
- `watchlists_validation_blocked`

Dimensions:
- `surface`: `job_form` | `schedule_picker` | `groups_tree`
- `rule`: `scope_required` | `schedule_too_frequent` | `invalid_email_recipients` | `group_cycle_parent`
- `remediation`: short machine-friendly action label
- optional `count` / `minutes` for contextual numeric detail

Rollup fields:
- `counters` (event totals)
- `blocked_by_rule`
- `blocked_by_surface`
- `recent_events` (capped)

## Operational Notes

- Prevention telemetry is local and best-effort; failures to write telemetry must not block UX flows.
- Guardrail copy should remain localized and mapped to `watchlists` locale keys.
