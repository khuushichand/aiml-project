# Email Search M3-003 Index and Planner Tuning

Last Updated: 2026-02-10
Owner: Backend and Search Team
Related PRD: `Docs/Product/Email_Ingestion_Search_PRD.md`

## Scope

This note captures the M3-003 search planner/index tuning changes for normalized email search and the benchmark protocol updates used for trace-driven validation.

## Index Changes

Applied in `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` (`_EMAIL_INDICES_SQL`):

1. `idx_email_messages_tenant_date_id` on `(tenant_id, internal_date DESC, id DESC)`
   - Aligns with default sort path and tenant-scoped paging.
2. `idx_email_messages_tenant_has_attachments_date` on `(tenant_id, has_attachments, internal_date DESC, id DESC)`
   - Improves `has:attachment` + recent-date query paths.
3. `idx_email_message_participants_message_role` on `(email_message_id, role, participant_id)`
   - Reduces participant-role EXISTS lookup cost for `from:/to:/cc:/bcc:` operators.

Validation test coverage:

- `tldw_Server_API/tests/DB_Management/test_email_native_stage1.py::test_email_search_m3_indexes_exist_on_sqlite`

## Workload Trace and Planner Capture

`Helper_Scripts/benchmarks/email_search_bench.py` now supports:

1. `--workload-trace-file` (JSON trace query inputs with counts)
2. `--workload-top-n` / `--workload-min-count` filtering
3. `--capture-query-plans` (SQLite `EXPLAIN QUERY PLAN` capture for each benchmark query)

Sample workload trace fixture:

- `Helper_Scripts/benchmarks/email_search_workload_trace.sample.json`

## Benchmark Command (Trace-Driven)

```bash
python Helper_Scripts/benchmarks/email_search_bench.py \
  --db-path .benchmarks/email_search_bench.sqlite \
  --ensure-fixture \
  --fixture-messages 20000 \
  --workload-trace-file Helper_Scripts/benchmarks/email_search_workload_trace.sample.json \
  --workload-top-n 15 \
  --warmup-runs 5 \
  --runs 30 \
  --capture-query-plans \
  --out .benchmarks/email_search_report_m3_003.json
```

## Benchmark Evidence (2026-02-10)

Executed against a 3,000-message fixture tenant with trace-derived top-5 queries and SQLite query-plan capture:

```bash
python Helper_Scripts/benchmarks/email_search_bench.py \
  --db-path /tmp/email_m3_003_bench.sqlite \
  --tenant-id bench-tenant \
  --workload-trace-file Helper_Scripts/benchmarks/email_search_workload_trace.sample.json \
  --workload-top-n 5 \
  --warmup-runs 1 \
  --runs 5 \
  --capture-query-plans \
  --query-plan-statements-max 4 \
  --out /tmp/email_m3_003_report_v2.json
```

Observed report highlights:

1. Warm summary: `p50_ms=9.51`, `p95_ms=10.89` (NFR target pass: `p50<=250`, `p95<=900`).
2. Planner capture summary:
   - `captured_queries=5`
   - `queries_with_index_hits=5`
   - `total_explained_statements=11`
   - `total_index_hit_rows=22`
3. Captured plans showed new/updated indexes in use, including:
   - `idx_email_messages_tenant_date_id`
   - `idx_email_messages_tenant_has_attachments_date`
   - `idx_email_message_participants_message_role`

## Acceptance Mapping

M3-003 deliverables and acceptance mapping:

1. Index tuning and planner optimization:
   - Implemented via new composite indexes and query-plan capture in the benchmark harness.
2. Documented and benchmarked:
   - This document + updated benchmark protocol/README.
3. NFR target validation:
   - Use report targets from `email_search_bench.py` (`p50 <= 250ms`, `p95 <= 900ms`) on representative corpus before cutover.
