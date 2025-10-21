# Claims Reviewer Workflow PRD

## 1. Background
- The ingestion pipeline extracts claims into `MediaDatabase.Claims`, powers RAG overlays, and exposes rebuild controls via `/api/v1/claims/*`.
- Operators currently lack a systematic review process: all claims are treated as equally authoritative, and corrections must be handled via ad-hoc database edits or re-ingestion.
- Expanding into collaborative research scenarios requires traceable approval states, configurable routing, and feedback loops to improve extraction quality over time.

## 2. Problem Statement
Teams need confidence that surfaced claims have been vetted, yet the platform provides no tooling to triage, approve, or correct them. Without a reviewer workflow:
- Analysts duplicate effort verifying the same claims.
- Product owners cannot track accuracy metrics or assign accountability.
- Extractor quality drifts without structured feedback.

## 3. Goals & Success Criteria
1. Provide an end-to-end reviewer workflow with staging states, assignment, and audit history.
2. Enable admins to triage batches of claims efficiently and requeue problem areas.
3. Capture reviewer corrections to drive extractor improvements and accuracy metrics.
4. Deliver APIs/UI hooks that integrate with existing claims endpoints and background services.

**Success Metrics**
- ≥90% of claims for high-value media reach an approved or rejected state within SLA.
- Reviewers process ≥50 claims/hour using batch tooling.
- Extractor delta report shows measurable reduction in post-review corrections over release cycles.
- Audit coverage: every claim transition has reviewer, timestamp, and notes.

## 4. Out of Scope (v1)
- Full-blown workflow builder or external ticketing integration.
- Automated truth scoring beyond reviewer decisions.
- Multi-step approval chains (single reviewer pass only).
- Support for non-text media annotations (handled elsewhere).

## 5. Personas & Use Cases
- **Claims Reviewer**: Reviews assigned claims, approves/flags them, leaves notes.
  - Needs queue prioritized by relevance or source, quick compare view with evidence.
  - Requires ability to bulk approve straightforward claims.
- **Claims Admin / Research Lead**: Configures assignment rules, monitors throughput.
  - Needs dashboards to see backlog, unsupported ratios, reviewer performance.
- **Product Engineer**: Integrates reviewer state into UI or exports, consumes APIs.
  - Needs stable endpoints, webhooks for state changes.
- **Extractor Owner / ML Engineer**: Monitors feedback loop to tune models.
  - Needs correction data, edit frequency, reason codes.

## 6. Functional Requirements

### 6.1 Staging States & Audit Trail
- Schema additions:
  - `Claims.review_status` (`pending`, `reassigned`, `approved`, `flagged`, `rejected`).
  - `Claims.reviewer_id`, `Claims.reviewed_at`, `Claims.review_notes`.
  - `Claims.review_version` (optimistic locking).
- New table `ClaimsReviewLog` capturing state transitions, reviewer, notes, delta (old/new text).
- API endpoints:
  - `GET /api/v1/claims/review-queue`: paginated pending claims with filters (media, source, extractor, priority).
  - `PATCH /api/v1/claims/{claim_id}/review`: payload `{status, review_version, notes?, corrected_text?, reason_code?}`.
  - `GET /api/v1/claims/{claim_id}/history`: list of review events.
- Business rules:
  - New claims default to `pending`, reviewer fields null.
  - Transition validation: `pending -> {approved|flagged|rejected|reassigned}`; `reassigned` transitions require a target reviewer or group. Flagged or reassigned items can transition back to pending when requeued.
  - Optimistic locking using `review_version` to avoid race conditions.

### 6.2 Batch Review UI & Bulk Actions
- Admin dashboard listing claims grouped by media with filters for review status, unsupported ratio, extraction mode, ingestion source, assigned reviewer.
- Batch operations:
  - `approve`, `flag_for_followup`, `reject`, `reassign`.
  - Ability to add a common note applied to each claim in the batch.
- Quick review panel displaying claim text, original chunk context, evidence, prior reviewer notes.
- Keyboard shortcuts (approve = `A`, flag = `F`, skip = `S`).
- Hook UI actions to the review endpoints; post-success refresh queue metrics.
- Integrate with the existing rebuild worker queue: flagged or reassigned claims enqueue follow-up tasks that the Claims rebuild worker processes for re-extraction or escalation (no new worker required).

### 6.3 Assignment Rules & Notifications
- Configurable rule engine:
  - New table `ClaimsReviewRules` storing predicates (e.g., source domain, media tags, ingestion provider, language) mapped to `reviewer_id` or `review_group`.
  - CRUD endpoints under `/api/v1/claims/review/rules`.
- On claim creation, evaluate rules in priority order; assign `reviewer_id` or `review_group`.
- Unmatched claims fall back to a global queue.
- Notification integration:
  - Emit events via existing notification subsystem (webhooks/Slack/email) when claims assigned to a reviewer or group.
  - Daily digest summarizing outstanding assignments per reviewer.

### 6.4 Feedback Loop & Extractor Insight
- Allow reviewers to optionally edit claim text or supply a corrected version; store delta in `ClaimsReviewLog`.
- Nightly job aggregates corrections:
  - Compute per-extractor metrics (approval rate, edit rate, frequent correction motifs).
  - Surface results via metrics endpoints and dashboards.
