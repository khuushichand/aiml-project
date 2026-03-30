# Deferred Backend-Dependent Items — Implementation Plan

**Date:** 2026-03-27
**Context:** These 4 items from the admin-ui production readiness plan require backend API changes before the frontend can surface the data. Listed in recommended implementation order.

---

## Item 1: Audit-to-Logs Cross-Referencing (REVIEW.md 5.11)

**Complexity: SMALL — Backend infrastructure already exists**

### Current State
The backend audit service already:
- Tracks `request_id` (auto-generated UUID) and `correlation_id` on every audit event
- Has indexed DB columns: `context_request_id`, `context_correlation_id`
- Supports filtering: `GET /api/v1/audit/export?request_id=<uuid>`

### Backend Work
**Option A (minimal):** No backend changes needed. The admin-ui just needs to link audit entries to the existing filtered export endpoint.

**Option B (convenience wrapper):** Add `GET /api/v1/admin/requests/{request_id}/audit-trail` that:
- Wraps the existing audit export filter
- Returns `{ request_id, audit_events[], related_sessions[], summary }`

**Recommendation:** Option A — just build the frontend link.

### Frontend Work
- In `admin-ui/app/audit/page.tsx`: Add a "View related logs" action button on each audit entry row
- On click, navigate to `/logs?requestId={entry.request_id}` with the request_id pre-filled as a filter
- In `admin-ui/app/logs/page.tsx`: Read `requestId` from URL params and apply as default filter

### Files
- **Backend:** None required (Option A)
- **Frontend:** `admin-ui/app/audit/page.tsx`, `admin-ui/app/logs/page.tsx`

### Estimated Effort: 2-3 hours (frontend only with Option A)

---

## Item 2: Incident SLA Tracking (REVIEW.md 5.7)

**Complexity: MEDIUM — One new field + computed metrics**

### Current State
Incidents have `created_at`, `updated_at`, `resolved_at`, and a `timeline` of events. Missing: `acknowledged_at` field needed for MTTA calculation. MTTR is computable from existing fields.

### Backend Work

**Step 1: Schema change**
- **File:** `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Add `acknowledged_at: datetime | None = None` to `IncidentItem` (line ~1160)
- Add `acknowledged_at: datetime | None = None` to `IncidentUpdateRequest`

**Step 2: Persistence**
- **File:** `tldw_Server_API/app/services/admin_system_ops_service.py`
- Update incident create/update to persist `acknowledged_at`
- Auto-set `acknowledged_at` when status transitions from `reported` → `investigating` (first acknowledgment)

**Step 3: SLA metrics endpoint**
- **File:** `tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py`
- Add `GET /api/v1/admin/incidents/metrics/sla` returning:
  ```json
  {
    "total_incidents": 42,
    "resolved_count": 38,
    "avg_mtta_minutes": 12.5,
    "avg_mttr_minutes": 185.3,
    "p95_mttr_minutes": 480.0,
    "sla_compliance_pct": 91.2
  }
  ```
- Compute MTTA = `acknowledged_at - created_at`, MTTR = `resolved_at - created_at`
- Include per-incident `mtta_minutes` and `mttr_minutes` in list response

**Step 4: Tests**
- Update `tldw_Server_API/tests/` incident tests for new field
- Add SLA metrics endpoint tests

### Frontend Work
- Add MTTA/MTTR columns to incident list in `admin-ui/app/incidents/page.tsx`
- Add SLA summary cards at top of page (avg MTTA, avg MTTR, compliance %)
- Color-code SLA breaches (red for incidents exceeding target)

### Files
- **Backend:** `admin_schemas.py`, `admin_system_ops_service.py`, `admin_ops.py`
- **Frontend:** `admin-ui/app/incidents/page.tsx`
- **Tests:** Backend incident tests + frontend incident page tests

### Estimated Effort: 1-2 days

---

## Item 3: ACP Agent Runtime Metrics (REVIEW.md 4.4 — Critical)

**Complexity: MEDIUM — Aggregation query over existing data**

### Current State
ACP sessions store per-session data: `agent_type`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `message_count`, `status`. Individual sessions can be listed and filtered by `agent_type`, but there's no aggregation endpoint to get totals per agent.

### Backend Work

**Step 1: Aggregation endpoint**
- **File:** `tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py`
- Add `GET /api/v1/admin/acp/agents/metrics` returning:
  ```json
  [
    {
      "agent_type": "research_assistant",
      "session_count": 156,
      "active_sessions": 3,
      "total_prompt_tokens": 2450000,
      "total_completion_tokens": 890000,
      "total_messages": 4200,
      "error_count": 12,
      "last_used_at": "2026-03-27T15:30:00Z"
    }
  ]
  ```

**Step 2: Database query**
- **File:** `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Add `get_agent_metrics()` method with SQL `GROUP BY agent_type`:
  ```sql
  SELECT agent_type,
         COUNT(*) as session_count,
         SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_sessions,
         SUM(prompt_tokens) as total_prompt_tokens,
         SUM(completion_tokens) as total_completion_tokens,
         SUM(message_count) as total_messages,
         MAX(last_activity_at) as last_used_at
  FROM acp_sessions
  GROUP BY agent_type
  ```

