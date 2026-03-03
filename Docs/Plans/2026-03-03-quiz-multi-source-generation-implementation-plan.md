# Quiz Multi-Source Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable quiz generation from mixed media, notes, flashcard decks, and specific flashcards via `POST /api/v1/quizzes/generate`, with strict per-question provenance enforcement.

**Architecture:** Extend the existing quiz generation contract with `sources[]`, add a backend source-resolution pipeline that normalizes mixed sources into anchored evidence, enforce strict citation validation before persistence, and persist source-bundle metadata on quizzes for UI discoverability. Keep backward compatibility by mapping legacy `media_id` requests to a single-source bundle.

**Tech Stack:** FastAPI, Pydantic, CharactersRAGDB (SQLite/Postgres abstraction), React + Ant Design + React Query, Vitest, Pytest.

---

### Task 1: Extend Generation + Citation Contracts (Backend and Frontend Types)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Test: `tldw_Server_API/tests/Quizzes/test_quiz_generate_schema_contract.py` (new)
- Test: `apps/packages/ui/src/services/__tests__/quizzes.test.ts`

**Step 1: Write the failing tests**

```python
from pydantic import ValidationError
from tldw_Server_API.app.api.v1.schemas.quizzes import QuizGenerateRequest, SourceCitation


def test_quiz_generate_request_accepts_sources_array():
    payload = QuizGenerateRequest.model_validate(
        {
            "num_questions": 5,
            "sources": [{"source_type": "note", "source_id": "note-1"}],
        }
    )
    assert payload.sources[0].source_type == "note"


def test_quiz_generate_request_rejects_unknown_source_type():
    try:
        QuizGenerateRequest.model_validate(
            {
                "sources": [{"source_type": "unknown", "source_id": "1"}],
            }
        )
    except ValidationError:
        return
    assert False, "expected ValidationError"


def test_source_citation_accepts_canonical_source_fields():
    citation = SourceCitation.model_validate(
        {
            "source_type": "flashcard_card",
            "source_id": "card-uuid",
            "quote": "sample"
        }
    )
    assert citation.source_type == "flashcard_card"
```

```ts
it("sends sources[] in quiz generation body", async () => {
  await generateQuiz({
    num_questions: 8,
    sources: [{ source_type: "note", source_id: "note-1" }]
  } as any)

  expect(mockBgRequest).toHaveBeenCalledWith(
    expect.objectContaining({
      path: "/api/v1/quizzes/generate",
      body: expect.objectContaining({
        sources: [{ source_type: "note", source_id: "note-1" }]
      })
    })
  )
})
```

**Step 2: Run tests to verify they fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_generate_schema_contract.py -v`
- `bunx vitest run apps/packages/ui/src/services/__tests__/quizzes.test.ts`

Expected: FAIL because `sources` and citation canonical fields are missing from types/schemas.

**Step 3: Write minimal implementation**

```python
class QuizGenerateSource(BaseModel):
    source_type: Literal["media", "note", "flashcard_deck", "flashcard_card"]
    source_id: str = Field(..., min_length=1)

class SourceCitation(BaseModel):
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    # retain existing fields: media_id, chunk_id, timestamp_seconds, source_url, ...

class QuizGenerateRequest(BaseModel):
    media_id: Optional[int] = None
    sources: Optional[list[QuizGenerateSource]] = None
    # keep existing fields
```

```ts
export type QuizGenerateSource = {
  source_type: "media" | "note" | "flashcard_deck" | "flashcard_card"
  source_id: string
}

export type SourceCitation = {
  source_type?: string | null
  source_id?: string | null
  // keep existing citation fields
}

export type QuizGenerateRequest = {
  media_id?: number
  sources?: QuizGenerateSource[]
  // existing fields...
}
```

**Step 4: Re-run tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_generate_schema_contract.py -v`
- `bunx vitest run apps/packages/ui/src/services/__tests__/quizzes.test.ts`

Expected: PASS for schema/type contract tests.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/quizzes.py \
  tldw_Server_API/tests/Quizzes/test_quiz_generate_schema_contract.py \
  apps/packages/ui/src/services/quizzes.ts \
  apps/packages/ui/src/services/__tests__/quizzes.test.ts
git commit -m "feat(quiz): add multi-source generation and citation contract types"
```

### Task 2: Persist and Expose Source Bundle Metadata (DB + API + UI Types)

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Test: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`

**Step 1: Write the failing tests**

```python
def test_quiz_source_bundle_roundtrip_via_create_and_get(quizzes_db):
    quiz_id = quizzes_db.create_quiz(
        name="source bundle",
        source_bundle_json=[{"source_type": "note", "source_id": "n1"}],
    )
    row = quizzes_db.get_quiz(quiz_id)
    assert row["source_bundle_json"][0]["source_id"] == "n1"
```

