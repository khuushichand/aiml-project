# Card-Level Study Assistant And Quiz Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add card-scoped study assistance and missed-question remediation to flashcards and quizzes, including per-card/question history, text chat, voice-transcript input, reply playback, and remediation quiz generation from missed questions.

**Architecture:** Add dedicated study-assistant persistence and flashcard assistant endpoints inside the flashcards/quizzes domain, keep assistant context server-scoped to one flashcard or one quiz-attempt question, and reuse the existing quiz-generation pipeline by extending source resolution with `quiz_attempt` and `quiz_attempt_question`. Voice stays client-orchestrated through existing STT and TTS APIs instead of introducing a new websocket assistant protocol.

**Tech Stack:** FastAPI, Pydantic, SQLite via `CharactersRAGDB`, React, TanStack Query, Ant Design, existing `audio/transcriptions` and `audio/speech` APIs, Vitest, pytest, Bandit.

---

### Task 1: Add Study Assistant Schemas And DB Tables

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Create: `tldw_Server_API/tests/Flashcards/test_study_assistant_db.py`

**Step 1: Write the failing tests**

Add DB tests for:

- creating one thread per flashcard context
- creating one thread per quiz-attempt-question context
- appending assistant/user messages
- incrementing `message_count` and `last_message_at`
- persisting `structured_payload_json` and `context_snapshot_json`

Example test shape:

```python
def test_get_or_create_flashcard_assistant_thread(chacha_db, flashcard_uuid):
    thread_a = chacha_db.get_or_create_study_assistant_thread(
        context_type="flashcard",
        flashcard_uuid=flashcard_uuid,
    )
    thread_b = chacha_db.get_or_create_study_assistant_thread(
        context_type="flashcard",
        flashcard_uuid=flashcard_uuid,
    )
    assert thread_a["id"] == thread_b["id"]
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_study_assistant_db.py -v
```

Expected: FAIL because the tables and helpers do not exist.

**Step 3: Write the minimal implementation**

In `ChaChaNotes_DB.py`:

- add `study_assistant_threads`
- add `study_assistant_messages`
- add migration/bootstrap logic for both tables
- add DB helpers:
  - `get_or_create_study_assistant_thread`
  - `get_study_assistant_thread`
  - `list_study_assistant_messages`
  - `append_study_assistant_message`

In `schemas/flashcards.py` add response models for:

- thread summary
- assistant message
- assistant history response

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_study_assistant_db.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/tests/Flashcards/test_study_assistant_db.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add study assistant persistence"
```

### Task 2: Add Flashcard Assistant Context Assembly And Response Contracts

**Files:**
- Create: `tldw_Server_API/app/core/Flashcards/study_assistant.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Create: `tldw_Server_API/tests/Flashcards/test_study_assistant_service.py`

**Step 1: Write the failing tests**

Add service tests for:

- building flashcard context from one card and recent thread history
- rejecting missing cards
- generating fact-check structured payloads with required keys
- limiting recent-history/context size

Example test shape:

```python
def test_build_flashcard_assistant_context_uses_only_active_card(chacha_db, flashcard_uuid):
    context = build_flashcard_assistant_context(chacha_db, flashcard_uuid)
    assert context["flashcard"]["uuid"] == flashcard_uuid
    assert "deck_cards" not in context
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_study_assistant_service.py -v
```

Expected: FAIL because the service module does not exist.

**Step 3: Write the minimal implementation**

In `study_assistant.py` implement:

- flashcard context assembly
- quiz-attempt-question context assembly
- action-to-prompt helpers for:
  - `explain`
  - `mnemonic`
  - `follow_up`
  - `fact_check`
  - `freeform`
- structured response normalization for fact-check results

In `schemas/flashcards.py` add:

