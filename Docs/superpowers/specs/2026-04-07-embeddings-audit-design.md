# Embeddings Module Correctness Audit Design

- Date: 2026-04-07
- Project: tldw_server
- Topic: Embeddings module review for issues, bugs, and potential problems/improvements
- Review mode: Findings only (no implementation in this phase)

## 1. Objective

Run a correctness-first audit of the Embeddings module to identify real defect risks, integrity failures, and latent bugs in embedding generation/storage/query paths.

This design intentionally excludes implementation changes. The deliverable is a prioritized findings report with evidence.

## 2. Scope

### In Scope

- Core embeddings orchestration and execution paths:
  - `tldw_Server_API/app/core/Embeddings/async_embeddings.py`
  - `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py`
  - Supporting Embeddings modules directly involved in request handling, batching, policy, cache, and persistence interactions.
- API surfaces for embeddings and media embeddings:
  - `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
  - `tldw_Server_API/app/api/v1/endpoints/media_embeddings.py`
  - Related embedding schemas in `app/api/v1/schemas/`.
- LLM embeddings adapter integration and contract behavior:
  - `tldw_Server_API/app/core/LLM_Calls/embeddings_adapter_registry.py`
  - `tldw_Server_API/app/core/LLM_Calls/providers/openai_embeddings_adapter.py`
  - `tldw_Server_API/app/core/LLM_Calls/providers/google_embeddings_adapter.py`
  - `tldw_Server_API/app/core/LLM_Calls/providers/huggingface_embeddings_adapter.py`
- Critical tests that validate correctness invariants.

### Out of Scope

- Embeddings ABTest/Evaluations subsystem and related evaluation workflow files.
- Unrelated refactors, style-only cleanup, and speculative architecture redesign.

## 3. Audit Architecture

The audit executes four correctness-focused passes:

1. Contract pass
- Trace endpoint -> core -> adapter contracts.
- Validate assumptions for input shape, model selection, dimensions, ordering, nullability, and normalization.
- Detect interface mismatches and silent coercions.

2. State and data pass
- Inspect write/read paths for embeddings and metadata coupling.
- Verify idempotency, consistency of vector dimensions, ordering stability, and storage semantics.
- Identify corruption/drift opportunities under retries and partial completion.

3. Failure-path pass
- Trace exceptions, fallback behavior, retry logic, cancellation/timeout handling, and partial-failure semantics.
- Identify cases where bad state can be accepted, masked, or persisted.

4. Evidence pass
- Convert suspected issues into evidence-backed findings with exact file/line references.
- Rank severity by user impact and data-integrity risk.

## 4. Verification Strategy

To reduce false positives and over-claiming:

- Use static trace validation across endpoint -> core -> adapter -> persistence boundaries.
- Use targeted test runs only where needed to validate/refute suspected invariant violations.
- Use minimal runtime spot checks for disputed behavior.
- If certainty is limited, record as an open question instead of asserting defect.

## 5. Output Format

The review report will be findings-first and ordered by severity:

1. Critical
2. High
3. Medium
4. Low

Each finding will include:

- Issue statement and integrity impact.
- Exact file and line reference.
- Trigger/failure scenario.
- Expected vs actual behavior.
- Confidence level and assumptions.

The report will also include:

- Open questions that block certainty.
- Residual risks/testing gaps if no direct defect is proven.

## 6. Non-Goals and Constraints

- No code implementation in this phase.
- No patch plan in this phase.
- No broadening into unrelated modules.
- Focus remains correctness/data integrity first; other risk classes are secondary unless they directly affect integrity.

## 7. Success Criteria

The design is successful when:

- Review scope remains aligned to requested boundaries.
- Findings are evidence-backed and reproducible at the code-path level.
- Report is actionable without requiring additional interpretation.
- No implementation action is taken before explicit user request.