```python
def test_quiz_response_includes_source_bundle(client_with_quizzes_db):
    created = client_with_quizzes_db.post("/api/v1/quizzes", json={"name": "q"}, headers=AUTH_HEADERS)
    quiz_id = created.json()["id"]
    fetched = client_with_quizzes_db.get(f"/api/v1/quizzes/{quiz_id}", headers=AUTH_HEADERS)
    assert "source_bundle_json" in fetched.json()
```

**Step 2: Run tests to verify they fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k source_bundle -v`

Expected: FAIL because DB/schema responses do not carry source bundle.

**Step 3: Implement minimal persistence + response exposure**

```python
# Schema version bump
_CURRENT_SCHEMA_VERSION = 30

# Add migration dispatcher calls for v29->v30 in both new DB and existing DB paths
if target_version >= 30 and current_db_version == 29:
    self._migrate_from_v29_to_v30(conn)

# Migration body
# sqlite: ALTER TABLE quizzes ADD COLUMN source_bundle_json TEXT
# postgres: ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS source_bundle_json JSONB

# CRUD methods (create/get/list/update)
# serialize/deserialize source_bundle_json
```

Expose `source_bundle_json` in:
- `QuizResponse` backend schema
- frontend `Quiz` type in `apps/packages/ui/src/services/quizzes.ts`

**Step 4: Re-run tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k source_bundle -v`

Expected: PASS with DB+API round-trip.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/api/v1/schemas/quizzes.py \
  apps/packages/ui/src/services/quizzes.ts \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py
git commit -m "feat(quiz-db): persist and expose source bundle metadata"
```

### Task 3: Build Source Resolver for Media, Notes, Decks, and Cards

**Files:**
- Create: `tldw_Server_API/app/services/quiz_source_resolver.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py`

**Step 1: Write the failing tests**

```python
def test_resolves_note_source_to_evidence_chunks():
    evidence = resolve_quiz_sources(
        [{"source_type": "note", "source_id": note_id}],
        db=notes_db,
        media_db=media_db,
    )
    assert evidence[0]["source_type"] == "note"
    assert evidence[0]["source_id"] == note_id
    assert evidence[0]["text"]
```

```python
def test_resolves_flashcard_deck_to_card_evidence_chunks():
    evidence = resolve_quiz_sources(
        [{"source_type": "flashcard_deck", "source_id": str(deck_id)}],
        db=notes_db,
        media_db=media_db,
    )
    assert len(evidence) >= 2
```

```python
def test_resolves_flashcard_card_source():
    evidence = resolve_quiz_sources(
        [{"source_type": "flashcard_card", "source_id": card_uuid}],
        db=notes_db,
        media_db=media_db,
    )
    assert evidence[0]["source_id"] == card_uuid
```

**Step 2: Run tests to verify failure**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py -v`

Expected: FAIL because resolver module does not exist.

**Step 3: Implement minimal resolver**

```python
def resolve_quiz_sources(sources, *, db, media_db):
    # returns list[{source_type, source_id, anchor_id, text, metadata}]
    # media -> media content/transcript
    # note -> note title/content
    # flashcard_deck -> all cards in deck
    # flashcard_card -> single card
    return evidence_chunks
```

Also include dedup of duplicate source entries and deterministic ordering.

**Step 4: Re-run tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py -v`

Expected: PASS for all resolver paths.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/quiz_source_resolver.py \
  tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py
git commit -m "feat(quiz): add mixed-source resolver for quiz generation"
```

### Task 4: Enforce Strict Provenance Validation Before Persistence

**Files:**
- Modify: `tldw_Server_API/app/services/quiz_generator.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quiz_generator_prompt_template.py`
- Create: `tldw_Server_API/tests/Quizzes/test_quiz_generator_provenance.py`

**Step 1: Write the failing tests**

```python
def test_rejects_questions_without_source_citations():
    with pytest.raises(ValueError, match="strict provenance"):
        _validate_strict_provenance(
            [{"question_text": "Q1", "source_citations": []}],
            allowed_sources={("note", "n1")},
        )
```

```python
def test_rejects_citations_not_in_selected_sources():
    with pytest.raises(ValueError, match="unknown source"):
        _validate_strict_provenance(
            [{"source_citations": [{"source_type": "media", "source_id": "999"}]}],
            allowed_sources={("note", "n1")},
        )
```

```python
def test_accepts_valid_citations_for_selected_sources():
    _validate_strict_provenance(
        [{"source_citations": [{"source_type": "note", "source_id": "n1"}]}],
        allowed_sources={("note", "n1")},
    )
```

