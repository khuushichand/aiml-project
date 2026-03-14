# Server-Side Remediation Conversion State Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace browser-only missed-question remediation conversion tracking with a quiz-owned server-side conversion model that creates decks, creates remediation flashcards, preserves superseded history, and drives results-tab status plus flashcards-study handoff.

**Architecture:** Add a dedicated remediation-conversion table and DB helper in ChaChaNotes, expose quiz endpoints for reading and converting missed-question remediation state, and update the quiz results UI to consume server-backed conversion summaries instead of session storage. Keep flashcard identity linked by UUID and preserve the existing card dedupe behavior by allowing multiple question-level conversion rows to reference the same created card UUIDs.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL via `CharactersRAGDB`, React, TanStack Query, Ant Design, Vitest, pytest, Bandit.

---

### Task 1: Add Remediation Conversion Schemas And DB Storage

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Create: `tldw_Server_API/tests/Quizzes/test_remediation_conversions_db.py`

**Step 1: Write the failing tests**

Add DB tests for:

- creating an active remediation conversion row
- enforcing one active row per `attempt_id + question_id`
- superseding the old active row
- storing `flashcard_uuids_json`
- reading active rows and superseded counts

Example test shape:

```python
def test_create_active_remediation_conversion(chacha_db, completed_attempt_id):
    row = chacha_db.create_quiz_remediation_conversion(
        attempt_id=completed_attempt_id,
        quiz_id=7,
        question_id=12,
        target_deck_id=3,
        target_deck_name_snapshot="Renal Deck",
        flashcard_uuids=["card-a"],
        source_ref_id="quiz-attempt:101:question:12",
    )
    assert row["status"] == "active"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_remediation_conversions_db.py -v
```

Expected: FAIL because the table, helper methods, and schemas do not exist.

**Step 3: Write minimal implementation**

In `ChaChaNotes_DB.py`:

- bump schema version
- add `quiz_remediation_conversions`
- add indexes
- add active-row uniqueness enforcement
- add DB helpers for:
  - create conversion row
  - supersede active row
  - list active conversions for an attempt
  - count superseded history

In `schemas/quizzes.py` add models for:

- remediation conversion summary
- remediation conversion list response

**Step 4: Run test to verify it passes**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_remediation_conversions_db.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/schemas/quizzes.py tldw_Server_API/tests/Quizzes/test_remediation_conversions_db.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "feat(quizzes): add remediation conversion persistence"
```

### Task 2: Add Attempt Validation And Conversion Orchestration Helpers

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Create: `tldw_Server_API/tests/Quizzes/test_remediation_conversion_service.py`

**Step 1: Write the failing tests**

Add service-level DB tests for:

- rejecting incomplete attempts
- rejecting question IDs not present in the attempt snapshot
- rejecting questions that were answered correctly
- accepting only missed questions
- preserving the current flashcard dedupe behavior while allowing multiple question records to point to the same UUID set
- creating a deck inside conversion when `create_deck_name` is provided
- marking old active rows `superseded` when `replace_active=True`

Example test shape:

```python
def test_convert_missed_questions_rejects_correct_answers(chacha_db, completed_attempt_id):
    with pytest.raises(InputError):
        chacha_db.convert_quiz_remediation_questions(
            attempt_id=completed_attempt_id,
            question_ids=[11],
            target_deck_id=3,
            replace_active=False,
        )
```

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_remediation_conversion_service.py -v
```

Expected: FAIL because the orchestration helper and validation rules do not exist.

**Step 3: Write minimal implementation**

In `ChaChaNotes_DB.py` implement one helper such as:

- `convert_quiz_remediation_questions(...)`

Behavior:

- load attempt and graded answers
- validate user ownership through existing DB access pattern
- validate completion and missed-question eligibility
- accept exactly one of `target_deck_id` or `create_deck_name`
- create deck when requested
- build flashcard payloads using existing remediation text shape
- preserve current text-answer dedupe behavior
- bulk create flashcards
- write remediation conversion rows
- supersede old actives when requested
- return mixed per-question results plus created card UUIDs

In `schemas/quizzes.py` add:

- convert request model
- per-question convert result model
- convert response model

**Step 4: Run test to verify it passes**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_remediation_conversion_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/schemas/quizzes.py tldw_Server_API/tests/Quizzes/test_remediation_conversion_service.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "feat(quizzes): add remediation conversion orchestration"
```

### Task 3: Expose Quiz Remediation Conversion Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`

**Step 1: Write the failing tests**

Add endpoint tests for:

- `GET /api/v1/quizzes/attempts/{attempt_id}/remediation-conversions`
- `POST /api/v1/quizzes/attempts/{attempt_id}/remediation-conversions/convert`
- `create_deck_name` path
- `replace_active=false` returning `already_exists`
- `replace_active=true` returning `superseded_and_created`
- mixed result responses
- orphaned active conversions being marked in read responses after linked flashcards are deleted

Example test shape:

```python
def test_convert_remediation_questions_creates_new_deck(client, auth_headers, completed_attempt_id):
    response = client.post(
        f"/api/v1/quizzes/attempts/{completed_attempt_id}/remediation-conversions/convert",
        json={
            "question_ids": [12, 13],
            "create_deck_name": "Quiz 7 - Missed Questions",
            "replace_active": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "created"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k "remediation_conversion" -v
```

Expected: FAIL because the routes do not exist.

**Step 3: Write minimal implementation**

In `quizzes.py` add:

- `GET /attempts/{attempt_id}/remediation-conversions`
- `POST /attempts/{attempt_id}/remediation-conversions/convert`

Implementation notes:

- keep all remediation conversion behavior in the quiz domain
- translate DB/domain errors into `400`, `404`, or `409` as appropriate
- return mixed per-question results without failing the entire request on one conflict

**Step 4: Run test to verify it passes**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k "remediation_conversion" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add tldw_Server_API/app/api/v1/endpoints/quizzes.py tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "feat(quizzes): add remediation conversion endpoints"
```

### Task 4: Add Quiz Service And Hook Support For Server-Backed Remediation State

**Files:**
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Modify: `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
- Create: `apps/packages/ui/src/components/Quiz/hooks/__tests__/useQuizRemediationConversionQueries.test.tsx`

**Step 1: Write the failing tests**

Add hook/service tests for:

- loading attempt remediation conversions
- converting with `target_deck_id`
- converting with `create_deck_name`
- retrying with `replace_active=true`
- invalidating and refreshing attempt remediation state after conversion

Example test shape:

```tsx
it("passes replace_active when converting again", async () => {
  await mutation.mutateAsync({
    attemptId: 101,
    payload: {
      question_ids: [12],
      target_deck_id: 3,
      replace_active: true
    }
  })
  expect(api.convertAttemptRemediationQuestions).toHaveBeenCalled()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Quiz/hooks/__tests__/useQuizRemediationConversionQueries.test.tsx
```

Expected: FAIL because the service methods and hooks do not exist.

**Step 3: Write minimal implementation**

In `quizzes.ts` add:

- remediation conversion summary types
- convert request/response types
- read and convert API client helpers

In `useQuizQueries.ts` add:

- `useAttemptRemediationConversionsQuery`
- `useConvertAttemptRemediationQuestionsMutation`

Invalidate:

- attempt remediation query for the active attempt
- any quiz results data paths that need refreshed deck/conversion state

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Quiz/hooks/__tests__/useQuizRemediationConversionQueries.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add apps/packages/ui/src/services/quizzes.ts apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts apps/packages/ui/src/components/Quiz/hooks/__tests__/useQuizRemediationConversionQueries.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "feat(ui): add quiz remediation conversion queries"
```

### Task 5: Replace Session Storage In Results And Remediation UI

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx`

**Step 1: Write the failing tests**

Add or update tests for:

- results tab marks already-converted missed questions from server data
- no remediation conversion session-storage keys are read or written
- convert action uses the new quiz endpoint instead of direct flashcard bulk-create
- `Convert again anyway` resubmits with `replace_active=true`
- deck labels render from active remediation records
- orphaned conversions show stale state and allow reconvert

Example test shape:

```tsx
it("removes session storage remediation tracking", async () => {
  const getItemSpy = vi.spyOn(window.sessionStorage, "getItem")
  render(<ResultsTab />)
  expect(getItemSpy).not.toHaveBeenCalledWith("quiz-results-missed-flashcards-v1")
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx
```

Expected: FAIL because the UI still uses session storage and the flashcards bulk-create hook directly.

**Step 3: Write minimal implementation**

In `ResultsTab.tsx`:

- remove remediation conversion session-storage helpers and state
- fetch remediation conversion summaries for the selected attempt
- route flashcard creation through the new quiz convert mutation
- preserve existing results-filter session-storage behavior
- implement explicit `Convert again anyway` confirmation for active conversions
- compute flashcards-study handoff:
  - keep deck filter when all active conversions share one live deck
  - omit deck filter when active conversions span multiple decks

In `QuizRemediationPanel.tsx`:

- replace `alreadyConverted: boolean`-only display with richer status text
- surface deck labels and stale/orphaned state

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "feat(ui): move remediation conversion state to server"
```

### Task 6: Update Docs And Run Verification

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

**Step 1: Update docs**

Document:

- remediation conversion state is now server-backed
- "Convert again anyway" creates a new active conversion and keeps previous history as superseded
- "Study linked cards" may span multiple decks and therefore may omit the deck filter

**Step 2: Run backend regression**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Quizzes/test_remediation_conversions_db.py \
  tldw_Server_API/tests/Quizzes/test_remediation_conversion_service.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k "remediation_conversion" -v
```

Expected: PASS.

**Step 3: Run frontend regression**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run \
  src/components/Quiz/hooks/__tests__/useQuizRemediationConversionQueries.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx \
  src/components/Flashcards/__tests__/FlashcardsManager.consistency.test.tsx
```

Expected: PASS.

**Step 4: Run Bandit on touched Python scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/app/api/v1/schemas/quizzes.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_remediation_conversion_state.json
```

Expected: no new findings in the touched remediation code.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "docs(quizzes): document server-backed remediation conversions"
```
