# Prompt Studio - MCTS Sequence Optimization (MCTS-OPS Inspired) PRD

- Version: v1.0 (MVP without sandboxed code execution)
- Owner: Prompt Studio
- Stakeholders: API team, WebUI team, DB team
- Target Release: 1-2 sprints for MVP, +1 sprint for code evaluator

## Overview

Add a new optimization strategy ("mcts") that treats prompt design as sequential planning over multi-step prompt sequences with Monte Carlo Tree Search (MCTS). Leverage low-cost LLM scoring and reward backpropagation to explore, evaluate, and refine prompt sequences; optionally apply a feedback revision loop to low-reward candidates. Integrates with existing Prompt Studio endpoints, job queue, TestRunner, PromptExecutor, and WebSocket events.

## Implementation Status (Rolling)

- Status: In Progress
- Last Updated: [auto]

Completed (MVP + MCTS core):
- API/schema: endpoint validation for `optimizer_type="mcts"` + `strategy_params` (range checks; includes `mcts_simulations`, `mcts_max_depth`, `mcts_exploration_c`, `prompt_candidates_per_node`, `score_dedup_bin`, `early_stop_no_improve`, `token_budget`, `feedback_*`, model overrides).
- Engine: `MCTSOptimizer` integrated with `OptimizationEngine` under strategy `"mcts"`.
- MCTS core algorithm: full tree search with Node(Q, N, parent/children, score_bin), UCT selection (`mcts_exploration_c`), expansion with `prompt_candidates_per_node` and sibling dedup using `score_dedup_bin`, simulation over multi-segment sequences (via `PromptDecomposer`), and backpropagation of rewards.
- Contextual generation: carries accumulated system context across segments for candidate creation; user content kept stable for evaluation.
- Optional feedback/refinement: honors `feedback_enabled`, `feedback_threshold`, `feedback_max_retries` by delegating to `IterativeRefinementOptimizer` and re-evaluating improved variants.
- Optimization MVP: iterative candidate variant generator with evaluation via existing `TestRunner`/`PromptExecutor`; early stop on no-improve.
- ProgramEvaluator Phase 2 (sandbox): feature-gated per project and env; extracts Python from LLM output, executes under isolated subprocess with import whitelist and no file/network, evaluates objective/constraints, and maps to reward [-1..10]; wired into `TestRunner` for `runner="python"` cases.
- PromptQualityScorer upgraded: optional cheap LLM scoring fallback (configurable `scorer_model`) blended with heuristics; in-memory TTL cache to reduce token usage; explicit `score_to_bin` helper for consistent dedup bins.
- Cost controls: MCTS tracks cumulative tokens for scorer/rephrase calls via `PromptExecutor` and enforces `token_budget` with early stop; `_call_llm` adds simple backoff/retry for 429/rate limits; in-memory caching for segment rephrases and evaluation results to avoid duplicate rollouts; optional DB-backed cache (sync_log) for scorer/rephrase/eval with TTL.
- Metrics + instrumentation: Records `sims_total`, `tree_nodes`, `avg_branching`, `best_reward`, `tokens_spent`, `duration_ms` via `prompt_studio_metrics.record_mcts_summary`. Error counters added (`prune_low_quality`, `prune_dedup`, `scorer_failure`, `evaluator_timeout`).
- WS lifecycle + cancellation: Broadcasts `OPTIMIZATION_STARTED` and `OPTIMIZATION_COMPLETED`; periodic cancellation checks exit long loops promptly.
- WebSocket: lifecycle events (started/completed) and throttled per-simulation progress broadcasts (iteration, current score, best score) via shared `EventBroadcaster`. Throttle interval configurable via `ws_throttle_every` (defaults ~ n_sims/50).
- Persistence (trace): Each throttled iteration is persisted via `record_optimization_iteration` with compact variant metadata (prompt_id, system_hash, preview). Final compact search trace (best path + top-K) included in `final_metrics.trace` for the optimization row.
- Feature gating: MCTS strategy is disabled by default; enabled in development via canary or explicitly with `PROMPT_STUDIO_ENABLE_MCTS=true`. Debug decision dumps controlled by `PROMPT_STUDIO_MCTS_DEBUG_DECISIONS=true`.
- Docs & Guides: See `Docs/Guides/Prompt_Studio_MCTS_Guide.md`, `Docs/Guides/Prompt_Studio_Program_Evaluator.md`, and `Docs/Guides/Prompt_Studio_Ablations.md`.
- Quality/Decomposition helpers: heuristic `PromptQualityScorer` (0..10) and `PromptDecomposer` (naive segment split); pruning via `min_quality` strategy param.
- Program Evaluator (Phase 2 groundwork): feature-flagged `ProgramEvaluator` stub (no code exec) wired into `TestRunner` for runner="python" cases; maps heuristic reward to aggregate score when enabled.
- OpenAPI example: added an `mcts` example payload to `/optimizations/create` for discoverability.

