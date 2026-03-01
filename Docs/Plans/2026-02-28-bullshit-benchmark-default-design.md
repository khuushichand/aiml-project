# Bullshit Benchmark Default Inclusion Design (tldw_server)

Date: 2026-02-28
Status: Approved
Owner: Evals subsystem

## 1. Objective

Add `bullshit_benchmark` as a built-in benchmark in `tldw_server` so users can run it without installing extra tooling or cloning external repos. It must be surfaced by default across:

- Unified CLI (`tldw-evals`)
- Unified evaluation API
- Evals UI benchmark selection

## 2. Decisions Captured During Brainstorming

1. Inclusion mode: auto-registered built-in benchmark by default.
2. Dataset packaging: pinned local snapshot in repo (no runtime fetch dependency).
3. Product surface: CLI + unified API + UI.

## 3. Non-Goals

- No runtime sync/refresh from upstream `bullshit-benchmark` repo in this phase.
- No reimplementation of upstream OpenRouter multi-judge orchestration in this phase.
- No changes to unrelated evaluation types.

## 4. Current-State Findings (Relevant)

- `tldw_server2` already has benchmark primitives:
  - Registry: `tldw_Server_API/app/core/Evaluations/benchmark_registry.py`
  - Loaders: `tldw_Server_API/app/core/Evaluations/benchmark_loaders.py`
  - Benchmark CLI module: `tldw_Server_API/app/core/Evaluations/cli/benchmark_cli.py`
- Unified CLI entrypoint is `tldw_Server_API/cli/evals_cli.py` (`tldw-evals`).
- Docs reference benchmark commands under `tldw-evals`, but benchmark command wiring is currently not part of unified CLI command groups.
- Existing benchmark infrastructure supports local-file datasets and evaluator creation.

## 5. Approaches Considered

### Approach A: Native built-in benchmark (recommended)

- Package benchmark data locally in repo.
- Register `bullshit_benchmark` in default benchmark registry.
- Add loader normalization for benchmark JSON structure.
- Expose benchmark list/run via unified CLI + API + UI.

Pros:
- Zero extra tooling for users.
- Aligns with existing architecture.
- Lower operational risk than external runtime dependencies.

Cons:
- Requires explicit API/UI surface wiring work.

### Approach B: Vendor upstream runner script behavior

- Embed/adapt upstream `openrouter_benchmark.py` flow directly.

Pros:
- Closer to upstream behavior.

Cons:
- Heavy coupling to upstream assumptions and judge orchestration.
- Larger maintenance and compatibility burden.

### Approach C: Thin adapter only

- Transform questions into internal format and rely on generic custom metric scoring.

Pros:
- Fast initial integration.

Cons:
- Potentially weaker benchmark fidelity and interpretability.

Recommendation: Approach A.

## 6. Target Architecture

### 6.1 Data packaging

- Add pinned dataset snapshot under:
  - `tldw_Server_API/app/core/Evaluations/data/bullshit_benchmark/questions_v2.json`
- Keep required runtime fields:
  - `id`, `question`, `nonsensical_element`, `technique`, `domain`.
- Exclude control-question execution for the default benchmark run path (aligning to current v2 dataset behavior).

### 6.2 Benchmark registry

- Add default registry entry `bullshit_benchmark` in `BenchmarkRegistry._load_default_benchmarks()`.
- Use local dataset source path, local format, and explicit metadata (version, source snapshot date).
- Ensure it appears in benchmark listing automatically.

### 6.3 Loader normalization

- Add `BenchmarkDatasetLoader.load_bullshit_benchmark(...)`.
- Flatten source format (`techniques[] -> questions[]`) into row-wise samples.
- Deterministic order and `limit` support.
- Fail fast with clear errors for missing asset or schema mismatch.

### 6.4 Evaluation semantics

- Initial integration uses existing benchmark evaluator path with a benchmark-specific prompt rubric focused on nonsense-recognition behavior.
- Output remains compatible with existing run summary structures.
- Scoring normalization remains in current framework bounds for consistency.

### 6.5 Unified CLI integration

- Ensure benchmark commands are exposed in unified `tldw-evals` command tree (not only legacy/deprecated paths).
- Baseline UX:
  - `tldw-evals benchmark list`
  - `tldw-evals benchmark info bullshit_benchmark`
  - `tldw-evals benchmark run bullshit_benchmark --limit <N>`
- Optionally add compatibility aliases if legacy docs/usage require them.

### 6.6 Unified API integration

- Add benchmark list/info/run endpoints under evaluations routes.
- Internally use shared registry/loader/evaluator flow used by CLI to avoid logic drift.
- Return standardized run metadata, per-item result details, and summary metrics.

### 6.7 UI integration

- Evals UI retrieves built-in benchmark list from API.
- `bullshit_benchmark` appears as default built-in option with concise description.
- Run workflow uses existing eval result rendering path.

## 7. Error Handling

- Missing packaged file: deterministic 5xx/CLI error with asset path.
- Invalid schema/content: validation error with field-level reason.
- Missing provider/model config: actionable configuration error (not install/tooling error).
- Partial per-item failures: preserve per-item errors; continue unless fail-fast is enabled.
- API/CLI/UI should surface normalized error payloads/messages.

## 8. Testing Strategy

### Unit tests

- Loader flattening and schema validation for `questions_v2.json`.
- Registry auto-registration of `bullshit_benchmark`.
- CLI command wiring in unified entrypoint.

### Integration tests

- CLI list includes `bullshit_benchmark`.
- CLI run with mocked provider succeeds for bounded sample count.
- API benchmark list/info/run endpoint behavior.

### UI tests

- Benchmark appears in selector by default.
- Run initiation and result summary render path works.

### Regression tests

- Existing benchmarks remain discoverable/runnable.
- Existing eval endpoints and command groups unaffected.
- Documentation examples map to real command paths.

## 9. Rollout Notes

- Phase 1: local snapshot + registry + loader + unified CLI exposure.
- Phase 2: unified API endpoints.
- Phase 3: UI surfacing and UX polish.

## 10. Risks and Mitigations

- Risk: CLI/docs mismatch persists.
  - Mitigation: add explicit unified CLI benchmark command tests.
- Risk: Dataset drift from upstream benchmark.
  - Mitigation: include snapshot metadata and follow-up refresh process doc.
- Risk: Scoring interpretation ambiguity.
  - Mitigation: publish benchmark-specific score interpretation in docs/UI help text.

## 11. Acceptance Criteria

- User can run `bullshit_benchmark` in `tldw_server` with existing installation and configured provider, without extra benchmark tooling.
- Benchmark is discoverable in CLI, API, and UI default benchmark listings.
- Benchmark run returns structured results and summary in existing evaluation result style.
- Tests covering registry/loader/CLI/API/UI paths pass for added behavior.
