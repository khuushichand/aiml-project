# Prompt Studio MCTS Rollout Notes

## Feature flags

- `PROMPT_STUDIO_ENABLE_MCTS`: hard enable switch for MCTS strategy.
- `PROMPT_STUDIO_ENABLE_MCTS_CANARY`: dev canary switch (used with `APP_ENV=dev` / `ENVIRONMENT=dev`).
- `PROMPT_STUDIO_MCTS_DEBUG_DECISIONS`: optional debug traces in `final_metrics.trace.debug_top_scores_by_depth`.

## Suggested rollout

1. **Dev canary**
   - Keep `PROMPT_STUDIO_ENABLE_MCTS=false`.
   - Enable canary behavior in dev/test and run the smoke suite:
     - optimization creation;
     - worker execution to completion;
     - status/history retrieval;
     - WS lifecycle + iteration events.
2. **Pre-prod validation**
   - Run controlled load with conservative params:
     - low `mcts_simulations`;
     - strict `token_budget`;
     - non-zero `ws_throttle_every`.
   - Confirm `prompt_studio.mcts.*` metrics and error labels are emitted.
3. **Production enablement**
   - Flip `PROMPT_STUDIO_ENABLE_MCTS=true` for selected environments.
   - Monitor queue depth, processing backlog, and MCTS error counters.

## Rollback

- Set `PROMPT_STUDIO_ENABLE_MCTS=false`.
- Existing optimization records and history remain queryable.
- Re-run status and history checks after rollback to confirm queue health.