In Progress / Planned next:
- ProgramEvaluator sandbox (actual execution) behind flag; per-project controls and resource limits.
- Docs: examples, UI notes, and ablation scripts; README WS payload samples and advanced usage.
 - Tests: expand unit/integration/perf coverage; throttle WS for large n_sims.

## Goals

- Improve robustness on "hard" tasks by exploring prompt sequences, not just single prompts.
- Provide token-aware, budget-bounded optimization with early stops and deduplication.
- Stream real-time progress via existing Prompt Studio WebSocket (WS).

## Non-Goals

- No new public endpoints (use existing `/api/v1/prompt-studio/optimizations/create`).
- No WebUI redesign (rely on current WS channel and optimization views).
- No mandatory sandboxed code execution in MVP (added in v2 behind a feature flag).

## Personas & Use Cases

- Prompt engineers: Optimize prompts for difficult tasks with structured, multi-step sequences.
- QA/researchers: Run controlled experiments comparing strategies (iterative vs mcts) on the same test set.
- Developers: Tune performance/cost knobs; introspect search traces and best candidate path.

## Functional Requirements

### Strategy: "mcts"

Inputs (via `optimization_config.strategy_params`):

- `mcts_simulations` (int, default 20, 1-200)
- `mcts_max_depth` (int, default 4, 1-10)
- `mcts_exploration_c` (float, default 1.4, 0.1-5.0)
- `prompt_candidates_per_node` (int, default 3, 1-10)
- `score_dedup_bin` (float, default 0.1, 0.05-0.5)
- `feedback_enabled` (bool, default true)
- `feedback_threshold` (float 0-10, default 6.0)
- `feedback_max_retries` (int, default 2)
- `token_budget` (int, default 50_000)
- `early_stop_no_improve` (int, default 5)
- `scorer_model` (string, default small/cheap model)
- `rollout_model` (string, default configured model)
- `min_quality` (float 0-10, default 0.0) - prune low-quality variants pre-evaluation using heuristic scorer (implemented in MVP).

MCTS loop:

- Selection: UCT selects children by `Q/N + c * sqrt(log(Np)/N)`.
- Expansion: Generate K prompt variants for current segment, score each; bin scores by `score_dedup_bin` and reuse siblings with same bin to cap branching.
- Simulation: Build a candidate sequence; call PromptExecutor/TestRunner to get a numeric reward (0-10). Failures score -1.
- Backpropagation: Update Q, N along the path; track best-so-far.
- Optional feedback: If reward < threshold, apply one self-refine iteration and re-evaluate; use `max(reward, refined_reward)`.

Decomposition & context:

- Decompose task/goal into segments (context, instruction, constraints, examples). Keep 3-6 segments.
- Each next generation receives "context so far" to maintain coherence.

### Job Integration

- Create via existing POST `/api/v1/prompt-studio/optimizations/create` with `optimizer_type="mcts"`.
- Run under job processor; stream progress via WS (per simulation and on best update).

### Storage

- Use existing optimization row + `record_optimization_iteration(...)` to persist per-simulation/iteration metrics; no schema change in v1.

### Observability

- Emit metrics: `sims_total`, `best_reward`, `avg_branching`, `nodes_expanded`, `token_spend`.
- WS events include current best reward, simulation index, and optional short trace summary.
  - Implemented: WS progress broadcasts per simulation (current and best scores; pruned events). Metrics pending.

## Non-Functional Requirements