**Step 2: Run tests to confirm failure**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_generator_provenance.py -v`

Expected: FAIL because validator does not exist.

**Step 3: Implement minimal strict validator + generator wiring**

```python
def _validate_strict_provenance(questions, allowed_sources):
    for q in questions:
        citations = q.get("source_citations") or []
        if not citations:
            raise ValueError("strict provenance failed: missing citations")
        for c in citations:
            key = (str(c.get("source_type") or "").strip(), str(c.get("source_id") or "").strip())
            if key not in allowed_sources:
                raise ValueError("strict provenance failed: unknown source citation")
```

Run this validator before writing quiz/questions to DB.

**Step 4: Re-run tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_generator_provenance.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_generator_prompt_template.py -v`

Expected: PASS; strict validation enforced.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/quiz_generator.py \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_prompt_template.py \
  tldw_Server_API/tests/Quizzes/test_quiz_generator_provenance.py
git commit -m "feat(quiz): enforce strict provenance validation for generated questions"
```

### Task 5: Endpoint Normalization + Backward Compatibility (Deterministic Tests)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`

**Step 1: Write the failing endpoint tests**

```python
def test_generate_maps_legacy_media_id_to_sources(monkeypatch, client_with_quizzes_db):
    captured = {}

    async def fake_generate_quiz_from_media(**kwargs):
        captured["media_id"] = kwargs.get("media_id")
        captured["sources"] = kwargs.get("sources")
        return {"quiz": {"id": 1, "name": "q", "total_questions": 0, "deleted": False, "client_id": "x", "version": 1}, "questions": []}

    monkeypatch.setattr("tldw_Server_API.app.api.v1.endpoints.quizzes.generate_quiz_from_media", fake_generate_quiz_from_media)

    response = client_with_quizzes_db.post(
        "/api/v1/quizzes/generate",
        json={"media_id": 42, "num_questions": 3},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert captured["sources"][0]["source_type"] == "media"
    assert captured["sources"][0]["source_id"] == "42"
```

```python
def test_generate_rejects_empty_sources(client_with_quizzes_db):
    response = client_with_quizzes_db.post(
        "/api/v1/quizzes/generate",
        json={"sources": [], "num_questions": 3},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400
    assert "At least one source" in str(response.json())
```

**Step 2: Run tests to verify failure**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k "legacy_media_id_to_sources or rejects_empty_sources" -v`

Expected: FAIL on mapping/validation behavior.

**Step 3: Implement endpoint normalization and guardrails**

```python
if request.sources:
    request_sources = [s.model_dump() for s in request.sources]
elif request.media_id:
    request_sources = [{"source_type": "media", "source_id": str(request.media_id)}]
else:
    raise HTTPException(status_code=400, detail="At least one source is required")
```

Pass normalized `request_sources` into generator and store in `source_bundle_json`.

**Step 4: Re-run tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k generate -v`