- Trigger re-embedding when text changes and update any dependent indexes (Chroma, FTS).
- Provide a `GET /api/v1/claims/review/analytics` endpoint summarizing accuracy trends.
- Optional hook to schedule targeted re-ingestion/rebuild for media with high correction rates.

### 6.5 Authorization & Security
- `reviewer` role with permissions to act on assigned claims.
- `claims_admin` role to manage rules, view any claim, perform bulk actions.
- Ensure reviewer actions are limited to assigned claims unless elevated privileges granted.
- Mask sensitive metadata in UI/API according to tenant policies.
- Record reviewer IP and user agent on every action and persist alongside audit entries.

### 6.6 Integrations
- Extend existing `/api/v1/claims` list endpoints to support `review_status` filters and note fields.
- Update exports (chatbooks, API responses) to include reviewer status when requested.
- Provide webhook payload schema for claim review events.

## 7. Non-Functional Requirements
- **Performance**: Batch operations should update ≤500 claims within 2 seconds; queues must support thousands of pending items.
- **Reliability**: All review actions transactional; audit log persistence guaranteed even on failures.
- **Scalability**: Support multi-tenant routing; rule evaluation must be efficient for hundreds of rules.
- **Usability**: UI optimized for keyboard workflows; include accessibility considerations (screen reader friendly, ARIA labels).
- **Security**: Enforce RBAC, log every review action with IP/user agent, prevent tampering via versioning.

## 8. Data Model Changes
- Update `Claims` table with review columns plus indexes on `review_status`, `reviewer_id`.
- Create `ClaimsReviewLog` table with fields: `id`, `claim_id`, `old_status`, `new_status`, `old_text`, `new_text`, `reviewer_id`, `notes`, `created_at`, `reason_code`, `action_ip`, `action_user_agent`.
- Optional `ClaimsReviewAssignment` table if supporting review groups/round-robin.

## 9. APIs & Endpoints (Draft)
| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v1/claims/review-queue` | GET | Retrieve pending claims (filters: media_id, source, priority, assigned_to, status) | reviewer/claims_admin |
| `/api/v1/claims/{claim_id}/review` | PATCH | Update status, assignment, notes, corrected text (requires `review_version`) | reviewer/claims_admin |
| `/api/v1/claims/{claim_id}/history` | GET | Fetch audit log for a claim | reviewer/claims_admin |
| `/api/v1/claims/review/bulk` | POST | Bulk approve/flag/reassign claims | claims_admin |
| `/api/v1/claims/review/rules` | GET/POST/PATCH/DELETE | Manage assignment rules | claims_admin |
| `/api/v1/claims/review/analytics` | GET | Summary metrics for extractor feedback | claims_admin |

## 10. UX Considerations
- Lightweight Kanban view: columns for `pending`, `flagged`, `reassigned`.
- Modal for editing claim text with diff viewer.
- Display supporting evidence alongside claim (context snippet, source metadata).
- Provide filters for SLAs (time since ingestion vs. review).
- Add tooltips linking to reviewer guidelines documentation.

## 11. Telemetry & Monitoring
- Metrics:
  - `claims_review_queue_size`, `claims_review_processed_total`, `claims_review_flagged_total`.
  - `claims_review_latency_seconds` histogram (ingestion → decision).
  - `claims_extractor_postreview_delta` measuring edit rate by extractor mode.
- Alerts when:
  - Queue size > threshold for >X minutes.
  - Approval rate dips below target per extractor.
  - SLA breached for priority media.

## 12. Dependencies & Risks
- Requires schema migrations impacting `Media_DB_v2` and Postgres variants; backwards compatibility must be maintained.
- Additional roles/permissions must align with AuthNZ strategy; need updates to JWT/RBAC config.
- UI depends on Next.js front-end alignment and design capacity.
- Risk of reviewer overload if assignment rules misconfigured; need admin overrides.
- Feedback loop may introduce additional load on embedding services; plan capacity.

## 13. Rollout Plan
1. **Phase 1**: Schema + core APIs (staging states, review endpoint, audit log, queue fetch). CLI tooling for MVP review without UI.
2. **Phase 2**: Batch UI (admin dashboard, bulk actions), assignment rule management, notifications.
3. **Phase 3**: Feedback analytics, extractor adjustment jobs, webhook integrations.
4. **Phase 4**: Advanced features (review groups, SLA dashboards, watchlist ties).

## 14. Open Questions
- Do we require multi-step approvals (e.g., reviewer + lead)? For v1, assume single reviewer.
- Should corrected claims trigger automatic re-publication to downstream systems?
- How to version assignment rules? Possibly require rule ordering and activation windows.
- Will rejected claims stay in storage or move to archive?

## 15. Appendix
- References:
  - Existing Claims PRD (`Docs/Product/Claims_Module_PRD.md`).
  - Claims endpoints (`tldw_Server_API/app/api/v1/endpoints/claims.py`).
  - Claims rebuild service (`tldw_Server_API/app/services/claims_rebuild_service.py`).
