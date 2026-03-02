# Benchmark Guide (API + WebUI/Extension) Design

Date: 2026-03-02  
Status: Approved

## 1) Goal

Create a single canonical user guide for benchmark creation/runs focused on:

- API workflows
- WebUI/extension UI workflows
- Current shipped behavior with explicitly labeled roadmap notes

Audience is mixed: operator-first content with a contributor appendix.

## 2) Problem Statement

Benchmark capability exists across backend and UI surfaces, but guidance is fragmented:

- Benchmark endpoints are implemented under unified evaluations routes.
- WebUI/extension benchmark run flow exists in the Evaluations Runs tab.
- Existing docs are evaluations-heavy and benchmark coverage is mostly API/CLI/internal, not one end-to-end operator guide for API + WebUI/extension.

Result: users can run benchmarks today but must infer steps across multiple documents and code paths.

## 3) Existing State (Validated)

### API surface

- `GET /api/v1/evaluations/benchmarks`
- `GET /api/v1/evaluations/benchmarks/{benchmark_name}`
- `POST /api/v1/evaluations/benchmarks/{benchmark_name}/run`

Implemented in:

- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_benchmarks.py`
- Mounted via `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`

### WebUI/extension surface

- Evaluations route resolves to shared UI package implementation.
- Benchmark run UI exists in Runs tab via ad-hoc evaluator mode `benchmark-run`.

Implemented in:

- `apps/packages/ui/src/components/Option/Evaluations/tabs/RunsTab.tsx`
- `apps/packages/ui/src/components/Option/Evaluations/hooks/useRuns.ts`
- `apps/packages/ui/src/services/evaluations.ts`

### Documentation state

- Existing server/user guides cover evaluations broadly.
- No single canonical benchmark guide for API + WebUI/extension operator workflow.

## 4) Proposed Approach (Selected)

Use one canonical guide with index/cross-links.

### Why this approach

- Reduces drift versus split guides.
- Improves discoverability and task completion for operators.
- Keeps contributor depth in an appendix without overloading the main path.

## 5) Deliverables

1. New guide:
   - `Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md`
2. Discoverability update:
   - Add guide link in `Docs/User_Guides/index.md`
3. Cross-links (minimal):
   - Add references from:
     - `Docs/User_Guides/Server/Evaluations_User_Guide.md`
     - `Docs/User_Guides/WebUI_Extension/User_Guide.md`

## 6) Guide Information Architecture

Planned sections:

1. Audience and prerequisites
2. Current-state capability map (what exists now)
3. WebUI/extension quickstart for benchmark runs
4. API quickstart for benchmark catalog/info/run
5. “Creating custom benchmarks” (current supported path only)
6. Troubleshooting
7. Roadmap (not yet shipped)
8. Contributor appendix (key files and extension points)

## 7) Data Flow Coverage In Guide

### WebUI/extension benchmark run flow

1. User selects Evaluations -> Runs.
2. User switches ad-hoc endpoint to `benchmark-run`.
3. UI loads benchmark catalog from `/api/v1/evaluations/benchmarks`.
4. User selects benchmark and submits JSON payload.
5. UI posts to `/api/v1/evaluations/benchmarks/{name}/run`.
6. UI displays returned run summary/output.

### API benchmark run flow

1. Client lists benchmarks.
2. Client retrieves benchmark info.
3. Client posts run payload (e.g., `limit`, `api_name`, `parallel`, `save_results`, optional filters).
4. Server returns summary including counts and score aggregates.

## 8) Accuracy and Safety Constraints

- Document only verified shipped behavior.
- Use mounted unified route paths exactly as implemented.
- Label roadmap content explicitly as non-shipped.
- Avoid claiming dedicated benchmark-creation UI if not present.

## 9) Error Handling/Troubleshooting Content Plan

Guide will include explicit resolutions for:

- 401/403 auth/permissions mismatch
- benchmark not found (404)
- dataset load failure for benchmark
- evaluation execution failures
- rate limiting behavior

## 10) Validation Plan

Documentation validation:

- Verify all referenced files/routes exist.
- Verify examples match request/response models in code.
- Run docs tests covering guide structure/linking when available.

Success criteria:

- Operator can execute benchmark run via WebUI/extension without guessing.
- Operator can execute benchmark run via API using copy/paste examples.
- Reader can distinguish current capability from roadmap.
- Guide is discoverable from user guide index.

## 11) Out of Scope

- CLI workflow coverage in this guide
- New benchmark backend features
- New WebUI feature implementation beyond documentation