Expected: PASS for deterministic legacy mapping and empty-source rejection.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py
git commit -m "feat(quiz-api): normalize generate sources with legacy media fallback"
```

### Task 6: Add Multi-Source Query + Selection UX in GenerateTab

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/tabs/GenerateTab.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Test: `apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx`

**Step 1: Write failing UI tests for source querying and submission**

```ts
it("submits mixed sources in generate payload", async () => {
  // arrange selected media + note + deck + card
  fireEvent.click(screen.getByRole("button", { name: /Generate Quiz/i }))
  await waitFor(() =>
    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        request: expect.objectContaining({
          sources: expect.arrayContaining([
            expect.objectContaining({ source_type: "media" }),
            expect.objectContaining({ source_type: "note" }),
            expect.objectContaining({ source_type: "flashcard_deck" }),
            expect.objectContaining({ source_type: "flashcard_card" })
          ])
        })
      })
    )
  )
})
```

```ts
it("blocks submit when no sources selected", async () => {
  fireEvent.click(screen.getByRole("button", { name: /Generate Quiz/i }))
  expect(mutateAsync).not.toHaveBeenCalled()
  expect(await screen.findByText(/select at least one source/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify failure**

Run:
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx`

Expected: FAIL because current tab is media-only.

**Step 3: Implement minimal multi-source UX + data loading**

```ts
type QuizSourceSelection = { source_type: "media" | "note" | "flashcard_deck" | "flashcard_card"; source_id: string }

const selectedSources = buildSelectedSources({ mediaIds, noteIds, deckIds, cardIds })
await mutateAsync({ request: { ...values, sources: selectedSources } })
```

Add/normalize APIs needed for selector data:
- notes list/search
- flashcard deck list
- flashcard list by deck for manual card picking

**Step 4: Re-run tests**

Run:
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx`

Expected: PASS for mixed-source submission and no-source guardrail.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Quiz/tabs/GenerateTab.tsx \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/services/flashcards.ts \
  apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts \
  apps/packages/ui/src/services/quizzes.ts \
  apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx
git commit -m "feat(quiz-ui): add mixed-source selectors and generation payload"
```

### Task 7: Add Source Bundle Badges in Take/Manage

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/ManageTab.tsx`
- Create: `apps/packages/ui/src/components/Quiz/utils/sourceBundle.ts`
- Test: `apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx`
- Test: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.edit-modal-scale.test.tsx`

**Step 1: Write failing display tests**

```ts
it("shows source badges for mixed-source quizzes", () => {
  render(<TakeQuizTab ... />)
  expect(screen.getByText(/Media/i)).toBeInTheDocument()
  expect(screen.getByText(/Notes/i)).toBeInTheDocument()
  expect(screen.getByText(/Flashcards/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify failure**

Run:
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx`
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.edit-modal-scale.test.tsx`

Expected: FAIL because source bundle metadata is not rendered.

**Step 3: Implement minimal source summary rendering**

```ts
export const summarizeQuizSources = (bundle?: QuizGenerateSource[]) => ({
  media: countBy(bundle, "media"),
  notes: countBy(bundle, "note"),
  flashcards: countBy(bundle, "flashcard_deck") + countBy(bundle, "flashcard_card")
})
```

Render compact badges on quiz cards in Take/Manage.

**Step 4: Re-run tests**

Run:
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx`
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.edit-modal-scale.test.tsx`

Expected: PASS with deterministic badge output.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx \
  apps/packages/ui/src/components/Quiz/tabs/ManageTab.tsx \
  apps/packages/ui/src/components/Quiz/utils/sourceBundle.ts \
  apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx \
  apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.edit-modal-scale.test.tsx
git commit -m "feat(quiz-ui): show mixed-source badges in take and manage"
```

### Task 8: Localization and Unit/Integration Verification

**Files:**
- Modify: `apps/packages/ui/src/assets/locale/en/option.json`
- Modify: `apps/packages/ui/src/public/_locales/en/option.json`
- Test: update existing unit/integration tests where copy changed

**Step 1: Add failing localization assertions**

```ts
expect(screen.getByText(/Select Sources/i)).toBeInTheDocument()
expect(screen.getByText(/Strict provenance required/i)).toBeInTheDocument()
```

**Step 2: Run tests and confirm failure**

Run:
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx`

Expected: FAIL until new keys are added.

**Step 3: Implement minimal localization updates**

```json
{
  "quiz": {
    "selectSources": "Select Sources",
    "strictProvenance": "Strict provenance required",
    "selectAtLeastOneSource": "Select at least one source before generating."
  }
}
```

Mirror keys in `src/assets/locale/en/option.json` and `src/public/_locales/en/option.json` to keep parity.

**Step 4: Re-run tests**

Run:
- `bunx vitest run apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/assets/locale/en/option.json \
  apps/packages/ui/src/public/_locales/en/option.json

git commit -m "chore(quiz-ui): add mixed-source generation localization strings"
```

### Task 9: E2E Coverage and Security Validation

**Files:**
- Modify: `apps/extension/tests/e2e/quiz-ux.spec.ts`
- Verify: touched backend/frontend paths from prior tasks

**Step 1: Add failing E2E mixed-source path assertions**

```ts
await expect(page.getByText(/Select Sources/i)).toBeVisible()
await expect(page.getByRole("button", { name: /Generate Quiz/i })).toBeEnabled()
// verify generated result includes source indicators
```

**Step 2: Run E2E test and verify failure**

Run:
- `bunx playwright test apps/extension/tests/e2e/quiz-ux.spec.ts --reporter=line`

Expected: FAIL before mixed-source flow support.

**Step 3: Implement E2E fixture and flow updates**

Update test setup to seed:
- one note
- one flashcard deck with cards
- one media item

Exercise mixed-source generate flow and verify success state.

**Step 4: Run full verification + Bandit**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Quizzes -v`
- `bunx vitest run apps/packages/ui/src/services/__tests__/quizzes.test.ts apps/packages/ui/src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx`
- `bunx playwright test apps/extension/tests/e2e/quiz-ux.spec.ts --reporter=line`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/quiz_generator.py tldw_Server_API/app/services/quiz_source_resolver.py tldw_Server_API/app/api/v1/endpoints/quizzes.py -f json -o /tmp/bandit_quiz_multi_source.json`

Expected: tests pass; no new high-severity issues in Bandit report for touched backend files.

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/quiz-ux.spec.ts
git commit -m "test(quiz-e2e): cover mixed-source generation flow"
```

## Execution Notes

- Use `@superpowers/test-driven-development` during each task’s red/green cycle.
- Use `@superpowers/verification-before-completion` before claiming completion.
- Keep commits scoped to each task (do not batch unrelated changes).
- Do not modify unrelated dirty files already present in workspace.
- For strict provenance behavior, fail entire generation on any invalid citation.
