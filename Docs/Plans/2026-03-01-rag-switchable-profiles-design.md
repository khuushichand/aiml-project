# RAG Switchable Profiles Design (Paper-Informed)

Date: 2026-03-01  
Status: Approved for planning  
Owner: RAG module (tldw_server)

## 1. Problem Statement

We reviewed paper `2602.13890v1` ("Evaluating Prompt Engineering Techniques for RAG in Small Language Models: A Multi-Hop QA Approach") and need to transfer practical improvements into `tldw_server`'s unified RAG module.

The module currently supports many retrieval/generation knobs, but there is no first-class runtime profile abstraction that coordinates those knobs for latency vs quality goals.

## 2. Key Takeaways from the Paper

1. Prompt strategy materially affects RAG answer quality for small models.
2. Better reasoning prompts often incur substantial latency cost (reported 8-10x in that setup).
3. Prompt effectiveness is model-specific; no universal best prompt.
4. Multi-hop decomposition and synthesis patterns are consistently useful for complex QA.
5. For stronger small models, high-level "expert synthesis" prompts can outperform verbose step-by-step prompting.
6. Efficient instruction-style prompts remain best for latency-critical deployments.

## 3. Goals and Non-Goals

### Goals

1. Add a switchable runtime profile mechanism: `fast`, `balanced`, `accuracy`.
2. Make profile behavior deterministic and traceable in response metadata.
3. Preserve existing explicit request parameter precedence.
4. Add profile-oriented prompt templates and policy defaults aligned with paper findings.
5. Raise `max_generation_tokens` schema cap to `4000` to support approved profile budgets.

### Non-Goals

1. Full automatic profile selection in v1 (no hard auto mode yet).
2. Re-architecting retrieval/reranking internals.
3. Replacing current evaluation framework wholesale.

## 4. Proposed Architecture

Introduce a profile policy layer in unified pipeline request handling:

1. Parse optional `rag_profile` from request schema.
2. Build a profile defaults map.
3. Apply defaults only for fields not explicitly set by caller.
4. Continue current unified pipeline flow unchanged.
5. Emit profile resolution details in metadata and observability attributes.

This is additive and backward compatible for existing clients.

## 5. Profile Behavior Matrix

The following defaults are applied when `rag_profile` is provided and corresponding request fields are omitted.

### fast (latency-first)

- `generation_prompt`: `instruction_tuned`
- `enable_query_decomposition`: `false`
- `enable_reranking`: `true`
- `reranking_strategy`: `flashrank`
- `top_k`: `6`
- `max_generation_tokens`: `440`
- `enable_structured_response`: `false`
- `enable_multi_turn_synthesis`: `false`
- `require_hard_citations`: `false`
- `enable_claims`: `false`

### balanced (quality/latency tradeoff)

- `generation_prompt`: `multi_hop_compact`
- `enable_query_decomposition`: `true`
- `max_subqueries`: `3`
- `subquery_time_budget_sec`: `2.5`
- `enable_reranking`: `true`
- `reranking_strategy`: `hybrid`
- `top_k`: `10`
- `max_generation_tokens`: `1000`
- `enable_structured_response`: `true`
- `require_hard_citations`: `false`
- `enable_claims`: `false`

### accuracy (quality-first)

- `generation_prompt`: `expert_synthesis`
- `enable_query_decomposition`: `true`
- `max_subqueries`: `5`
- `subquery_time_budget_sec`: `6.0`
- `enable_reranking`: `true`
- `reranking_strategy`: `two_tier`
- `top_k`: `16`
- `rerank_top_k`: `16`
- `max_generation_tokens`: `2200`
- `enable_structured_response`: `true`
- `require_hard_citations`: `true`
- `enable_numeric_fidelity`: `true`
- `enable_claims`: `true` (may be tuned off by ops in strict latency environments)

## 6. Prompt Strategy Mapping

Add/maintain RAG prompt entries in prompt assets so they can be selected by profile:

1. `instruction_tuned` (concise, direct, context-only)
2. `multi_hop_compact` (compact decomposition + synthesis + citations)
3. `expert_synthesis` (high-level synthesis, contradiction handling, citation discipline)

These names map to paper-supported patterns and should be loaded via existing prompt loader mechanisms.

## 7. Data Flow and Precedence

Pipeline order:

1. Request parse and validation.
2. Resolve profile defaults.
3. Merge with request where explicit request values override profile defaults.
4. Execute retrieval/decomposition/reranking/generation path with effective config.
5. Attach `profile_resolution` metadata.

Precedence rule (strict):
`explicit request field > profile default > existing hardcoded/schema default`.

## 8. Schema and API Changes

### Schema

In `rag_schemas_unified.py`:

1. Add `rag_profile: Literal["fast", "balanced", "accuracy"] | None`.
2. Raise `max_generation_tokens` upper bound from `2000` to `4000`.

### API behavior

No endpoint path changes. Existing payloads remain valid.

### UI typing/defaults

In frontend RAG settings type:

1. Add `rag_profile` field and preset controls.
2. Keep advanced per-knob overrides available.

## 9. Error Handling and Degradation

1. Unknown `rag_profile` -> schema validation error (`422`).
2. Missing configured prompt template -> fallback to default prompt and emit warning in `result.errors`.
3. Feature dependency unavailable (for example `two_tier`) -> degrade to `hybrid` and record degradation in metadata.
4. Safety: if runtime value exceeds allowed cap (regression), clamp and warn.

## 10. Observability

Add profile observability fields:

1. Span attributes: `rag.profile.requested`, `rag.profile.applied`.
2. Response metadata block:
   - `requested_profile`
   - `applied_profile`
   - `effective_overrides_count`
   - `degraded_features`

## 11. Test and Validation Plan

### Unit tests

1. Schema validation for `rag_profile` and new token cap `<= 4000`.
2. Resolver precedence tests.
3. Degradation tests (missing prompt, unavailable `two_tier`).

### Integration tests

1. Compare baseline vs each profile on fixed query fixtures.
2. Validate metadata profile resolution and response shape.
3. Validate streaming parity where generation prompt/profile is used.

### Evaluation harness

Run a paper-inspired ablation over fixed dataset slices:

1. Quality metric (existing eval route / judge flow).
2. Latency metrics (p50/p95).
3. Efficiency metric (`quality / latency`).
4. Citation/hard-citation coverage for quality profile.

Success criteria:

1. `fast` materially improves latency vs no-profile baseline.
2. `accuracy` materially improves quality vs no-profile baseline.
3. `balanced` remains stable between the two.
4. No regression in grounding/verification indicators.

## 12. Risks and Mitigations

1. Prompt coupling risk: guard with prompt fallback and explicit metadata.
2. Latency inflation in `accuracy`: communicate profile intent and expose overrides.
3. Model-specific variance: keep profiles configurable and iterate with evals.

## 13. Rollout Strategy

1. Land behind additive request field with default `None` behavior.
2. Start with internal testing and profile eval report.
3. Expose in UI presets after backend validation.
4. Tune defaults using metrics and eval outcomes.

## 14. Implementation Direction (Next Step)

Use `writing-plans` to produce a staged implementation plan covering:

1. Schema/API updates.
2. Unified pipeline profile resolver.
3. Prompt asset additions.
4. Frontend settings wiring.
5. Test and validation execution.