- `StudyAssistantAction`
- request schema for assistant response creation
- structured payload schema for fact-check responses

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_study_assistant_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/core/Flashcards/study_assistant.py tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/tests/Flashcards/test_study_assistant_service.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add study assistant context helpers"
```

### Task 3: Add Flashcard Assistant Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

**Step 1: Write the failing tests**

Add endpoint tests for:

- `GET /api/v1/flashcards/{card_uuid}/assistant` returns thread summary, messages, and context snapshot
- `POST /api/v1/flashcards/{card_uuid}/assistant/respond` appends user and assistant messages
- missing card returns `404`
- invalid action returns `422`
- fact-check response returns required structured payload keys

Example test shape:

```python
def test_flashcard_assistant_respond_persists_thread(client, auth_headers, flashcard_uuid):
    response = client.post(
        f"/api/v1/flashcards/{flashcard_uuid}/assistant/respond",
        json={"action": "explain"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["role"] == "assistant"
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "assistant" -v
```

Expected: FAIL because the routes do not exist.

**Step 3: Write the minimal implementation**

In `flashcards.py` add:

- `GET /api/v1/flashcards/{card_uuid}/assistant`
- `POST /api/v1/flashcards/{card_uuid}/assistant/respond`

Implementation notes:

- load/create the thread through Task 1 helpers
- build server-side context through Task 2 helpers
- call the existing LLM infrastructure with narrow action-specific prompts
- persist the user and assistant messages only after a successful assistant response

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "assistant" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add card study assistant endpoints"
```

### Task 4: Extend Quiz Source Resolution For Remediation

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Modify: `tldw_Server_API/app/services/quiz_source_resolver.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py`

**Step 1: Write the failing tests**

Add tests for:

- resolving `quiz_attempt` sources into question evidence
- resolving `quiz_attempt_question` into one missed-question evidence block
- carrying user answer, correctness, correct answer, explanation, and citations into the evidence text
- rejecting missing attempt/question IDs

Example test shape:

```python
def test_resolve_quiz_attempt_question_source_includes_user_answer(chacha_db, quiz_attempt_fixture):
    evidence = resolve_quiz_sources(
        [{"source_type": "quiz_attempt_question", "source_id": "301:12"}],
        db=chacha_db,
        media_db=media_db,
    )
    assert "User answer:" in evidence[0]["text"]
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py -k "quiz_attempt" -v
```

Expected: FAIL because the new source types are unsupported.

**Step 3: Write the minimal implementation**

In `schemas/quizzes.py` extend `QuizSourceType` with:

- `QUIZ_ATTEMPT`
- `QUIZ_ATTEMPT_QUESTION`

In `quiz_source_resolver.py` add:

- parser/helper for attempt-question identifiers
- `quiz_attempt` source resolution
- `quiz_attempt_question` source resolution

Keep evidence clipped and deterministic, and prefer missed-question detail when the source is question-scoped.

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py -k "quiz_attempt" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/api/v1/schemas/quizzes.py tldw_Server_API/app/services/quiz_source_resolver.py tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(quizzes): add remediation quiz source types"
```

### Task 5: Add Quiz Remediation Entry Points And Integration Tests

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`
- Possibly modify: `tldw_Server_API/app/services/quiz_generator.py`

**Step 1: Write the failing tests**

Add endpoint tests for:

- generating a remediation quiz from `quiz_attempt_question` sources
- generating from multiple missed questions in one attempt
- preserving source citations in the generated quiz questions
- rejecting invalid attempt/question source identifiers

Example test shape:

```python
def test_generate_quiz_from_quiz_attempt_question_sources(client, auth_headers):
    response = client.post(
        "/api/v1/quizzes/generate",
        json={
            "sources": [{"source_type": "quiz_attempt_question", "source_id": "301:12"}],
            "num_questions": 3,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k "quiz_attempt_question" -v
```

Expected: FAIL because remediation sources are not wired through the endpoint flow yet.

**Step 3: Write the minimal implementation**

Wire the new source types through quiz generation with the existing request path.

Keep the API surface small:

- no special remediation-only endpoint yet
- use the existing `POST /api/v1/quizzes/generate`
- ensure quiz titles/descriptions stay reasonable for remediation-generated quizzes

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -k "quiz_attempt_question" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/api/v1/endpoints/quizzes.py tldw_Server_API/app/services/quiz_generator.py tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(quizzes): wire remediation quiz generation"
```

### Task 6: Add Frontend Assistant And Remediation Clients

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Modify: `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
- Create: `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardAssistantQueries.test.tsx`
- Create: `apps/packages/ui/src/components/Quiz/hooks/__tests__/useQuizRemediationQueries.test.tsx`

**Step 1: Write the failing tests**

Add hook/service tests for:

- fetching flashcard assistant history
- posting assistant actions
- generating remediation quizzes from selected missed questions
- keeping existing flashcards/quiz queries stable

Example test shape:

```tsx
it("posts flashcard assistant explain actions", async () => {
  await result.current.mutateAsync({ cardUuid: "card-1", action: "explain" })
  expect(mockRequest).toHaveBeenCalledWith(
    expect.objectContaining({ path: "/api/v1/flashcards/card-1/assistant/respond" })
  )
})
```

**Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Flashcards/hooks/__tests__/useFlashcardAssistantQueries.test.tsx src/components/Quiz/hooks/__tests__/useQuizRemediationQueries.test.tsx
```

Expected: FAIL because the services/hooks do not exist.

**Step 3: Write the minimal implementation**

In frontend services add typed clients for:

- flashcard assistant history
- flashcard assistant respond
- remediation quiz generation using `quiz_attempt_question` sources

Add focused query/mutation hooks that isolate assistant loading/error state from existing review/results flows.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Flashcards/hooks/__tests__/useFlashcardAssistantQueries.test.tsx src/components/Quiz/hooks/__tests__/useQuizRemediationQueries.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add apps/packages/ui/src/services/flashcards.ts apps/packages/ui/src/services/quizzes.ts apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardAssistantQueries.test.tsx apps/packages/ui/src/components/Quiz/hooks/__tests__/useQuizRemediationQueries.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(ui): add study assistant and remediation clients"
```

### Task 7: Build The ReviewTab Study Assistant Panel

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/components/FlashcardStudyAssistantPanel.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/components/VoiceTranscriptComposer.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.*.test.tsx`

**Step 1: Write the failing tests**

Add UI tests for:

- rendering quick actions on an active card
- loading per-card history
- posting `Explain` and `Fact-check me`
- transcript confirmation before send
- reply playback action visibility
- non-blocking error state when assistant requests fail

Example test shape:

```tsx
it("submits fact-check requests only after transcript confirmation", async () => {
  renderReviewTab()
  fireEvent.click(screen.getByRole("button", { name: /fact-check me/i }))
  expect(screen.getByText(/confirm transcript/i)).toBeInTheDocument()
})
```

**Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
```

Expected: FAIL because the panel does not exist.

**Step 3: Write the minimal implementation**

Build `FlashcardStudyAssistantPanel` and integrate it into `ReviewTab`.

Implementation notes:

- keep local `idle | transcribing | responding | speaking | error` state
- hide voice actions when STT is unavailable
- use browser or server TTS only for explicit playback, not autoplay
- keep review/rating/undo flows untouched when the assistant is idle or failing

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx apps/packages/ui/src/components/Flashcards/components/FlashcardStudyAssistantPanel.tsx apps/packages/ui/src/components/Flashcards/components/VoiceTranscriptComposer.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add review study assistant panel"
```

### Task 8: Build The ResultsTab Remediation Panel

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- Create: `apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.*.test.tsx`

**Step 1: Write the failing tests**

Add UI tests for:

- explaining a missed question
- selecting multiple missed questions for remediation
- generating a remediation quiz from selected misses
- creating remediation flashcards
- preserving existing results filtering and flashcards handoff

Example test shape:

```tsx
it("generates remediation quizzes from selected missed questions", async () => {
  renderResultsTab()
  fireEvent.click(screen.getByLabelText(/select missed question 12/i))
  fireEvent.click(screen.getByRole("button", { name: /create remediation quiz/i }))
  expect(mockGenerateQuiz).toHaveBeenCalled()
})
```

**Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: FAIL because the remediation panel does not exist.

**Step 3: Write the minimal implementation**

Build `QuizRemediationPanel` and integrate it into `ResultsTab`.

Implementation notes:

- support per-question actions and selected-question batch actions
- reuse the existing flashcard conversion and flashcards-study handoff patterns where possible
- keep remediation loading/error state separate from attempt/result browsing state

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(quizzes): add remediation panel"
```

### Task 9: Verify, Document, And Clean Up

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

**Step 1: Add docs updates**

Document:

- flashcard study assistant actions
- voice transcript confirmation flow
- card/question history behavior
- remediation quiz generation from missed questions

**Step 2: Run targeted backend tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_study_assistant_db.py tldw_Server_API/tests/Flashcards/test_study_assistant_service.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -v
```

Expected: PASS.

**Step 3: Run targeted frontend tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Flashcards/hooks/__tests__/useFlashcardAssistantQueries.test.tsx src/components/Quiz/hooks/__tests__/useQuizRemediationQueries.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: PASS.

**Step 4: Run Bandit on the touched Python scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r tldw_Server_API/app/core/Flashcards/study_assistant.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/api/v1/endpoints/quizzes.py tldw_Server_API/app/services/quiz_source_resolver.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_study_assistant.json
```

Expected: no new findings in touched code.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "docs(flashcards): document study assistant remediation"
```

## Execution Notes

- Keep assistant context strictly scoped to one flashcard or one quiz-attempt question.
- Do not persist failed transcription attempts as assistant messages.
- Keep voice transport client-driven through existing STT and TTS APIs.
- Keep assistant actions read-only with respect to scheduling and card edits.
- Reuse existing quiz generation and flashcard handoff primitives instead of building a second remediation pipeline.
