# Prompt Studio - Ablation Scripts

Compare optimization strategies (iterative vs mcts vs genetic) on a shared test set.

## Setup

1. Seed a project, prompt, and golden test set.
2. Ensure provider keys are configured.
3. For MCTS canary, enable in dev or set `PROMPT_STUDIO_ENABLE_MCTS=true`.

## Example payloads

Iterative:
```json
{
  "project_id": 1,
  "initial_prompt_id": 12,
  "test_case_ids": [1,2,3],
  "optimization_config": {
    "optimizer_type": "iterative",
    "max_iterations": 10,
    "target_metric": "accuracy"
  },
  "name": "Iterative"
}
```

Genetic:
```json
{
  "project_id": 1,
  "initial_prompt_id": 12,
  "test_case_ids": [1,2,3],
  "optimization_config": {
    "optimizer_type": "genetic",
    "max_iterations": 10,
    "target_metric": "accuracy",
    "strategy_params": {
      "population_size": 8,
      "mutation_rate": 0.1
    }
  },
  "name": "Genetic"
}
```

MCTS (canary): see `Docs/Guides/Prompt_Studio_MCTS_Guide.md`.

## Metrics to collect

- Final score, improvement
- Iterations completed
- tokens_spent, duration_ms
- For MCTS: tree_nodes, avg_branching, best_reward, errors, applied_params

## Tips

- Use the same `test_case_ids` for comparability.
- Keep iterations small in dev; increase for final runs.
- Use `ws_throttle_every` to avoid flooding WS.
