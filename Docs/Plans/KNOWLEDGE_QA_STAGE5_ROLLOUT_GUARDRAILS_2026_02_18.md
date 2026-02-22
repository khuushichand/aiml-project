# Knowledge QA Stage 5 Rollout Guardrails

Date: 2026-02-18  
Plan Scope: Findings `11.1` to `11.9`

## Feature Flags

- `ff_knowledgeQaStreaming`:
  - Purpose: gate streamed generation path (`11.1`).
  - Default: `true` in current rollout.
  - Fallback behavior when disabled: use non-streaming `ragSearch`.

- `ff_knowledgeQaComparison`:
  - Purpose: gate comparison-mode UI rollout (`11.9`).
  - Default: `false` until UI and backend diffing are production-ready.

## Telemetry KPIs

- Latency perception:
  - `search_complete.duration_ms`
  - `search_complete.used_streaming`
- Completion and utility:
  - `search_complete.result_count`
  - `search_complete.has_answer`
  - `workspace_handoff.source_count`
- Quality loop engagement:
  - `answer_feedback_submit.helpful`
  - `source_feedback_submit.relevant`
- Query ideation adoption:
  - `suggestion_accept.source`

## Milestones

1. MVP (active now)
- Streaming available behind `ff_knowledgeQaStreaming`.
- Local query suggestions prototype in SearchBar.
- Workspace handoff with seeded sources and note context.
- Comparison mode contract/data model established, UI gated.

2. Follow-on (next increment)
- Remote suggestion API (`phase_2_remote_personalized`).
- Comparison mode pairing UI (`phase_1_manual_pairing`) behind `ff_knowledgeQaComparison`.
- Expanded quality diagnostics and per-turn comparison artifacts.

3. Scale-up (after validation)
- Semantic cross-document suggestions.
- Comparison diff summaries and structured verdict generation.
- Promotion of comparison flag to default-on after KPI guardrails pass.
