# Deep Research Synthesizing Slice Design

## Overview

This slice adds deterministic synthesis to the deep research pipeline. It converts approved planning inputs plus collecting artifacts into reusable synthesis artifacts without invoking packaging or external LLM providers.

The synthesizing slice is intentionally bounded:

- read planning and collecting artifacts
- generate deterministic outline, claims, report, and synthesis summary artifacts
- enforce source-backed claim generation
- support checkpointed and autonomous run modes
- stop before final package assembly

## Goals

- Produce internal synthesis artifacts from collected evidence, not from raw search results.
- Keep the execution contract testable and deterministic.
- Preserve provenance so later packaging and export work can reuse the same artifacts.
- Advance checkpointed runs to an `outline_review` checkpoint and autonomous runs to `packaging`.

## Non-Goals

- No automatic `bundle.json` creation in the worker path.
- No export generation from the synthesizing job.
- No live LLM/provider calls in this slice.
- No packaging job execution.

## Architecture

Add `ResearchSynthesizer` under `tldw_Server_API/app/core/Research/`. The synthesizer reads:

- `approved_plan.json` or `plan.json`
- `source_registry.json`
- `evidence_notes.jsonl`
- `collection_summary.json`

It returns a deterministic synthesis result containing:

- `outline`
- `claims`
- `report_markdown`
- `synthesis_summary`

`handle_research_phase_job(...)` in `tldw_Server_API/app/core/Research/jobs.py` gains a `synthesizing` branch that:

1. loads the effective plan and collecting artifacts
2. calls `ResearchSynthesizer`
3. writes synthesis artifacts through `ResearchArtifactStore`
4. transitions the session to `awaiting_outline_review` for checkpointed runs, or `packaging` for autonomous runs

`ResearchService.approve_checkpoint(...)` keeps explicit checkpoint-to-phase mapping:

- `plan_review -> collecting` and enqueue the next job
- `sources_review -> synthesizing` without enqueue for now
- `outline_review -> packaging` without enqueue for now

## Artifact Contract

### `outline_v1.json`

```json
{
  "query": "string",
  "sections": [
    {
      "title": "string",
      "focus_area": "string",
      "source_ids": ["src_1"],
      "note_ids": ["note_1"]
    }
  ],
  "unresolved_questions": ["string"]
}
```

### `claims.json`

```json
{
  "claims": [
    {
      "claim_id": "clm_1",
      "text": "string",
      "focus_area": "string",
      "source_ids": ["src_1"],
      "citations": [{"source_id": "src_1"}],
      "confidence": 0.7
    }
  ]
}
```

### `report_v1.md`

Deterministic markdown with one section per focus area. Each section cites the source IDs it was synthesized from.

### `synthesis_summary.json`

```json
{
  "query": "string",
  "focus_areas": ["string"],
  "section_count": 1,
  "claim_count": 1,
  "source_count": 1,
  "unresolved_questions": ["string"],
  "coverage": {
    "covered_focus_areas": ["string"],
    "missing_focus_areas": []
  }
}
```

## Synthesis Rules

The v1 synthesizer is rule-based:

- group evidence notes by `focus_area`
- create one outline section per focus area with supporting source and note IDs
- emit claims only when at least one source ID is available
- build report sections from note text and source references
- carry unresolved questions forward from collection gaps and any focus area with no evidence notes

This design intentionally optimizes for predictability and citation discipline over prose quality. A later slice can add optional LLM polishing without changing the Jobs or artifact interfaces.

## State Transitions

- `synthesizing -> awaiting_outline_review` for checkpointed runs
- `synthesizing -> packaging` for autonomous runs
- `outline_review` approval updates the session to `packaging`

No packaging job is enqueued in this slice.

## Error Handling

- missing required plan or collecting artifacts raises a phase error
- malformed JSON/JSONL artifacts raise a phase error rather than silently degrading
- unsupported claims are omitted instead of being emitted without citations
- empty synthesis is allowed, but unresolved questions must reflect the gap

## Testing

Add or extend:

- synthesizer unit tests for grouping, citations, and unresolved-question propagation
- Jobs worker tests for checkpointed and autonomous `synthesizing` execution
- service tests for `outline_review -> packaging`
- e2e run lifecycle test through `awaiting_outline_review`

## Follow-On Work

The next slice after synthesis should implement packaging execution:

- convert synthesis artifacts into the canonical final package
- write `bundle.json`
- connect package export to the worker-driven lifecycle
