# Text2SQL Retriever Design

Date: 2026-03-07
Owner: RAG / Retrieval
Status: Approved for planning

## 1) Problem Statement
Users should be able to ask natural-language analytical questions and retrieve structured answers from SQL data, while preserving the current RAG architecture and strict security posture.

The solution must:
- Support both internal tldw databases and external SQL connectors.
- Return both generated SQL and executed results.
- Enforce strict read-only execution.
- Support typical BI-style multi-table joins and grouped analytics in v1.
- Be available both as a standalone API and as a RAG source.

## 2) Design Decisions (Validated)
- Integration pattern: shared Text2SQL core + dual adapters (standalone endpoint + RAG source).
- SQL generation: LLM generation + AST validation + deterministic rewrite.
- Guardrails: strict mode only in v1.
- Response default: SQL + result rows + execution metadata.

## 3) Approach Options
### Option A: RAG-first only
Pros: fastest route to RAG usage.
Cons: standalone API becomes awkward and duplicated later.

### Option B: Shared core with dual adapters (Selected)
Pros: one policy surface, no duplication, consistent behavior across entry points.
Cons: slightly higher up-front design cost.

### Option C: Separate implementations
Pros: per-path tailoring.
Cons: policy and behavior drift risk; duplicated tests and security logic.

## 4) Revised Architecture (with hardening)

### 4.1 Core Components
1. `Text2SQLCoreService`
- Orchestrates schema selection, SQL generation, guard, execution, and shaping.
- Shared by all entry points.

2. `Text2SQLSourceRegistry` (new canonical source map)
- Single fail-closed registry used by:
  - request schema source validation,
  - source string -> enum mapping,
  - retriever registration/dispatch.
- Unknown sources must raise validation errors, never default to `media_db`.
- Provide separate public and internal source profiles so internal-only sources
  (for example `prompts`, `claims`) are not accidentally removed by API-facing
  normalization.

3. `SchemaCatalog`
- Builds compact schema context (tables, columns, keys, semantic hints) per target.
- Supports internal DB adapters and external connector adapters.
- Schema cache with short TTL.

4. `SqlGenerator`
- LLM prompt includes scoped schema, query intent, and policy constraints.
- Returns SQL plus optional confidence/reasoning metadata.

5. `SqlGuard`
- AST parse + policy validation + deterministic rewrite.
- Enforces one read-only statement and bounded output.

6. `SqlExecutor`
- Adapter interface for internal/external backends.
- Executes with hard timeout and max-row controls.

7. `SqlResultProjector`
- Shapes endpoint response.
- Converts rows into `Document` objects for RAG retrieval/fusion.

8. `SqlAuditTelemetry`
- Logs SQL fingerprint, connector id, row count, latency, block reason.
- Must never log raw secrets or full sensitive result payloads.

### 4.2 Security-Critical Controls
Strict mode requires all of the following (not optional):
- AST allowlist (`SELECT`/`WITH` only).
- Single statement only.
- Denylist for write/DDL/session mutation primitives.
- Forced `LIMIT` injection/clamping.
- Hard execution timeout.
- Row and payload budget caps.
- DB/session read-only mode where supported.
- Read-only credentials for connector principals.
- Per-tenant connector ACL checks.

## 5) API and Integration Design

### 5.1 Standalone Endpoint
`POST /api/v1/text2sql/query`

Request (conceptual):
- `query: str`
- `target_id: str` (internal target alias or external connector id)
- `max_rows: int` (capped server-side)
- `timeout_ms: int` (capped server-side)
- `include_sql: bool = true` (default true)

Response:
- `sql` (executed SQL)
- `columns`
- `rows`
- `row_count`
- `truncated: bool`
- `duration_ms`
- `target_id`
- `guardrail`: policy metadata (limit injected, clamped, etc.)
- `trace_id`

### 5.2 RAG Source Integration
- Add `sql` as valid `sources` entry.
- Add `DataSource.SQL`.
- Register `SQLRetriever` in multi-source retrieval orchestration.
- Extend request contract with SQL target selector (for example `sql_target_id`).
- SQL rows map to `Document` objects with explicit structured metadata.

