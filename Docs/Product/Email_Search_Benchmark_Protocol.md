# Email Search Benchmark Protocol (M1-009)

Last Updated: 2026-02-10
Owner: Backend and Search Team
Related PRD: `Docs/Product/Email_Ingestion_Search_PRD.md`

## Purpose

Define a reproducible protocol for Stage-1 email operator search performance claims, including:

1. Hardware/software profile capture.
2. Dataset shape requirements.
3. Fixed query-mix methodology.
4. Warm and cold run measurement method.
5. Report artifact location and required fields.

## Harness and Artifacts

1. Benchmark harness script:
   - `Helper_Scripts/benchmarks/email_search_bench.py`
2. Sample query mix fixture:
   - `Helper_Scripts/benchmarks/email_search_query_mix.sample.jsonc`
3. Sample workload trace fixture:
   - `Helper_Scripts/benchmarks/email_search_workload_trace.sample.json`
4. Recommended report output path:
   - `.benchmarks/email_search_report.json`

## Environment Profile Requirements

Every report must include:

1. OS/platform string.
2. CPU model and logical core count.
3. Python version.
4. Database backend and DB file path.
5. Timestamp (UTC ISO-8601).

The harness writes these fields automatically in `environment` and `benchmark`.

## Dataset Shape Requirements

Target benchmark profile for performance claims in PRD NFR:

1. Message count: 1,000,000 (single tenant) for final NFR signoff.
2. Attachment ratio: record actual ratio in report (recommended representative range 15% to 35%).
3. Label cardinality: record distinct label count.
4. Participant cardinality: use realistic sender/recipient pools (not a single sender).
5. Time span: include min/max `internal_date` in report.

For developer iteration, smaller fixtures are acceptable (for example 10k to 100k), but must not be used as final NFR evidence.

## Query Mix Requirements

Use at least one query for each operator class:

1. `from:`
2. `to:`
3. `subject:`
4. `label:`
5. `has:attachment`
6. `before:`
7. `after:`
8. `newer_than:` or `older_than:`
9. free-text with unary negation (`-label:...` or similar)
10. explicit `OR`

The harness auto-builds a mix from observed dataset values, or accepts a fixed file via `--query-mix-file`.
For M3 index/planner tuning, prefer a trace-derived mix via `--workload-trace-file` and tune with top-N production-like queries.

## Warm and Cold Methodology

Run both paths in a single benchmark execution:

1. Cold pass:
   - Reopen DB connection for each query.
   - Execute each query once.
   - Report aggregate p50/p95 over cold samples.
2. Warm pass:
   - Keep one DB connection for the full pass.
   - Per query: run `warmup_runs` unmeasured calls.
   - Per query: run `runs` measured calls.
   - Report per-query and aggregate p50/p95.

Default harness values:

1. `warmup_runs=3`
2. `runs=20`
3. `limit=50`

## Command Recipes

1. Build synthetic fixture and benchmark:

```bash
python Helper_Scripts/benchmarks/email_search_bench.py \
  --db-path .benchmarks/email_search_bench.sqlite \
  --ensure-fixture \
  --fixture-messages 20000 \
  --runs 30 \
  --warmup-runs 5 \
  --out .benchmarks/email_search_report.json
```

2. Benchmark existing populated tenant (no fixture writes):

```bash
python Helper_Scripts/benchmarks/email_search_bench.py \
  --db-path /path/to/media.db \
  --tenant-id user:1 \
  --runs 20 \
  --warmup-runs 3 \
  --out .benchmarks/email_search_report.json
```

3. Use fixed query mix:

```bash
python Helper_Scripts/benchmarks/email_search_bench.py \
  --db-path .benchmarks/email_search_bench.sqlite \
  --query-mix-file Helper_Scripts/benchmarks/email_search_query_mix.sample.jsonc \
  --out .benchmarks/email_search_report.json
```

4. Use workload trace and include SQLite query-plan capture:

```bash
python Helper_Scripts/benchmarks/email_search_bench.py \
  --db-path .benchmarks/email_search_bench.sqlite \
  --workload-trace-file Helper_Scripts/benchmarks/email_search_workload_trace.sample.json \
  --workload-top-n 15 \
  --capture-query-plans \
  --out .benchmarks/email_search_report.json
```

## Pass/Fail Criteria for Stage-1 Target

Warm-pass aggregate targets (from PRD NFR):

1. p50 <= 250 ms
2. p95 <= 900 ms

Cold pass is recorded for observability/regression tracking and is not the primary SLO gate.

## Reporting Requirements

Any published benchmark claim must include:

1. Full JSON report artifact.
2. Command used.
3. Dataset profile summary.
4. Whether p50 and p95 warm-pass targets were met.
5. Date and commit SHA used for run.

When `--capture-query-plans` is enabled for M3 planner/index work, include the `warm_pass.query_plan_summary` block (captured query count and index-hit coverage) in the published evidence.
