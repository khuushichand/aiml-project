# Prompt Studio API

The Prompt Studio module provides a structured workflow to design, version, test, evaluate, and optimize prompts within projects. It exposes cohesive APIs for projects, prompts (with versioning), test cases, evaluations, optimizations, and real-time updates.

## Overview

- Projects group all Prompt Studio entities (prompts, test cases, evaluations, optimizations) under a workspace.
- Prompts are versioned. Every update creates a new immutable version for reproducibility.
- Test cases define inputs, expected outputs, tags, and a golden flag; they form the corpus for evaluation.
- Evaluations run a prompt (or prompt version) against a set of test cases and save metrics.
- Optimizations run strategies to iteratively improve prompts (e.g., iterative refinement, hyperparameter tuning).
- Real-time updates are available via WebSocket with SSE fallback.

Authentication follows the server's standard modes (single-user API key or multi-user JWT). Endpoints are project-scoped: reads require access, writes require write access. Rate limits apply to generation/optimization endpoints.

### Auth + Rate Limits
- Single-user: header `X-API-KEY: <key>`
- Multi-user: header `Authorization: Bearer <JWT>`
- Rate limits: applied to generation (`/generate`, `/execute`) and optimization endpoints; listing/CRUD use standard limits.

Tag in OpenAPI: `prompt-studio`.

Auth headers
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`

### Test/CI Environment Variables (Prompt Studio)
- `TLDW_PS_BACKEND=sqlite|postgres` - for the heavy optimization suite, pick a single backend per run (default: sqlite).
- `TLDW_PS_STRESS=1` - enable larger datasets/iterations in heavy tests.
- `TLDW_PS_TC_COUNT` - override test-case volume (default 250; stress 1000).
- `TLDW_PS_ITERATIONS` - override iteration count (default 5; stress 10).
- `TLDW_PS_OPT_COUNT` - override concurrent optimizations (default 3; stress 8).
- `TLDW_TEST_POSTGRES_REQUIRED=1` - fail fast if Postgres probe fails (otherwise Postgres tests are skipped when unreachable).
- `TLDW_PS_SQLITE_WAL=1` - opt-in to WAL for per-test SQLite DBs (default: DELETE mode for CI tidiness).
- `TLDW_PS_JOB_LEASE_SECONDS` - lease window for processing jobs in the Prompt Studio queue (default: 60). Expired processing jobs are reclaimed.
- `TLDW_PS_HEARTBEAT_SECONDS` - heartbeat interval override for renewing job leases during processing (default: lease/2 up to 30s).

### Strategy Parameters (validation highlights)
- `beam_search`:
  - `beam_width` ≥ 2, `max_candidates` ≥ `beam_width` (if both provided)
  - `diversity_rate` in [0, 1], `prune_threshold` in [0, 1]
  - `length_penalty` in [0, 2]
  - `candidate_reranker`: one of `none|score|diversity|hybrid`
- `anneal` (simulated annealing):
  - `cooling_rate` in (0, 1], `initial_temp` > 0, `min_temp` ≥ 0 and ≤ `initial_temp`
  - Optional schedule: `exponential|linear|cosine`
  - If `schedule=linear` and `step_size`/`epochs` provided, enforce `step_size * epochs ≤ (initial_temp - min_temp)`
- `genetic`:
  - `population_size` ≥ 2, `mutation_rate` in [0, 1], `crossover_rate` in [0, 1], `elitism` ≥ 0
  - `selection`: `tournament|roulette|rank`
  - `crossover_operator`: `one_point|two_point|uniform`
- `hyperparameter`, `random_search`:
  - `max_trials` ≥ 1 (if provided)
  - `max_tokens_range`: `[min, max]` with `1 ≤ min < max ≤ 100000`

## More Examples

### Update Project
```bash
curl -X PUT "http://localhost:8000/api/v1/prompt-studio/projects/update/1" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"description": "Updated description"}'
```

### Delete Project (soft)
```bash
curl -X DELETE "http://localhost:8000/api/v1/prompt-studio/projects/delete/1" \
  -H "X-API-KEY: $API_KEY"
```

### Archive / Unarchive Project
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/projects/archive/1" -H "X-API-KEY: $API_KEY"
curl -X POST "http://localhost:8000/api/v1/prompt-studio/projects/unarchive/1" -H "X-API-KEY: $API_KEY"
```

### Update Test Case
```bash
curl -X PUT "http://localhost:8000/api/v1/prompt-studio/test-cases/update/101" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"name": "Short text (v2)", "is_golden": true}'
```

