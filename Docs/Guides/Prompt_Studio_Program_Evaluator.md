# Prompt Studio - Program Evaluator (Feature Flag)

The Program Evaluator executes Python code produced by the LLM and scores outputs against objectives and constraints. It is disabled by default.

## Enable

- Global: `PROMPT_STUDIO_ENABLE_CODE_EVAL=true`
- Project-level: set project `metadata` to `{ "enable_code_eval": true }`

Both must pass; if either disables, the evaluator falls back to a heuristic text-based reward.

## Runner specification

- Mark test cases intended for execution with `runner="python"`.
- Provide inputs and expected outputs appropriate for evaluation.
- The evaluator extracts Python code from fenced blocks (```python ... ```), or falls back to heuristics if necessary.

## Safety and sandbox

- Sandboxed execution via a separate Python subprocess with:
  - No filesystem or network access
  - Import whitelist
  - CPU and memory limits (best-effort via POSIX RLIMIT)
- On non-POSIX platforms, resource limits are best-effort; treat as advisory.

## Scoring

- Success: code runs, constraints satisfied → reward in [0..10]
- Failure: syntax/runtime error → -1
- Partial: runs but fails some checks → 0..5 depending on objective proximity

## Usage with MCTS

- Combine with `optimizer_type="mcts"` to evaluate generated programs.
- Example in OpenAPI: `mcts_with_program_evaluator` under `/api/v1/prompt-studio/optimizations/create`.

## Caveats

- Do not enable in untrusted multi-tenant contexts.
- Limit iterations and token budgets to control cost.
- Always validate code extraction heuristics for your domain.
