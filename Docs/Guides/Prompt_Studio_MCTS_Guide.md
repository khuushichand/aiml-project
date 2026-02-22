# Prompt Studio - Running MCTS (Canary)

This guide walks you through running the MCTS optimizer, controlling costs, and watching WebSocket progress.

## Enable (feature flag)

- Dev canary (default): set `APP_ENV=dev` (or `ENVIRONMENT=dev`) and keep `PROMPT_STUDIO_ENABLE_MCTS_CANARY=true`.
- Global enable: `PROMPT_STUDIO_ENABLE_MCTS=true`.

## Create an optimization

POST `/api/v1/prompt-studio/optimizations/create`

Example payload:

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
      "early_stop_no_improve": 5,
      "token_budget": 50000,
      "ws_throttle_every": 2,
      "trace_top_k": 3
    }
  },
  "name": "MCTS Sequence Optimization"
}
```

## Watch progress (WebSocket)

Connect to `/api/v1/prompt-studio/ws` and subscribe to optimization events.
You will receive:
- `optimization_started`
- `optimization_iteration` (throttled): `{optimization_id, iteration, max_iterations, current_metric, best_metric, progress, strategy, sim_index, depth, reward, best_reward, token_spend_so_far, trace_summary}`
- `optimization_completed`

Throttle interval defaults to roughly `n_sims/50` (configurable via `ws_throttle_every`).

## Reference examples

- `Docs/Examples/PromptStudio/mcts/create_optimization_mcts.json`
- `Docs/Examples/PromptStudio/mcts/websocket_optimization_iteration_event.json`
- `Docs/Examples/PromptStudio/mcts/optimization_history_response.json`
- `Docs/Examples/PromptStudio/mcts/ROLL_OUT_NOTES.md`

## Cost control tips

- Set a `token_budget` to cap spend.
- Reduce `mcts_simulations`, `mcts_max_depth`, and `prompt_candidates_per_node`.
- Use caching (built-in) and conservative defaults during development.

## Results & traces

The optimization row includes `final_metrics` with:
- `tree_nodes`, `avg_branching`, `tokens_spent`, `duration_ms`, `best_reward`, `errors`, and `applied_params`.
- A compact `trace` with `best_path` and `top_candidates`. Set `PROMPT_STUDIO_MCTS_DEBUG_DECISIONS=true` to include `debug_top_scores_by_depth`.

## Rollout notes (canary to global)

1. Keep `PROMPT_STUDIO_ENABLE_MCTS=false` in production by default.
2. Enable canary in dev/test (`APP_ENV=dev` with `PROMPT_STUDIO_ENABLE_MCTS_CANARY=true`) and validate:
   - optimization creation succeeds;
   - WS emits lifecycle + throttled iteration payloads;
   - `final_metrics.trace` persists.
3. Promote to controlled production rollout by enabling `PROMPT_STUDIO_ENABLE_MCTS=true` for selected environments.
4. Monitor:
   - `prompt_studio.mcts.*` summary metrics;
   - `prompt_studio.mcts.errors_total{error=...}` labels;
   - queue depth and job processing health from `/api/v1/prompt-studio/status`.
5. Roll back by setting `PROMPT_STUDIO_ENABLE_MCTS=false`; existing optimization records remain queryable.