### Delete Test Case
```bash
curl -X DELETE "http://localhost:8000/api/v1/prompt-studio/test-cases/delete/101" \
  -H "X-API-KEY: $API_KEY"
```

### Delete Evaluation
```bash
curl -X DELETE "http://localhost:8000/api/v1/prompt-studio/evaluations/501" -H "X-API-KEY: $API_KEY"
```

### Cancel Optimization
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/optimizations/cancel/701" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"reason": "Stopping for manual review"}'
```

### Record an Optimization Iteration
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/optimizations/iterations/701" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"iteration_number": 4, "metrics": {"accuracy": 0.82}, "tokens_used": 1400, "cost": 0.08}'
```

### List Optimization Iterations
```bash
curl -X GET "http://localhost:8000/api/v1/prompt-studio/optimizations/iterations/701?page=1&per_page=20" \
  -H "X-API-KEY: $API_KEY"
```

### Get Optimization History & Timeline
```bash
curl -X GET "http://localhost:8000/api/v1/prompt-studio/optimizations/history/701" -H "X-API-KEY: $API_KEY"
```

## Endpoints

### Projects
- Create: `POST /api/v1/prompt-studio/projects/`
- List: `GET /api/v1/prompt-studio/projects/`
  - Query params: `page`, `per_page`, `status`, `include_deleted`, `search`
  - Example response:
    ```json
    {
      "success": true,
      "data": [
        { "id": 1, "uuid": "f9e3...", "name": "Demo Project", "status": "active" }
      ],
      "metadata": { "page": 1, "per_page": 20, "total": 1, "total_pages": 1 }
    }
    ```
- Get: `GET /api/v1/prompt-studio/projects/get/{project_id}`
- Update: `PUT /api/v1/prompt-studio/projects/update/{project_id}`
- Delete: `DELETE /api/v1/prompt-studio/projects/delete/{project_id}?permanent=false`
- Archive: `POST /api/v1/prompt-studio/projects/archive/{project_id}`
- Unarchive: `POST /api/v1/prompt-studio/projects/unarchive/{project_id}`
- Stats: `GET /api/v1/prompt-studio/projects/stats/{project_id}`

### Prompts (Versioned)
- Create: `POST /api/v1/prompt-studio/prompts/create`
- List: `GET /api/v1/prompt-studio/prompts/list/{project_id}`
  - Query params: `page`, `per_page`, `include_deleted`
  - Example response:
    ```json
    {
      "success": true,
      "data": [
        { "id": 12, "project_id": 1, "name": "Summarizer", "version_number": 2 }
      ],
      "metadata": { "page": 1, "per_page": 20, "total": 1, "total_pages": 1 }
    }
    ```
- Get: `GET /api/v1/prompt-studio/prompts/get/{prompt_id}`
- Update (new version): `PUT /api/v1/prompt-studio/prompts/update/{prompt_id}`
- History: `GET /api/v1/prompt-studio/prompts/history/{prompt_id}`
- Revert (new version): `POST /api/v1/prompt-studio/prompts/revert/{prompt_id}/{version}`
- Execute (simple): `POST /api/v1/prompt-studio/prompts/execute`

### Test Cases
- Create: `POST /api/v1/prompt-studio/test-cases/create`
- Bulk Create: `POST /api/v1/prompt-studio/test-cases/bulk`
- List: `GET /api/v1/prompt-studio/test-cases/list/{project_id}`
  - Query params: `page`, `per_page`, `is_golden`, `tags`, `search`, `signature_id`
  - Example response:
    ```json
    {
      "success": true,
      "data": [
        { "id": 101, "project_id": 1, "name": "Short text", "is_golden": true }
      ],
      "metadata": { "page": 1, "per_page": 20, "total": 1, "total_pages": 1 }
    }
    ```
- Get: `GET /api/v1/prompt-studio/test-cases/get/{test_case_id}`
- Update: `PUT /api/v1/prompt-studio/test-cases/update/{test_case_id}`
- Delete: `DELETE /api/v1/prompt-studio/test-cases/delete/{test_case_id}?permanent=false`
- Import: `POST /api/v1/prompt-studio/test-cases/import` (CSV or JSON payload)
- Export: `POST /api/v1/prompt-studio/test-cases/export/{project_id}` (CSV or JSON)
- Generate: `POST /api/v1/prompt-studio/test-cases/generate`

### Evaluations
- Create: `POST /api/v1/prompt-studio/evaluations`
  - Supports async run via background task
- List: `GET /api/v1/prompt-studio/evaluations?project_id=...&prompt_id=...`

