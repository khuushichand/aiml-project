# RAG Pre-Retrieval Clarification and Research Action Dedup Design

Date: 2026-02-25
Status: Approved (brainstorming phase)
Owner: RAG Pipeline (`tldw_Server_API/app/core/RAG/rag_service`)

## 1. Problem Statement

Current unified RAG behavior can ask for clarification late (after generation gating or low-confidence verification), but it does not consistently ask before retrieval on ambiguous user prompts. This causes:

1. Retrieval and generation on underspecified queries.
2. Avoidable low-confidence or weakly grounded answers.
3. Poor UX when users should have been asked a short clarifying question first.

In research mode, URL dedup exists, but repeated non-URL action/query patterns can still consume budget with limited incremental value.

## 2. Goals and Non-Goals

### Goals

1. Improve answer quality for ambiguous queries by clarifying before retrieval.
2. Improve UX by prompting clarification earlier for `enable_generation=true` requests.
3. Reduce redundant research-loop actions beyond URL-only dedup.
4. Preserve backward compatibility with existing API consumers.
5. Keep p95 latency regression for `enable_generation=true` at or below 10%.

### Non-Goals (Phase 1)

1. No breaking response schema changes.
2. No new mandatory endpoint for clarification.
3. No full graph/LangGraph rewrite of the unified pipeline.
4. No advanced conversation memory subsystem redesign.

## 3. Confirmed Product Decisions

1. Primary success priorities: answer quality and early clarification UX.
2. Clarification rollout: default-on when `enable_generation=true`.
3. Clarification response contract: `200 OK`, `generated_answer` contains clarifying question, metadata flags indicate clarification.
4. Acceptance gate: both quality metrics improve, with <=10% latency regression.

## 4. Approaches Considered

## Approach A (Selected): Inline Pre-Retrieval Clarification Gate in Unified Pipeline

Add a new clarification stage near the beginning of `unified_rag_pipeline()`. Gate retrieval when query is ambiguous and generate a clarifying question directly in `generated_answer`.

Pros:
1. Meets UX and quality goals with minimal API disruption.
2. Works in existing endpoint and schema flow.
3. Allows bounded latency via heuristic-first decision path.

Cons:
1. Adds one new decision stage and metadata semantics to maintain.

## Approach B: Query Classifier-Only Extension

Extend classifier output with clarification fields and rely on query classification path for clarification behavior.

Pros:
1. Centralized decision logic.

Cons:
1. Depends on classifier toggles and path coverage.
2. Weaker behavior when classifier is disabled or bypassed.

## Approach C: Separate Clarification Endpoint/Workflow

Introduce explicit clarify endpoint and require client orchestration.

Pros:
1. Very explicit protocol.

Cons:
1. API complexity and client integration overhead.
2. Conflicts with desired default-on generation behavior.

## 5. Selected Architecture

### 5.1 New Module

Add `tldw_Server_API/app/core/RAG/rag_service/clarification_gate.py`.

Core API:
1. `ClarificationDecision` dataclass:
   - `required: bool`
   - `question: str | None`
   - `reason: str`
   - `confidence: float`
   - `detector: Literal["heuristic", "llm", "hybrid"]`
2. `assess_query_for_clarification(...) -> ClarificationDecision`
   - Inputs: query, optional chat history, optional existing classification hints, provider/model, timeout.
   - Output: decision used for pipeline short-circuit.

### 5.2 Unified Pipeline Insertion Point

Insert clarification gate in `unified_pipeline.py` after basic query validation and before expansion/retrieval fan-out.

Trigger semantics:
1. If `enable_pre_retrieval_clarification` is `None` and `enable_generation=true`, clarification gate is active.
2. If explicit `enable_pre_retrieval_clarification` is set, use that explicit value.
3. If gate returns `required=true`, return early with clarification response contract.

### 5.3 Research Action Dedup Upgrade

Extend `research_agent.py` dedup from URL-only to action signature dedup.

Action signature examples:
1. `("web_search", normalized_query, engine, result_count)`
2. `("academic_search", normalized_query, result_count)`
3. `("discussion_search", normalized_query, sorted(platforms), max_results)`
4. `("local_db_search", normalized_query, sorted(sources), top_k)`

Behavior:
1. If exact action signature repeats and previous result count > 0, skip execution and reuse prior results.
2. Emit metadata and progress events for skipped/reused actions.

## 6. Data Flow

## 6.1 Clarification Path

1. Request enters `/api/v1/rag/search`.
2. `unified_rag_pipeline()` validates input.
3. Clarification gate runs (default-on for generation requests).
4. If clarification required:
   - `generated_answer` = clarifying question.
   - `documents` = empty.
   - metadata marks clarification + retrieval bypass reason.
   - return `UnifiedRAGResponse` (`200 OK`).
5. Otherwise continue existing pipeline path.

## 6.2 Non-Clarification Path

No semantic changes to existing retrieval, reranking, generation, claims, verification, and guardrails behavior.

## 6.3 Research Loop Dedup Path

1. Agent proposes action.
2. Action signature computed and checked.
3. If duplicate with reusable prior result, skip actual call and reuse cached results.
4. Continue loop with updated metadata.

