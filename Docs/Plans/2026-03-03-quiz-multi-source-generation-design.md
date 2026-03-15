# Quiz Multi-Source Generation Design (WebUI + Extension)

Date: 2026-03-03  
Status: Approved

## Summary

Extend quiz generation so users can generate a quiz from mixed source types (media, notes, flashcards) in one request, while enforcing strict per-question provenance.

This design keeps the existing endpoint (`POST /api/v1/quizzes/generate`) and extends its request payload, preserving backward compatibility for media-only callers.

## Product Decisions (Approved)

- Source scope: mixed cross-type sources in a single generation request.
- Provenance policy: strict; every generated question must cite at least one selected source.
- Flashcard sourcing modes:
  - deck-level (all cards in selected deck(s))
  - manual card-level selection
- API strategy: extend existing `/api/v1/quizzes/generate`.
- Rollout: direct ship (no feature flag).

## Goals

- Support quiz generation from:
  - media
  - notes
  - flashcard decks
  - specific flashcards
- Keep one unified generation UX in Quiz `Generate` tab.
- Persist source bundle metadata for generated quizzes.
- Enforce citation validity against selected sources.

## Non-Goals

- Creating a new “study packet” resource.
- Splitting quiz generation into multiple endpoints.
- Soft/best-effort provenance mode.

## Architecture

### 1. API Contract Extension (Same Endpoint)

Extend `QuizGenerateRequest` with `sources`.

Legacy compatibility:
- If `sources` is omitted and `media_id` is provided, server treats it as one `media` source.
- Existing clients continue to work.

Example request shape:

```json
{
  "num_questions": 12,
  "question_types": ["multiple_choice", "true_false"],
  "difficulty": "mixed",
  "focus_topics": ["cell membrane", "mitosis"],
  "sources": [
    { "source_type": "media", "source_id": "42" },
    { "source_type": "note", "source_id": "d664c2f4-..." },
    { "source_type": "flashcard_deck", "source_id": "9" },
    { "source_type": "flashcard_card", "source_id": "7e0f0f0a-..." }
  ]
}
```

Proposed source enums:
- `media`
- `note`
- `flashcard_deck`
- `flashcard_card`

### 2. Persistence Model

Keep existing `quizzes.media_id` for compatibility and add:
- `quizzes.source_bundle_json` (JSON text, nullable)

`source_bundle_json` stores canonical source list used for generation and powers quiz source badges in Take/Manage views.

### 3. Citation Model

Extend `SourceCitation` to include canonical fields:
- `source_type`
- `source_id`

Keep existing citation fields (`media_id`, `chunk_id`, `timestamp_seconds`, `source_url`, etc.) for compatibility and richer media references.

### 4. Generation Pipeline Refactor

Add a source resolution stage before prompt assembly:

1. Resolve each source into normalized evidence chunks.
2. Assign stable source anchors (type + id + chunk metadata).
3. Build prompt with explicit citation contract.
4. Parse/normalize output.
5. Validate strict provenance:
   - each question has `source_citations` length >= 1
   - each citation maps to one selected source anchor
6. Persist quiz/questions only if validation passes.

## Frontend / UX Design

## Generate Tab

- Replace “Select Media” card with “Select Sources”.
- Add source-type pickers:
  - Media selector (multi-select)
  - Notes selector (multi-select)
  - Flashcards:
    - Deck selector (multi-select)
    - Card selector (manual specific card picks)
- Add selected-source summary panel:
  - counts by source type
  - estimated content budget warning
- Keep existing question settings (count, type, difficulty, focus topics).
- Submission validation:
  - at least one source selected
  - if manual card mode used, at least one card selected

## Post-Generation UI

- Keep existing generated preview card.
- Add provenance/coverage summary from response metadata.

## Take/Manage Tabs

- Show source badges using `source_bundle_json` metadata.

## Data Flow

1. User selects mixed sources in Generate tab.
2. UI sends one `generate` request with `sources[]`.
3. Backend resolves source content and builds normalized corpus.
4. LLM generates questions with citations.
5. Backend validates strict provenance.
6. On success:
   - persist quiz + questions + citations + source bundle
   - return generated payload + coverage metadata

## Error Handling

- `400 Bad Request`
  - invalid source type
  - empty source list
  - malformed IDs
- `404 Not Found`
  - one or more sources inaccessible/missing
- `413` or `400`
  - source corpus too large (return actionable reduction guidance)
- `422 Unprocessable Entity`
  - strict provenance validation failure
  - missing citations, invalid source references

Strict mode behavior: fail request; do not silently drop invalid questions or sources.

## Testing Strategy

### Backend

- Request schema validation tests for `sources[]`.
- Resolver unit tests for each source type.
- Provenance validator unit tests:
  - reject missing/invalid citations
  - accept valid mixed-source citations
- Integration tests for `/api/v1/quizzes/generate` mixed-source flow.
- Backward compatibility tests (`media_id`-only requests).

### Frontend

- `GenerateTab` tests for multi-source selection and form validation.
- Deck-level and card-level flashcard source tests.
- Request payload contract tests (`sources[]` correctness).
- Preview coverage/provenance display tests.

### E2E

- Mixed-source generation success flow.
- Strict provenance failure flow.
- Regression: media-only generation unchanged.

## Migration & Compatibility

- Add DB migration for `quizzes.source_bundle_json`.
- Keep `quizzes.media_id` and legacy generation request behavior.
- Existing quizzes remain valid with null `source_bundle_json`.

## Risks and Mitigations

- Risk: oversized mixed corpora causing latency/failures.
  - Mitigation: preflight budget estimate + clear reduction guidance.
- Risk: citation drift from model output.
  - Mitigation: strict validator + deterministic source anchors in prompt.
- Risk: UI complexity in source selection.
  - Mitigation: grouped selectors + concise selection summary.

## Acceptance Criteria

- Users can generate quizzes from mixed media + notes + flashcards in one request.
- Every persisted generated question has valid source citation(s) tied to selected sources.
- Deck-level and manual card-level flashcard sourcing both work.
- Media-only legacy generation continues to function without client changes.