### Optimizations
- Create: `POST /api/v1/prompt-studio/optimizations/create`
- List: `GET /api/v1/prompt-studio/optimizations/list/{project_id}`
- Get: `GET /api/v1/prompt-studio/optimizations/get/{optimization_id}`
- Cancel: `POST /api/v1/prompt-studio/optimizations/cancel/{optimization_id}`
- Strategies: `GET /api/v1/prompt-studio/optimizations/strategies`
- Compare: `POST /api/v1/prompt-studio/optimizations/compare`
- Status/Health: `GET /api/v1/prompt-studio/status?warn_seconds=30` - queue depth, processing count, and lease health (active, expiring soon, stale processing)

### Real-time API
- WebSocket base: `WS /api/v1/prompt-studio/ws`
- WebSocket per project: `WS /api/v1/prompt-studio/ws/{project_id}`
- SSE fallback: `GET /api/v1/prompt-studio/ws?client_id=<id>&project_id=<optional>` (text/event-stream)
  - Requires `client_id` query param; optional `project_id` to scope events

Notes
- Several endpoints also accept “simple” aliases on the base path without trailing slashes to improve client ergonomics.
- All list endpoints return a `metadata` object with `page`, `per_page`, `total`, and `total_pages`.

## Common Schemas

- ProjectCreate, ProjectUpdate, ProjectResponse
- PromptCreate, PromptUpdate, PromptResponse, PromptVersion
- TestCaseCreate, TestCaseUpdate, TestCaseResponse, TestCaseBulkCreate, TestCaseImportRequest, TestCaseExportRequest, TestCaseGenerateRequest
- EvaluationCreate, EvaluationResponse, EvaluationMetrics
- OptimizationCreate, OptimizationResponse, OptimizationConfig
  - Note: `OptimizationConfig.strategy_params` allows optional strategy-specific knobs (e.g., `beam_width`, `cooling_rate`, `mutation_rate`). These parameters are validated when provided for supported strategies.
  - Additional optional knobs currently validated when present:
    - `beam_search`: `beam_width>=2`, `prune_threshold` in [0,1], `max_candidates>=beam_width`
    - `anneal`: `cooling_rate` in (0,1], `initial_temp>0`, `min_temp>=0` and `<=initial_temp` (if both set), `schedule` one of `exponential|linear|cosine`
    - `genetic`: `population_size>=2`, `mutation_rate` in [0,1], `crossover_rate` in [0,1], `elitism>=0`, `selection` one of `tournament|roulette|rank`

### Metrics (Prometheus)
- The status endpoint updates the following Prometheus gauges with label `backend=sqlite|POSTGRESQL`:
  - `prompt_studio_queue_depth`
  - `prompt_studio_processing`
  - `prompt_studio_leases_active`
  - `prompt_studio_leases_expiring_soon`
  - `prompt_studio_leases_stale_processing`
- Scrape via `GET /api/v1/metrics/text`.

### Idempotency
- Create endpoints (projects, prompts, optimizations) accept `Idempotency-Key` header.
- The idempotency map enforces uniqueness per user: `(entity_type, idempotency_key, user_id)`.
- Duplicate submits with the same key and user return the canonical entity without enqueuing new work.

## Quick Examples

### Create a Project
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/projects/" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "name": "Demo Project",
        "description": "Exploring prompt versions",
        "status": "active"
      }'
```

### Create a Prompt (v1)
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/prompts/create" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "name": "Summarizer",
        "system_prompt": "Summarize the content clearly.",
        "user_prompt": "{{text}}"
      }'
```

### Add Test Cases (Bulk)
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/test-cases/bulk" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "test_cases": [
          {"name": "Short text", "inputs": {"text": "Hello world"}, "expected_outputs": {"summary": "Hello world."}},
          {"name": "Long text", "inputs": {"text": "..."}, "expected_outputs": {"summary": "..."}}
        ]
      }'
```

### Update Prompt (new version)
```bash
curl -X PUT "http://localhost:8000/api/v1/prompt-studio/prompts/update/12" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"system_prompt": "Summarize concisely.", "change_description": "Tighten style"}'
```

### Revert Prompt to Specific Version
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/prompts/revert/12/1" -H "X-API-KEY: $API_KEY"
```

### Export Test Cases (JSON)
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/test-cases/export/1" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"format": "json", "include_golden_only": false, "tag_filter": ["smoke"]}'
```

### Import Test Cases via CSV Upload (multipart/form-data)

Sample CSV (save as `cases.csv`):
```
name,description,input.text,expected.summary,tags,is_golden
Short,,"Hello world","Hello world.","smoke,basic",true
Long,"Longer passage","This is a longer passage...","A concise summary...","regression",false
```

Upload with curl:
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/test-cases/import/csv-upload" \
  -H "X-API-KEY: $API_KEY" \
  -F project_id=1 \
  -F signature_id=2 \
  -F auto_generate_names=true \
  -F file=@cases.csv;type=text/csv
```

