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
- `optimization_iteration` (throttled): `{optimization_id, iteration, max_iterations, current_metric, best_metric, progress}`
- `optimization_completed`

Throttle interval defaults to roughly `n_sims/50` (configurable via `ws_throttle_every`).

## Cost control tips

- Set a `token_budget` to cap spend.
- Reduce `mcts_simulations`, `mcts_max_depth`, and `prompt_candidates_per_node`.
- Use caching (built-in) and conservative defaults during development.

## Results & traces

The optimization row includes `final_metrics` with:
- `tree_nodes`, `avg_branching`, `tokens_spent`, `duration_ms`, `best_reward`, `errors`, and `applied_params`.
- A compact `trace` with `best_path` and `top_candidates`. Set `PROMPT_STUDIO_MCTS_DEBUG_DECISIONS=true` to include `debug_top_scores_by_depth`.
