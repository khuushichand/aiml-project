## Stage 1: Profiles & Modes
**Goal**: Introduce a small set of blessed RAG profiles (e.g., production, research, cheap/fast) with well-documented defaults that map directly onto `unified_rag_pipeline` parameters without breaking existing callers.
**Success Criteria**: 
- A lightweight profile abstraction exists (e.g., `RAGProfile`) with three named profiles and clear defaults.
- Callers can opt into a profile via a simple API (e.g., helper or `profile` argument) while still being able to override individual knobs.
- Documentation describes each profile’s intent, defaults, and tradeoffs (latency, cost, safety).
- Unit tests cover profile → pipeline-args mapping and guard against regression.
**Tests**: 
- New unit tests for the profile helper module.
- Adjusted/added tests in `tests/RAG_NEW` that exercise at least one profile end-to-end.
**Status**: In Progress

## Stage 2: Eval Harness & Dataset
**Goal**: Provide a reproducible evaluation harness for the unified RAG pipeline with a known dataset and clear retrieval/factuality metrics that can be run locally or in CI.
**Success Criteria**: 
- A small, versioned eval dataset exists in-repo (or clearly documented external dataset with loader config).
- A single CLI / script path runs the eval harness against `unified_rag_pipeline` and emits retrieval and factuality metrics.
- Quality eval scheduler is wired to a real default dataset path with docs on how to customize.
- Docs briefly summarize which metrics are reported and how to interpret them.
**Tests**: 
- Unit tests for the harness configuration/runner (using a tiny synthetic dataset).
- Smoke-style test that calls the runner in a constrained mode to ensure it doesn’t regress.
**Status**: Not Started

## Stage 3: Multi-Tenant Isolation Story
**Goal**: Clarify and, where needed, tighten multi-tenant isolation across DBs, caches, exemplars, and telemetry for the RAG pipeline.
**Success Criteria**: 
- Design doc (or section in existing RAG docs) explicitly states tenant/user boundaries and trust assumptions.
- Caches and any persisted artifacts (semantic/adaptive cache, rewrite cache, exemplars) are keyed or scoped by user/namespace/tenant where appropriate, or explicitly disabled in multi-tenant profiles.
- Telemetry/metrics and tracing include tenant-safe labels and guidance on off-box export.
- Tests and/or linters guard against obvious cross-tenant leakage patterns in new code.
**Tests**: 
- Unit tests for cache keying / namespacing behavior.
- Focused tests for exemplar logging to ensure user/namespace metadata is present and redaction is applied.
**Status**: Not Started

## Stage 4: Pipeline Refactor & API Cleanups
**Goal**: Factor the ~2000-line `unified_rag_pipeline` into composable, testable steps with clearer required/optional components, enforced budgets, and a cleaner public API.
**Success Criteria**: 
- A `RAGPipelineContext` (or equivalent) internal abstraction exists and is used across phases (retrieval, expansion, caching, guardrails, reranking, generation, claims, post-verification, telemetry).
- The main entry point becomes a thin orchestrator over smaller functions or classes, without changing external behavior.
- Required vs optional modules are clearly separated; production profiles fail loudly when required components are missing, while “experimental” paths remain opt-in.
- Time/cost budgets are enforced in a centralized way, with sensible defaults per profile.
- API surface issues (e.g., `enable_streaming` semantics, duplicate helpers, return-type guarantees) are documented and at least partially addressed without breaking existing clients.
**Tests**: 
- Existing `tests/RAG_NEW` suites continue to pass.
- New unit tests for at least one extracted phase (e.g., retrieval or guardrails) to validate behavior in isolation.
**Status**: Not Started

