# Email Release Checklist and Rollback Plan

Audience: Backend + SRE/Ops + Product  
Status: Draft for stakeholder sign-off

Related:
- PRD: `Docs/Product/Email_Ingestion_Search_PRD.md`
- M3 gate evidence: `Docs/Operations/Email_M3_Gate_Validation_Checklist.md`
- Sync runbook: `Docs/Operations/Email_Sync_Operations_Runbook.md`
- Monitoring rules: `Docs/Operations/monitoring/prometheus_alerts_tldw.yml`
- Env vars: `Docs/Operations/Env_Vars.md`

## Scope
Production rollout checklist for normalized email ingestion/search and `/media/search` delegation, with explicit rollback criteria and execution order.

## Rollout Controls
Primary flags:
- `EMAIL_NATIVE_PERSIST_ENABLED`
- `EMAIL_OPERATOR_SEARCH_ENABLED`
- `EMAIL_MEDIA_SEARCH_DELEGATION_MODE` (`opt_in` or `auto_email`)
- `EMAIL_GMAIL_CONNECTOR_ENABLED`
- `CONNECTORS_WORKER_ENABLED`

Guidance:
- Keep `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=opt_in` until canary sync/search health is stable.
- Promote to `auto_email` only after canary and limited rollout gates pass.

## Preflight Checklist
- [ ] M3 gate evidence approved.
- [ ] M4 documentation set published (user guide, architecture, sync runbook, release plan).
- [ ] Alerting wired for:
  - `TLDWEmailSyncFailureRateHigh`
  - `TLDWEmailSyncLagP95High`
- [ ] Connectors worker deployment confirmed (in-process or sidecar).
- [ ] Jobs admin access validated for on-call responders.

## Rollout Sequence

### Phase 0: Staging Validation
- [ ] Enable `EMAIL_GMAIL_CONNECTOR_ENABLED=true` in staging.
- [ ] Run sync dry-run from `Docs/Operations/Email_Sync_Operations_Runbook.md`.
- [ ] Validate no API regressions for:
  - `GET /api/v1/email/search`
  - `GET /api/v1/email/messages/{id}`
  - `GET /api/v1/media/search` in legacy/default mode.

### Phase 1: Production Canary
- [ ] Enable Gmail source sync (`EMAIL_GMAIL_CONNECTOR_ENABLED=true`) for canary environment/slice.
- [ ] Keep delegation in `opt_in`.
- [ ] Trigger manual canary sync and verify:
  - Source reaches `sync.state=healthy`.
  - No persistent `retrying`/`failed` on canary source.
- [ ] Observe 60+ minutes:
  - Failure rate under warning threshold.
  - Lag p95 under warning threshold.

### Phase 2: Limited Rollout
- [ ] Expand canary coverage (more sources/tenants).
- [ ] Keep `opt_in` unless operator-search behavior is explicitly being promoted.
- [ ] Verify parity and latency sample checks remain green.

### Phase 3: Delegation Promotion
- [ ] Set `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=auto_email`.
- [ ] Run targeted regression for `/api/v1/media/search` email-only scope.
- [ ] Monitor for 24h with no sustained alerts.

### Phase 4: Broad Rollout
- [ ] Announce rollout completion.
- [ ] Record final config snapshot and sign-offs.

## Rollback Triggers
Rollback immediately when any high-risk condition persists beyond initial mitigation window:
- `TLDWEmailSyncFailureRateHigh` firing for >= 20 minutes.
- `TLDWEmailSyncLagP95High` firing for >= 20 minutes.
- Repeated `cursor_invalid_full_backfill_required` across multiple active sources.
- Email endpoint or `/media/search` regression causing user-visible failures.
- Sustained connectors job backlog growth with no recovery trend.

## Rollback Plan (Ordered)
1. Disable delegation first:
  - Set `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=opt_in`.
2. If user impact persists, disable operator search surface:
  - Set `EMAIL_OPERATOR_SEARCH_ENABLED=false`.
3. Stop new Gmail sync triggers:
  - Set `EMAIL_GMAIL_CONNECTOR_ENABLED=false`.
4. Pause connectors worker ingestion:
  - Set `CONNECTORS_WORKER_ENABLED=false`.
5. Restart API/workers and verify config application.
6. Stabilize queue state:
  - Inspect `GET /api/v1/jobs/list?domain=connectors`.
  - Retry/cancel only after root cause is understood.

## Post-Rollback Verification
- [ ] `/api/v1/media/search` legacy path healthy for baseline traffic.
- [ ] Email sync endpoints correctly disabled (404 expected) when Gmail connector flag is off.
- [ ] Connectors queue no longer accumulates new failing jobs.
- [ ] Alerts return to baseline.
- [ ] Incident timeline and corrective actions documented.

## Sign-off Record
- [ ] Backend sign-off (owner + date).
- [ ] SRE/Ops sign-off (owner + date).
- [ ] Product sign-off (owner + date).

M4 gate closes only when all sign-offs are complete and target rollout scope is enabled.
