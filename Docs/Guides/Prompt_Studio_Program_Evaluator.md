# Prompt Studio - Program Evaluator (Feature Flag)

The Program Evaluator executes Python code produced by the LLM and scores outputs against objectives and constraints. It is disabled by default.

## Enable

- Global: `PROMPT_STUDIO_ENABLE_CODE_EVAL=true`
- Project-level: set project `metadata` to `{ "enable_code_eval": true }`

Project metadata takes precedence when set to a boolean; otherwise global flag controls behavior.

## Runtime configuration

- `PROMPT_STUDIO_CODE_EVAL_TIMEOUT_MS` (default: `WALL_TIME_SEC` fallback)
- `PROMPT_STUDIO_CODE_EVAL_MEM_MB` (default: `256`)
- `PROMPT_STUDIO_CODE_EVAL_IMPORT_WHITELIST` (default: `math,statistics`)

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

## Evaluator result shape

`ProgramEvaluator.evaluate(...)` returns:
- `success`
- `return_code`
- `stdout` (truncated)
- `stderr` (truncated)
- `metrics` (includes `mode`, `timeout_sec`, `memory_mb`, and failure details such as `failure_kind` when execution fails)
- `reward`
- `error` (optional)

## Usage with MCTS

- Combine with `optimizer_type="mcts"` to evaluate generated programs.
- Example in OpenAPI: `mcts_with_program_evaluator` under `/api/v1/prompt-studio/optimizations/create`.

## Caveats

- Do not enable in untrusted multi-tenant contexts.
- Limit iterations and token budgets to control cost.
- Always validate code extraction heuristics for your domain.
