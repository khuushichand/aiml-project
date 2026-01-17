# Prompt Studio Jobs Worker Migration (Phase 2)

Status: Complete
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Move Prompt Studio background execution onto the core Jobs worker SDK. Jobs become the execution source of truth for optimization/evaluation/generation tasks instead of in-process background tasks or the legacy prompt studio queue.

## 2. Current State
- Prompt Studio job records are written to core Jobs via `PromptStudioJobsAdapter`.
- Optimization creation enqueues core Jobs; background-task execution has been removed.
- Prompt Studio job views read from core Jobs only; legacy queue usage has been removed.

## 3. Goals
- Execute Prompt Studio jobs via core Jobs workers.
- Keep API behavior unchanged (accepted response + job_id) while shifting execution off the API server.

## 4. Non-Goals
- Removing legacy prompt studio queue tables or endpoints in this phase.
- Refactoring optimization engine logic or evaluation metrics.

## 5. Proposed Jobs Execution

### 5.1 Job Types & Queues
- `domain`: `prompt_studio`
- `queue`: `PROMPT_STUDIO_JOBS_QUEUE` (default `default`)
- `job_type`: `optimization` | `evaluation` | `generation`

### 5.2 Payload Shape (optimization example)
```json
{
  "optimization_id": 42,
  "entity_id": 42,
  "optimizer_type": "iterative",
  "optimization_config": { "max_iterations": 20 },
  "initial_prompt_id": 12,
  "test_case_ids": [1, 2, 3],
  "project_id": 7,
  "created_by": "user-123",
  "submitted_at": "2026-01-10T01:00:00Z",
  "request_id": "req-abc"
}
```
Notes:
- `entity_id` is included for generic worker mapping.
- Evaluation jobs should include `evaluation_id` + `prompt_id` + `test_case_ids` + `model_configs`.
- Generation jobs should include `project_id` and generation parameters (`type`, `description`, etc.).

### 5.3 Worker Flow
Add a Jobs worker service `tldw_Server_API/app/core/Prompt_Management/prompt_studio/services/jobs_worker.py`:
1. Acquire jobs via `WorkerSDK` (domain `prompt_studio`, queue `PROMPT_STUDIO_JOBS_QUEUE`).
2. Validate job type and required payload IDs.
3. Load a Prompt Studio database for the job owner.
4. Use `JobProcessor` to execute `process_optimization_job`, `process_evaluation_job`, or `process_generation_job`.
5. Update core Jobs status/result on success; mark failure with an error message on exceptions.

### 5.4 API Behavior
- Endpoints enqueue core Jobs and do not spawn background tasks.
- `PROMPT_STUDIO_JOBS_BACKEND` is now ignored; legacy backend removed.

## 6. Migration Steps
1. Add the Prompt Studio Jobs worker and document run command.
2. Gate optimization endpoints to enqueue core Jobs when enabled.
3. Validate Prompt Studio E2E/integration tests with the worker running.

## 7. Testing
- E2E: `tldw_Server_API/tests/e2e/test_prompt_studio_e2e.py`
- Integration: `tldw_Server_API/tests/prompt_studio/integration/test_optimizations_dual_backend_heavy.py`

## 8. Open Questions
- Should evaluation creation be moved fully to core Jobs (no BackgroundTasks) in Phase 2, or phased later?