## 7. Request/Response Contract Changes

### 7.1 Request Additions (Unified Request)

1. `enable_pre_retrieval_clarification: Optional[bool] = None`
2. `clarification_timeout_sec: Optional[float] = None`
3. `enable_research_action_dedup: bool = True` (optional; default true if accepted during implementation)

### 7.2 Response/Metadata Additions

No breaking top-level response fields.

Metadata additions when clarification is triggered:
1. `clarification.required = true`
2. `clarification.stage = "pre_retrieval"`
3. `clarification.reason = <string>`
4. `clarification.confidence = <float>`
5. `clarification.detector = <heuristic|llm|hybrid>`
6. `retrieval_bypassed.reason = "pre_retrieval_clarification"`

Research action dedup metadata:
1. `action_dedup.enabled`
2. `action_dedup.duplicates_skipped`
3. `action_dedup.reused_results_count`

## 8. Decision Logic Details

### 8.1 Heuristic-First Clarification

Use a low-cost heuristic pass first:
1. Pronoun-dependent follow-up without resolvable referent in recent history.
2. Underspecified target requests ("fix this", "improve it", "why is this broken").
3. Multi-intent queries with missing target entities.

Heuristic outcomes:
1. High-confidence ambiguous -> immediate clarification required.
2. Confidently clear -> proceed.
3. Borderline -> optional LLM clarification check.

### 8.2 LLM Clarification Check

For borderline cases only:
1. Use structured JSON output:
   - `needs_clarification`
   - `clarifying_question`
   - `confidence`
   - `reason`
2. Enforce strict timeout from `clarification_timeout_sec` (or safe default).
3. Fail-open policy: if call fails/times out, continue pipeline unless heuristic was high-confidence ambiguous.

## 9. Error Handling and Resilience

1. Clarification logic must never return non-200 by itself.
2. Clarification module failures are logged and surfaced in `result.errors` when appropriate.
3. Timeout/failure in LLM clarification path falls back to heuristic decision.
4. Research action dedup failures degrade gracefully to normal action execution.

## 10. Observability and Metrics

Add metrics:
1. `rag_clarification_triggered_total`
2. `rag_clarification_llm_timeout_total`
3. `rag_pre_retrieval_clarification_latency_ms`
4. `rag_research_action_dedup_skipped_total`
5. `rag_research_action_dedup_reused_total`

Segment existing quality metrics by clarification presence where possible:
1. unsupported ratio with `clarification_applied=true|false`
2. generation gate outcomes with clarification context

## 11. Testing Strategy

### 11.1 Unit Tests

1. New clarification gate module:
   - clear query -> no clarification
   - ambiguous query -> clarification required
   - borderline + LLM timeout -> fallback behavior
2. Unified pipeline:
   - default-on clarification when `enable_generation=true`
   - explicit opt-out via request flag
   - response metadata and retrieval short-circuit contract
3. Research agent dedup:
   - repeated action signatures skipped and prior results reused
   - non-duplicates still execute

### 11.2 Integration Tests

1. `/api/v1/rag/search` ambiguous request returns clarification question with `200`.
2. Non-ambiguous generation request remains on normal retrieval path.
3. Research-loop integration validates action dedup metadata and behavior.

### 11.3 Regression

Run affected RAG NEW and integration suites around:
1. query classification/reformulation
2. research loop
3. generation controls
4. post-verification metadata

## 12. Acceptance Criteria

All must pass:
1. Unsupported-claim ratio improves on ambiguous-query eval slice.
2. Clarification precision improves on labeled ambiguity set.
3. p95 latency regression for `enable_generation=true` is <=10%.
4. No API breaking changes for existing clients.

## 13. Rollout and Slicing

### Slice 1: Clarification Gate Scaffolding

1. Add `clarification_gate.py`.
2. Add request fields and defaults.
3. Wire minimal gate path in unified pipeline.

### Slice 2: Heuristic and LLM Decision

1. Implement heuristic ambiguity checks.
2. Implement bounded LLM clarification check.
3. Add metadata and metrics.

### Slice 3: Research Action Dedup

1. Add action signature cache in `research_agent.py`.
2. Reuse prior result sets for duplicate signatures.
3. Add dedup metrics and metadata.

### Slice 4: Validation and Tuning

1. Add/adjust tests.
2. Run quality and latency benchmark slice.
3. Tune thresholds/timeouts to keep <=10% latency cap.

## 14. Risks and Mitigations

1. Over-triggering clarification can hurt completion rate.
   - Mitigation: heuristic precision bias + conservative thresholds + labeled evaluation set.
2. Latency increase from extra LLM call.
   - Mitigation: heuristic-first path, borderline-only LLM checks, strict timeout.
3. Dedup false positives could suppress useful retrieval.
   - Mitigation: exact signature matching only in phase one and reuse only when prior results non-empty.

## 15. Implementation Handoff Notes

1. Keep all behavior behind request-level toggles/default semantics.
2. Preserve existing endpoint contracts and `UnifiedRAGResponse`.
3. Prefer minimal, composable additions over large pipeline restructuring.

