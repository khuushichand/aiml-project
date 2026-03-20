# Optional Per-Deck FSRS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add FSRS as an optional per-deck scheduler alongside the existing SM-2+ path without breaking current review, analytics, deck creation, or sync behavior.

**Architecture:** Keep the shared queue model and review endpoints, add deck-level `scheduler_type`, store scheduler config in a single JSON envelope, add per-card `scheduler_state_json`, and dispatch review calculations to either `scheduler_sm2.py` or a new `scheduler_fsrs.py`. The backend remains the sole owner of interval math and review previews; the UI only edits deck config and renders returned state.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL migrations inside `ChaChaNotes_DB.py`, React, TypeScript, Vitest, pytest.

---

### Task 1: Add failing backend schema tests for FSRS storage

**Files:**
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py` (only if deck schema helpers are shared)

**Step 1: Write the failing test**

Add tests that assert:

```python
assert "scheduler_type" in deck_columns
assert "scheduler_state_json" in flashcard_columns
assert "scheduler_type" in review_columns

deck = chacha_db.get_deck(deck_id)
settings = json.loads(deck["scheduler_settings_json"])
assert "sm2_plus" in settings
assert "fsrs" in settings
assert deck["scheduler_type"] == "sm2_plus"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py -v
```

Expected: FAIL because the new columns and envelope shape do not exist yet.

**Step 3: Write minimal schema changes**

Modify:

- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

Add column-ensure logic for:

```python
ALTER TABLE decks ADD COLUMN scheduler_type TEXT NOT NULL DEFAULT 'sm2_plus'
ALTER TABLE flashcards ADD COLUMN scheduler_state_json TEXT NOT NULL DEFAULT '{}'
ALTER TABLE flashcard_reviews ADD COLUMN scheduler_type TEXT NOT NULL DEFAULT 'sm2_plus'
```

Update default deck settings JSON creation to:

```python
{
    "sm2_plus": get_default_scheduler_settings(),
    "fsrs": get_default_fsrs_settings(),
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py
git commit -m "feat: add fsrs scheduler schema fields"
```

### Task 2: Add a pure FSRS scheduler module with deterministic bootstrap tests

**Files:**
- Create: `tldw_Server_API/app/core/Flashcards/scheduler_fsrs.py`
- Create: `tldw_Server_API/tests/Flashcards/test_scheduler_fsrs.py`
- Modify: `tldw_Server_API/app/core/Flashcards/__init__.py` if exports are used

**Step 1: Write the failing test**

Add unit tests for:

- default FSRS settings normalization
- bootstrap from an existing card snapshot
- review transition returns shared compatibility fields
- `next_intervals` preview generation

Example:

```python
def test_bootstrap_fsrs_state_from_existing_card_snapshot():
    card = {
        "interval_days": 12,
        "repetitions": 7,
        "lapses": 1,
        "last_reviewed_at": "2026-03-01T00:00:00Z",
        "due_at": "2026-03-13T00:00:00Z",
        "queue_state": "review",
    }
    state = bootstrap_fsrs_state(card, now=parse_iso_datetime("2026-03-13T00:00:00Z"))
    assert isinstance(state, dict)
    assert state["stability"] > 0
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_scheduler_fsrs.py -v
```

Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

Create `scheduler_fsrs.py` with:

- `DEFAULT_FSRS_SETTINGS`
- `normalize_fsrs_settings`
- `bootstrap_fsrs_state`
- `simulate_fsrs_review_transition`
- `build_fsrs_next_interval_previews`

Keep the v1 settings intentionally small:

```python
DEFAULT_FSRS_SETTINGS = {
    "target_retention": 0.9,
    "maximum_interval_days": 36500,
    "enable_fuzz": False,
}
```

Return shared fields:

```python
{
    "queue_state": "review",
    "due_at": ...,
    "interval_days": ...,
    "repetitions": ...,
    "lapses": ...,
    "scheduler_state_json": "...",
    "last_reviewed_at": ...,
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_scheduler_fsrs.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Flashcards/scheduler_fsrs.py tldw_Server_API/tests/Flashcards/test_scheduler_fsrs.py
git commit -m "feat: add fsrs scheduler engine"
```

### Task 3: Dispatch review logic by scheduler type and persist FSRS state

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py:19524-19598`
- Modify: `tldw_Server_API/app/core/Flashcards/scheduler_sm2.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py:1411-1424`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

**Step 1: Write the failing integration tests**

Add tests for:

- `POST /api/v1/flashcards/review` returns `scheduler_type`
- FSRS deck review persists `scheduler_state_json`
- switched existing deck lazily bootstraps missing FSRS state on first review

Example:

```python
assert payload["scheduler_type"] == "fsrs"
assert card_after["scheduler_state_json"] != "{}"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "fsrs or scheduler_type" -v
```

Expected: FAIL because review still assumes one SM-2+ scheduler.

**Step 3: Write minimal implementation**

In `ChaChaNotes_DB.py`:

- select `d.scheduler_type` and `d.scheduler_settings_json`
- deserialize the settings envelope
- dispatch:

```python
if scheduler_type == "fsrs":
    upd = simulate_fsrs_review_transition(...)
else:
    upd = simulate_review_transition(...)
```

- update `flashcards.scheduler_state_json`
- insert `flashcard_reviews.scheduler_type`
- include `scheduler_type` in returned payload

In `flashcards.py`:

- include `scheduler_type` in `review/next` and review response shapes

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "fsrs or scheduler_type" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/Flashcards/scheduler_sm2.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git commit -m "feat: dispatch flashcard review by scheduler type"
```

### Task 4: Extend deck schemas, create/update endpoints, and sync-log payloads

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py:6422-6468`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py:6482-6560`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py`

**Step 1: Write the failing tests**

Add tests that assert:

- deck create/update accepts `scheduler_type`
- `scheduler_settings_json` stays envelope-shaped
- sync-log deck payload includes `scheduler_type`
- sync-log flashcard payload includes `scheduler_state_json`

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "scheduler or sync_log" -v
```

Expected: FAIL because the schema/API only support one scheduler model.

**Step 3: Write minimal implementation**

In `schemas/flashcards.py`, add:

```python
class FsrsSettings(BaseModel):
    target_retention: float = 0.9
    maximum_interval_days: int = 36500
    enable_fuzz: bool = False

class DeckSchedulerSettingsEnvelope(BaseModel):
    sm2_plus: DeckSchedulerSettings = Field(default_factory=DeckSchedulerSettings)
    fsrs: FsrsSettings = Field(default_factory=FsrsSettings)
```

Extend `DeckCreate`, `DeckUpdate`, and `Deck` with:

- `scheduler_type`
- envelope `scheduler_settings`

Update DB sync triggers so JSON payloads include the new fields.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "scheduler or sync_log" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py
git commit -m "feat: extend flashcard deck schemas for fsrs"
```

### Task 5: Add scheduler-type-aware frontend models and shared editor support

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/utils/scheduler-settings.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useDeckSchedulerDraft.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/components/DeckSchedulerSettingsEditor.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx`

**Step 1: Write the failing frontend tests**

Add tests that assert:

- scheduler-type selector switches between SM-2+ and FSRS
- FSRS settings validate locally
- inactive scheduler settings remain preserved

Example:

```tsx
expect(screen.getByLabelText(/scheduler type/i)).toHaveValue("fsrs")
expect(screen.getByLabelText(/target retention/i)).toBeInTheDocument()
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx
```

Expected: FAIL because the editor is single-scheduler and SM-2+-only.

**Step 3: Write minimal implementation**

In `services/flashcards.ts`, replace the single settings type with:

```ts
export type DeckSchedulerType = "sm2_plus" | "fsrs"

export type FsrsSchedulerSettings = {
  target_retention: number
  maximum_interval_days: number
  enable_fuzz: boolean
}

export type DeckSchedulerSettingsEnvelope = {
  sm2_plus: DeckSchedulerSettings
  fsrs: FsrsSchedulerSettings
}
```

Update the shared draft/editor layer so it:

- tracks `schedulerType`
- validates SM-2+ and FSRS separately
- preserves both config objects in one draft

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/flashcards.ts apps/packages/ui/src/components/Flashcards/utils/scheduler-settings.ts apps/packages/ui/src/components/Flashcards/hooks/useDeckSchedulerDraft.ts apps/packages/ui/src/components/Flashcards/components/DeckSchedulerSettingsEditor.tsx apps/packages/ui/src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx
git commit -m "feat: add fsrs-aware scheduler editor"
```

### Task 6: Expose FSRS in Scheduler tab and deck creation flows

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/SchedulerTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ImageOcclusionTransferPanel.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx`
- Test: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx`

**Step 1: Write the failing UI tests**

Add tests that assert:

- new decks can be created with `scheduler_type="fsrs"`
- existing decks show scheduler type summary
- switching an existing deck to FSRS shows the bootstrap warning

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: FAIL because create flows and scheduler tab do not support FSRS.

**Step 3: Write minimal implementation**

Wire the shared editor into:

- `SchedulerTab`
- flashcard create drawer
- import/generate/image-occlusion deck creation blocks
- remediation create-new-deck path

Add warning text in `SchedulerTab`:

```tsx
<Alert
  type="warning"
  message="Switching to FSRS initializes existing cards conservatively as they are reviewed."
/>
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/tabs/SchedulerTab.tsx apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx apps/packages/ui/src/components/Flashcards/tabs/ImageOcclusionTransferPanel.tsx apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
git commit -m "feat: expose fsrs across deck creation flows"
```

### Task 7: Keep review UI stable and add scheduler visibility

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/utils/queue-state-badges.tsx` if a scheduler badge helper is needed
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.queue-state.test.tsx` (create if missing)

**Step 1: Write the failing test**

Add a test that asserts:

- returned `scheduler_type` renders a small badge
- review buttons still render server `next_intervals`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.queue-state.test.tsx
```

Expected: FAIL because review responses and UI do not expose scheduler type yet.

**Step 3: Write minimal implementation**

Add a small display-only badge:

```tsx
<Tag>{reviewCard.next_intervals ? activeSchedulerTypeLabel : null}</Tag>
```

Do not change the rating flow or button layout.

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.queue-state.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx apps/packages/ui/src/components/Flashcards/utils/queue-state-badges.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.queue-state.test.tsx
git commit -m "feat: show scheduler type in flashcard review"
```

### Task 8: Run full targeted verification, docs update, and security check

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`
- Modify: any touched implementation files above

**Step 1: Update docs**

Add:

- what FSRS is in this app
- that it is optional per deck
- that existing decks stay on SM-2+ unless switched
- that switched decks bootstrap conservatively

**Step 2: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py \
  tldw_Server_API/tests/Flashcards/test_scheduler_fsrs.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -v
```

Expected: all pass.

**Step 3: Run frontend verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx \
  src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.queue-state.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: all pass.

**Step 4: Run Bandit on touched Python scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/Flashcards/scheduler_fsrs.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/api/v1/endpoints/flashcards.py \
  tldw_Server_API/app/api/v1/schemas/flashcards.py \
  -f json -o /tmp/bandit_optional_fsrs.json
```

Expected: no new findings in touched code.

**Step 5: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md
git commit -m "docs: add optional fsrs guidance"
```