Download a CSV template derived from a signature (fields):
```bash
curl -L "http://localhost:8000/api/v1/prompt-studio/test-cases/import/template?signature_id=2" \
  -H "X-API-KEY: $API_KEY" -o template.csv
```

Notes:
- Use `input.<field>` for inputs and `expected.<field>` for expected outputs. Values may be raw strings or JSON; JSON will be parsed when present.
- Separate multiple tags with commas (`,`). The importer splits on commas.
- `signature_id` is optional; provide when schema validation is desired.

CSV column schema (conceptual JSON Schema):
```
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string" },
    "tags": { "type": "string", "description": "Comma-separated tags" },
    "is_golden": { "type": "boolean" },
    "input.*": { "type": ["string", "object"], "description": "Input fields; prefix with input." },
    "expected.*": { "type": ["string", "object"], "description": "Expected output fields; prefix with expected." }
  },
  "required": [ "input.*" ]
}
```

### Run Evaluation
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/evaluations" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "prompt_id": 12,
        "name": "Baseline Eval",
        "test_case_ids": [1,2,3],
        "config": {"model_name": "gpt-4o-mini", "temperature": 0.2, "max_tokens": 256}
      }'
```

### Create Optimization Job
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/optimizations/create" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "name": "Refine Summarizer",
        "initial_prompt_id": 12,
        "test_case_ids": [1,2,3],
        "optimization_config": {
          "optimizer_type": "iterative",
          "max_iterations": 20,
          "target_metric": "accuracy",
          "early_stopping": true
        }
      }'
```

### Subscribe to Real-time Updates (WebSocket)
```js
const ws = new WebSocket("ws://localhost:8000/api/v1/prompt-studio/ws");
ws.onopen = () => ws.send(JSON.stringify({ type: "subscribe", entity_type: "project", entity_id: 1 }));
ws.onmessage = (evt) => console.log("event", evt.data);
```

## Access Control & Limits

- Reads require project access; writes require project write access
- SecurityConfig defines limits (e.g., max prompt length, max test cases)
- Rate limiting is applied to generation/optimization endpoints

## Notes

- Prompt updates create new versions; reverting also creates a new version
- Evaluations can run synchronously or as background tasks
- Real-time updates support both WebSocket and SSE fallback
- Real-time updates support both WebSocket and SSE fallback
## Metrics

Prompt Studio emits the following metrics (names, labels) and when they are updated:

- Job queue gauges/counters
  - `jobs.queued{job_type}`: updated on job create/acquire/status refresh.
  - `jobs.processing{job_type}`: updated on acquire/complete/fail/retry/status refresh.
  - `jobs.backlog{job_type}`: computed as queued - processing; updated alongside gauges.
  - `jobs.stale_processing`: aggregate gauge from lease stats.
  - `jobs.duration_seconds{job_type}`: histogram observed when a job finishes (success/failure).
  - `jobs.queue_latency_seconds{job_type}`: histogram observed on acquire (started_at - created_at).
  - `jobs.retries_total{job_type}`: increments when a job is rescheduled for retry.
  - `jobs.failures_total{job_type,reason}`: increments on terminal failure with exception type.
  - `jobs.lease_renewals_total{job_type}`: increments on each lease heartbeat renewal.
  - `jobs.reclaims_total{job_type}`: increments when a processing job with expired lease is reclaimed.

- Idempotency
  - `prompt_studio.idempotency.hit_total{entity_type}`: increments when a duplicated request (same Idempotency-Key) returns the canonical entity.
  - `prompt_studio.idempotency.miss_total{entity_type}`: increments when a new mapping is recorded for a request.

- Postgres advisory locks
  - `prompt_studio.pg_advisory.lock_attempts_total`: increments per acquire attempt on Postgres.
  - `prompt_studio.pg_advisory.locks_acquired_total`: increments when a job row is selected with `pg_try_advisory_lock`.
  - `prompt_studio.pg_advisory.unlocks_total`: increments when the advisory lock is released.

The `/api/v1/prompt-studio/status` endpoint also updates generic gauges for Prometheus scraping:
`prompt_studio_queue_depth`, `prompt_studio_processing`, and lease gauges (`prompt_studio_leases_*`),
and refreshes the per-type Prompt Studio gauges (`queued`, `processing`, `backlog`, `stale_processing`).