- Token/cost control:
  - Token budget hard-cap; early stop on `early_stop_no_improve`.
  - Use cheap model for PromptQualityScorer; reserve better model for final rollouts.
- Performance:
  - Default simulations (20) complete within typical job SLAs; concurrency capped; backpressure via queue.
- Reliability:
  - Fail closed; if scorer/LLM unavailable, job aborts gracefully with error message.
- Compatibility:
  - Backwards compatible with existing API and storage.

Implemented so far:
- Input validation and safe defaults; optional WS path used only when WS endpoints are loaded (no hard dependency).

## Security & Privacy

- MVP: No arbitrary code execution.
- v2 (optional): ProgramEvaluator behind feature flag
  - Sandboxed execution (timeout, memory, no network/files); whitelist imports; capture stdout/stderr; scrub logs.
  - Never log user secrets; redact inputs in traces.
- MVP: non-executing `ProgramEvaluator` stub wired under flag - no code runs; returns heuristic reward only when enabled.
- Rate limiting:
  - Reuse existing Prompt Studio limits in endpoint deps.

## User Experience

- API flow:
  - Client submits optimization with `optimizer_type="mcts"` and strategy params.
  - Poll via GET optimization status or subscribe to WS for progress.
  - On completion, response includes `optimized_prompt_id`, metrics, and summary.
- WebSocket:
  - Broadcast simulation updates: `{optimization_id, sim_index, depth, reward, best_reward, token_spend_so_far}`.
  - Final “completed” event with summary.

## Architecture

New components (under `tldw_Server_API/app/core/Prompt_Management/prompt_studio/`):

- `MctsOptimizer`: Orchestrates tree search and reward loop; plugs into `OptimizationEngine`.
- `PromptDecomposer`: Simple LLM/heuristic splitter into 3-6 segments.
- `PromptQualityScorer`: Cheap LLM/heuristic scorer, returns 0-10 and a `score_bin`.
- `MctsTree` / `UctPolicy`: Node structs with Q, N, score_bin, prompt fragment; selection/expansion/backprop.
- `ContextualGenerator`: Uses `PromptExecutor._call_llm` directly to include “context so far”.
- `ProgramEvaluator` (v2): Optional sandboxed code runner.

Implemented so far:
- `MctsOptimizer` (MVP iterative best-of-N search, early stop, WS broadcasts)
- `PromptQualityScorer` (heuristic)
- `PromptDecomposer` (heuristic)
- `ProgramEvaluator` (non-executing stub, feature-flagged) + `TestRunner` wiring

Integration points:

- `optimization_engine.py`: add routing for `optimizer_type == "mcts"`.
- `optimization_strategies.py`: house helper classes if shared across strategies.
- `api/v1/schemas/prompt_studio_optimization.py`: schema validation for mcts params.
- `api/v1/endpoints/prompt_studio_optimization.py` (create): validation guard rails.
- `job_processor.py`: status broadcasts compatible with WS `EventBroadcaster`.

## API & Schemas

Request example (POST `/api/v1/prompt-studio/optimizations/create`):

```json
{
  "project_id": 1,
  "initial_prompt_id": 12,
  "test_case_ids": [1, 2, 3],
  "optimization_config": {
    "optimizer_type": "mcts",
    "max_iterations": 20,
    "target_metric": "accuracy",
    "strategy_params": {
      "mcts_simulations": 20,
      "mcts_max_depth": 4,
      "mcts_exploration_c": 1.4,
      "prompt_candidates_per_node": 3,
      "score_dedup_bin": 0.1,
      "feedback_enabled": true,
      "feedback_threshold": 6.0,
      "feedback_max_retries": 2,
      "token_budget": 50000,
      "early_stop_no_improve": 5
    }
  }
}
```

Validation:

- Enforce numeric ranges; ensure non-negative budgets; cap candidates per node.
 - Implemented in `/optimizations/create` strategy validation.

## Scoring & Evaluation

- MVP reward:
  - Use `TestRunner.run_single_test` aggregate score (0-1) directly for optimization decisions and final payloads.
  - Internal thresholds may use scaled values, but API responses and metrics remain 0-1. Failures (exceptions) contribute 0 unless otherwise specified.
