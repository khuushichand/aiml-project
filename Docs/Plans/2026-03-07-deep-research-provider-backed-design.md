# Deep Research Provider-Backed Collection And Synthesis Design

## Summary

This slice replaces the deterministic collection and synthesis stubs in the deep research backend with real provider-backed integrations while preserving the existing session lifecycle, artifact model, checkpoint flow, and read APIs.

The design keeps deep research as a Jobs-driven backend pipeline. The public run APIs remain stable. The change is internal: `ResearchBroker` and `ResearchSynthesizer` stop inventing placeholder evidence and instead consume a thin adapter layer that wraps the repo's existing local retrieval, web search, academic search, and chat/LLM capabilities.

## Goals

- Use real provider-backed collection for local corpus, web search, and academic search.
- Use real provider-backed synthesis through the existing chat/LLM layer.
- Preserve `TEST_MODE` and deterministic fallback behavior for tests and degraded environments.
- Support server defaults with optional per-run provider overrides.
- Keep artifact outputs inspectable and reproducible.

## Non-Goals

- No new UI work in this slice.
- No streaming/progress transport changes.
- No broad expansion to every existing academic provider in v1.
- No internal HTTP self-calls from research Jobs to existing endpoints.

## Recommended Approach

Add a thin provider adapter layer under `tldw_Server_API/app/core/Research/providers/` and keep orchestration in the current research core.

This is preferred over direct wiring in `broker.py` and `synthesizer.py` because it keeps provider-specific logic isolated and testable, while avoiding coupling the research backend to HTTP endpoint contracts.

## Architecture

### Provider Package

Add a small provider package:

- `providers/config.py`
  - resolves server defaults
  - validates and clamps per-run overrides
  - produces a resolved effective provider config
- `providers/local.py`
  - wraps `MultiDatabaseRetriever`
- `providers/web.py`
  - wraps existing web search orchestration from core web search code
- `providers/academic.py`
  - wraps academic provider functions for arXiv, PubMed, and Crossref-backed metadata lookups
- `providers/synthesis.py`
  - wraps `perform_chat_api_call_async`

### Existing Research Core Changes

- `broker.py`
  - consume provider adapters instead of deterministic lane functions
  - preserve source-policy routing and normalization responsibilities
- `synthesizer.py`
  - keep deterministic synthesis as a fallback mode
  - add LLM-backed synthesis using bounded evidence packets and structured outputs
- `jobs.py`
  - construct configured provider-backed broker and synthesizer instances for phase execution
- `service.py`
  - accept optional per-run provider overrides
  - persist resolved config through artifacts
- `research_runs_schemas.py`
  - extend run creation input to allow bounded override payloads

## Provider Configuration Model

### Default Strategy

Use a hybrid configuration contract:

- server defaults provide the normal web, academic, local, and synthesis settings
- advanced callers may override a bounded subset per run

This keeps v1 usable without forcing every caller to understand provider configuration while still supporting reuse from chat, workflows, or Prompt Studio later.

### Per-Run Override Shape

Allow a bounded override payload on run creation with these buckets:

- `local`
  - `top_k`
  - `sources`
- `web`
  - `engine`
  - `result_count`
  - selected allowlisted web search parameters already supported by the core search stack
- `academic`
  - `providers`
  - `max_results`
- `synthesis`
  - `provider`
  - `model`
  - `temperature`

### Guardrails

- allowlist override keys explicitly
- clamp counts and limits in the research layer
- do not pass arbitrary caller config through to lower-level providers
- preserve test-mode behavior without requiring live provider configuration

### Reproducibility

Persist:

- raw caller overrides in the session record or request payload handling path
- resolved effective config as a `provider_config.json` artifact during planning

That makes runs auditable and reproducible even if server defaults later change.

## Collection Design

### Local Collection

Use `MultiDatabaseRetriever` directly rather than the HTTP RAG endpoint.

For each focus area, issue a bounded hybrid retrieval and normalize returned documents into:

- `ResearchSourceRecord`
- `ResearchEvidenceNote`

The local provider remains responsible for retrieval only. `ResearchBroker` still owns deduping, lane accounting, and gap reporting.

### Web Collection

Use the existing core web search orchestration rather than reimplementing a separate web search path.

For v1:

- one query per focus area
- no broad subquery expansion by default
- no aggregation pass during collection
- normalize top web results into source records using title, URL, snippet, provider, and retrieval metadata

### Academic Collection

Start with a narrow provider set:

- arXiv
- PubMed
- Crossref-backed metadata lookups and title/DOI support where practical

This covers a useful research baseline without dragging every paper provider into the first provider-backed slice.

### Source Policy Behavior

Preserve current policy semantics:

- `local_only`
- `external_only`
- `balanced`
- `local_first`
- `external_first`

`local_first` and `external_first` should influence lane ordering and whether fallback lanes run based on observed coverage, but the policy model itself does not change.

### Failure Model

Lane failures should degrade the run instead of terminating it immediately.

- record lane failures and missing coverage in `collection_summary.json`
- continue if at least one enabled lane produced usable sources
- fail the phase only when every enabled lane fails and zero sources are collected

## Synthesis Design

### Dual Synthesis Modes

Keep two synthesis paths:

- `deterministic`
  - existing logic remains available for tests, fallback, and recovery
- `llm_backed`
  - uses real provider/model selection through the existing chat service

### LLM-Backed Synthesis Flow

Build a bounded evidence packet from:

- `plan.json`
- `approved_plan.json` when present
- `source_registry.json`
- `evidence_notes.jsonl`
- `collection_summary.json`

Send that packet to the synthesis provider through `perform_chat_api_call_async` and require structured JSON output for:

- outline sections
- synthesized claims
- report section text
- unresolved questions
- synthesis summary

### Validation Rules

The research layer must validate the model output:

- every claim must reference at least one existing `source_id`
- unknown source references are rejected
- malformed structured output triggers fallback

If validation or parsing fails, the system should:

- fall back to deterministic synthesis
- record the fallback reason in `synthesis_summary.json`

## Errors And Observability

### Collection

- lane-level errors are recorded as collection metadata
- collection only hard-fails when no usable evidence exists

### Synthesis

- provider failure, parse failure, or invalid citations fall back to deterministic synthesis
- only hard-fail when there is no usable evidence or artifacts are inconsistent

### Artifact Additions

Add `provider_config.json` as a first-class artifact to capture resolved execution settings.

This artifact supports:

- reproducibility
- debugging
- future audit/explainability needs

## Testing Strategy

### Unit Tests

- provider config resolution and override validation
- local/web/academic provider adapters with mocked dependencies
- synthesis adapter behavior and structured-output parsing
- broker routing across source policies with mocked providers
- synthesizer fallback behavior for malformed or invalid LLM output

### Integration And Job Tests

- collecting phase with provider stubs
- synthesizing phase with synthesis provider stub
- degraded lane behavior where one lane fails and the run still advances
- failure behavior where all enabled lanes fail and the phase stops correctly

### End-To-End

Add one hybrid deep research run test that exercises:

- local retrieval adapter
- web adapter in test mode
- academic adapter in test mode
- synthesis provider stub or deterministic fallback

Real network tests are out of scope for this slice. The goal is integration correctness and robust fallback behavior, not upstream provider availability.

## Acceptance Criteria

- deep research collecting uses real local/web/academic adapters instead of deterministic placeholders
- deep research synthesizing can use a real provider/model through the chat service
- deterministic fallback remains available and covered by tests
- resolved provider configuration is persisted in artifacts
- run creation supports bounded provider overrides
- targeted research tests, broader regression tests, and Bandit pass on touched production scope