**Step 3: Schema**
- Add `ACPAgentMetrics` response model to ACP schemas

**Step 4: Tests**
- Add test for aggregation endpoint with multiple agents

### Frontend Work
- In `admin-ui/app/acp-agents/page.tsx`:
  - Fetch `/admin/acp/agents/metrics` in parallel with agent configs
  - Add columns: "Sessions", "Tokens", "Messages", "Last Used"
  - Match by `agent_type` key

### Files
- **Backend:** `admin_acp_agents.py`, `admin_acp_sessions_service.py`, ACP schemas
- **Frontend:** `admin-ui/app/acp-agents/page.tsx`, `admin-ui/lib/api-client.ts`
- **Tests:** Backend + frontend

### Estimated Effort: 1-2 days

---

## Item 4: ACP Session Cost Column (REVIEW.md 4.7)

**Complexity: MEDIUM — Requires model tracking + pricing integration**

### Current State
- ACP sessions track token counts but NOT the model used
- A comprehensive `pricing_catalog.py` exists with rates for 50+ models across 12 providers
- Cost = `(prompt_tokens × prompt_rate + completion_tokens × completion_rate) / 1000`

### Backend Work

**Step 1: Track model in sessions**
- **File:** `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Add `model` field to session schema and DB table
- Set from the agent config's model when session is created
- Migration: existing sessions get `model = NULL` (cost shown as "Unknown")

**Step 2: Cost computation utility**
- **File:** `tldw_Server_API/app/core/Usage/pricing_catalog.py` (extend)
- Add `compute_session_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None`
- Returns `None` if model not in pricing catalog (unknown cost)

**Step 3: Extend session response**
- **File:** ACP schemas
- Add to `ACPSessionUsageResponse`:
  ```python
  estimated_cost_usd: float | None = None
  model: str | None = None
  ```
- Compute cost when returning session data

**Step 4: Extend aggregation (from Item 3)**
- Add `total_estimated_cost_usd` to the per-agent metrics from Item 3
- Add `estimated_cost_usd` to individual session list responses

**Step 5: Tests**
- Unit test for cost computation with known model rates
- Integration test for session response including cost

### Frontend Work
- In `admin-ui/app/acp-sessions/page.tsx`: Add "Est. Cost" column showing `$X.XX`
- Format with `Intl.NumberFormat` for currency
- Show "—" for sessions with unknown model
- In `admin-ui/app/acp-agents/page.tsx`: Add "Total Cost" to agent metrics (from Item 3)

### Files
- **Backend:** `admin_acp_sessions_service.py`, `pricing_catalog.py`, ACP schemas, DB migration
- **Frontend:** `admin-ui/app/acp-sessions/page.tsx`, `admin-ui/app/acp-agents/page.tsx`
- **Tests:** Backend pricing + session tests, frontend column tests

### Estimated Effort: 2-3 days

### Dependency: Item 3 should be implemented first (agent metrics endpoint), then extended with cost data.

---

## Recommended Implementation Order

```
Item 1 (Audit cross-ref)     ─── Frontend only, 2-3 hours
        │
Item 2 (Incident SLA)        ─── Independent, 1-2 days
        │
Item 3 (Agent metrics)       ─── Independent, 1-2 days
        │
Item 4 (Session cost)        ─── Depends on Item 3, 2-3 days
```

**Total estimated effort:** ~5-8 days of focused work (backend + frontend combined)

**Parallelization:** Items 1-3 can be done in parallel by different developers. Item 4 depends on Item 3's aggregation endpoint.

---

## What Can Be Done Without Backend Changes

| Item | Frontend-Only Possible? | Notes |
|------|:---:|-------|
| 1. Audit cross-ref | **Yes** | Backend already supports request_id filtering |
| 2. Incident SLA | **Partial** | MTTR from existing fields; MTTA needs `acknowledged_at` |
| 3. Agent metrics | **No** | Needs aggregation endpoint |
| 4. Session cost | **No** | Needs model field + pricing integration |