## 6) Data Flow
1. Request enters standalone endpoint or unified RAG.
2. Source/target validation via canonical source registry.
3. RBAC + connector ACL check.
4. SchemaCatalog returns scoped schema summary.
5. SqlGenerator produces candidate SQL.
6. SqlGuard validates and rewrites (strict mode).
7. SqlExecutor runs query under read-only/time/row limits.
8. SqlResultProjector returns endpoint payload and/or RAG `Document`s.
9. SqlAuditTelemetry emits structured metrics/audit events.

## 7) Scoring and Fusion Policy (new)
Current fusion weights do not account for SQL source. Add explicit SQL scoring policy:
- `sql_confidence` from generator + guard outcomes.
- `execution_quality` signal (non-empty rows, low truncation, stable schema match).
- Optional rerank normalization before multi-source fusion.
- Add `DataSource.SQL` weight explicitly; do not rely on fallback defaults.

## 8) Error Model
Deterministic error codes/messages:
- `invalid_source`
- `unauthorized_target`
- `schema_unavailable`
- `sql_generation_failed`
- `sql_policy_violation`
- `sql_timeout`
- `sql_execution_failed`
- `result_budget_exceeded`

Errors should be user-safe; internals go to logs/telemetry.

## 9) RBAC and Tenancy
Current RAG endpoints are gated by `media.read`, which is too coarse for external SQL.

Add dedicated permission(s):
- `sql.read` for text2sql execution.
- Optional future `sql.admin` for connector lifecycle.

Authorization requirements:
- caller has `sql.read`.
- caller has access to `target_id` within tenant/org scope.
- connector resolution is registry-backed only (no raw DSN/credentials in request).
- `sql.read` must be seeded/backfilled in RBAC defaults and migration paths so
  existing deployments do not fail unexpectedly after rollout.

## 10) Performance and Budget Controls
- `max_rows` hard cap.
- `max_columns` cap.
- per-cell and per-row char caps.
- response byte budget with truncation markers.
- timeout and optional cancellation.
- optional preflight planning/cost checks where backend supports them.

## 11) Backward Compatibility and Rollout
Phase 1:
- internal DB targets + standalone endpoint + SQL source in RAG.

Phase 2:
- external connectors via registry-backed adapters.

Phase 3:
- richer optimization (plan checks, learned SQL hints, richer governance).

## 12) Testing Strategy
1. Unit
- source registry fail-closed behavior.
- SQL guard policy matrix (valid/invalid).
- limit rewrite and clamp behavior.
- result budgeting/truncation.

2. Integration
- standalone endpoint success and policy-failure cases.
- unified RAG with `sources=["sql"]`.
- per-connector RBAC and tenant isolation.

3. Security
- injection attempts, multi-statement attempts, write attempts.
- forbidden function/pragma/DDL patterns.

4. Property-based
- fuzz SQL strings against guard invariants.

5. Regression
- NL->SQL golden cases for joins/aggregations.

## 13) Explicit Non-Goals (v1)
- write operations (`INSERT/UPDATE/DELETE/DDL`).
- arbitrary user-supplied DSNs in requests.
- advanced SQL wizard features as primary workflow.

## 14) Risks and Mitigations
1. Mapping drift across schema/pipeline/retriever.
- Mitigation: canonical source registry + fail-closed validation.

2. Security bypass via parser-only checks.
- Mitigation: dual-layer enforcement (AST + DB/session read-only + read-only creds).

3. Unbounded tabular payloads degrading RAG quality.
- Mitigation: strict result budgets + explicit truncation metadata.

4. RBAC leakage from coarse permissions.
- Mitigation: dedicated `sql.read` plus connector ACL.

## 15) Acceptance Criteria
- `sql` source supported in unified RAG without fallback misrouting.
- Standalone endpoint returns SQL + results under strict read-only policy.
- External connectors are accessible only via registry IDs and tenant ACL.
- All policy violations return deterministic structured errors.
- Security and integration tests cover strict guardrails and tenant isolation.