- v2 reward (optional):
  - For test cases marked “program” (runner="python"), run `ProgramEvaluator` with its internal reward mapping; normalize to 0-1 when aggregating for optimization results.

## Metrics & Logging

- Metrics (expose via `monitoring.py`):
  - `prompt_studio.mcts.sims_total`, `prompt_studio.mcts.best_reward`, `prompt_studio.mcts.tree_nodes`, `prompt_studio.mcts.avg_branching`, `prompt_studio.mcts.tokens_spent`, `prompt_studio.mcts.duration_ms`.
  - Error counters: `prompt_studio.mcts.errors_total{error=prune_low_quality|prune_dedup|scorer_failure|evaluator_timeout}`.
- Logs:
  - Per simulation decision, reward, and improvement, throttled to avoid PII leakage.
 - Implemented: metrics collection, lifecycle + throttled WS broadcasts, per-iteration DB traces.

## Rollout Plan

- Phase 1 (MVP):
  - Implement `MctsOptimizer` with scorer and contextual generator; no code execution.
  - Endpoint validation, WS progress events, metrics, docs.
- Current status: `MctsOptimizer` MVP, heuristic scorer/decomposer, WS progress, validation and docs completed.
- Phase 2 (Optional):
  - Add `ProgramEvaluator` with secure sandbox; feature flag + config; basic code tasks.
- Current status: non-executing `ProgramEvaluator` stub and wiring added; sandbox execution pending.
- Phase 3:
  - UI polish (use existing WS payloads), docs/examples, ablation scripts.

## Acceptance Criteria

- Can create an optimization with `optimizer_type="mcts"` that:
  - Runs to completion within token budget and iterations.
  - Emits WS updates and persists per-simulation iterations via `record_optimization_iteration`.
  - Returns `optimized_prompt_id` with final metrics ≥ initial metrics on a seeded sample test set.
- Input validation rejects invalid strategy params with clear errors.
- No breaking changes to other strategies or endpoints.
- Metrics exposed without errors; logs do not include secrets.
  - Current: WS progress is live; metrics to be added.

## Test Plan

- Unit (marker: `unit`):
  - UCT selection favors higher UCT child; tie-breaking stable.
  - Score binning deduplicates siblings correctly.
  - Early stop triggers on no-improvement and budget exhaustion.
- Integration (marker: `integration`):
  - Create → run → complete MCTS optimization against 3-5 toy test cases; best_reward improves vs baseline prompt.
  - WS: receive progress and completion events.
  - Endpoint validation rejects out-of-range params.
- (Phase 2) Security:
  - ProgramEvaluator timeouts; no file/network; unsafe imports blocked.

## Risks & Mitigations

- Token overuse: enforce `token_budget`, use cheap scorer, early stop.
- Noisy scorer: smooth via averaging across 2-3 low-cost calls or use heuristics (length, variable coverage).
- Latency: cap simulations; stream partial progress; allow cancellation via existing cancel endpoint.
- Sandboxing complexity (v2): keep optional; ship MVP without code exec.

## Open Questions

- Persist full MCTS tree for UI? MVP: store compact summaries in optimization `result` and per-iteration records.
- Preferred small model for scoring (OpenAI mini vs local)? Default to configured “fast” provider; make configurable per project.
- Decomposer LLM-based vs heuristic rule-based? MVP: heuristic with optional LLM assist when budget allows.

## Dependencies

- Reuse existing infra: PromptExecutor, TestRunner, JobManager, EventBroadcaster, DB methods.
- No new external libs for MVP; (optional) sandbox may need OS-level constraints if implemented.

## Documentation

- This PRD (Docs/Design/Prompt_Studio_MCTS_Sequence_Optimization_PRD.md).
- API docs: extend Prompt Studio Optimization section with mcts strategy params and examples.
- Add examples under `Docs/Examples/PromptStudio/mcts/` (follow-up task).

## Milestones

- M1 (Week 1): Schema validation, `MctsOptimizer` skeleton, heuristic scorer/decomposer, integration with `OptimizationEngine`, docs. (Done)
- M2 (Week 2): WS streaming (Done), metrics, cost controls, integration tests. Ship MVP.
- M3 (Week 3, optional): `ProgramEvaluator` behind feature flag, sandbox, tests.
