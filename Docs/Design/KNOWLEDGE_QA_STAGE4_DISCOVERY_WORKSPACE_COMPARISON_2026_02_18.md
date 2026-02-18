# Knowledge QA Stage 4 Design: Suggestions, Workspace Handoff, Comparison Contract

Date: 2026-02-18  
Scope: Findings `11.4`, `11.8`, `11.9`

## 1. Query Suggestions (Typeahead) Contract

### Stage 4 implementation (now)
- Local prototype in the SearchBar using:
  - prior Knowledge QA history queries,
  - source titles from current retrieval context,
  - curated example prompts.
- Deterministic scoring and deduplication with bounded list size.
- Keyboard and click selection support.

### Remote API contract (next phase)
- Request:
```json
{
  "query": "compare conclusions",
  "limit": 5,
  "thread_id": "optional-thread-id",
  "include_history": true,
  "include_source_titles": true
}
```
- Response:
```json
{
  "suggestions": [
    {
      "text": "Compare conclusions across my PDFs",
      "source": "history",
      "score": 0.93,
      "reason": "Similar to previous accepted query"
    }
  ],
  "model_version": "suggestions-v1",
  "generated_at": "2026-02-18T00:00:00.000Z"
}
```

### Rollout phases
1. `phase_1_local_history_examples`
2. `phase_2_remote_personalized`
3. `phase_3_semantic_cross_document`

## 2. Open in Workspace Handoff

### Goal
Move a Knowledge QA thread into Workspace Playground without forcing manual copy/paste.

### Handoff payload
- Includes:
  - thread id,
  - query,
  - answer,
  - citation indices,
  - normalized source records (media id when resolvable, title, source type, url/page metadata).
- Stored as one-shot local prefill payload and consumed on Workspace load.

### Workspace seed behavior
- Add resolvable media sources to the workspace source list.
- Select imported sources for immediate chat/studio use.
- Append a note draft containing question, answer, and source summary.

## 3. Comparison Mode Data Model (Contract Only in Stage 4)

### Draft model
- `KnowledgeQaComparisonDraft`:
  - `left` and `right` query references,
  - optional thread/message ids,
  - optional answers,
  - citation index arrays,
  - `status: draft | ready`.

### Status rule
- `ready` only when both left and right queries are non-empty.

### Rollout phases
1. `phase_1_manual_pairing`
2. `phase_2_shared_source_overlap`
3. `phase_3_diff_and_verdicts`
