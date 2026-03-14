# Card-Level Study Assistant And Quiz Remediation Design

Date: 2026-03-13  
Status: Approved

## Summary

This design adds contextual study assistance to the existing flashcards and quiz workflow without turning the module into a general tutoring product.

The goal is to let users ask for help at the exact moment of confusion:

- while reviewing a flashcard
- after missing a quiz question
- while explaining a card out loud and asking for fact-checking

The slice also closes a repeated feedback gap: keeping a history of questions per card and turning misses into targeted remediation instead of generic re-study.

## Current Baseline

The repo already has the main primitives this slice needs:

- Flashcards `Review` flow with deck-scoped study, undo, cram mode, edit-in-review, and scheduler-backed `next_intervals`
- Quiz generation from `media`, `note`, `flashcard_deck`, and `flashcard_card` sources
- Quiz attempts, scoring, detailed results, and flashcard handoff routes
- Audio transcription and speech synthesis endpoints
- Broad LLM infrastructure for controlled text generation

Relevant code anchors:

- `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
- `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- `apps/packages/ui/src/services/flashcards.ts`
- `apps/packages/ui/src/services/quizzes.ts`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- `tldw_Server_API/app/services/quiz_generator.py`
- `tldw_Server_API/app/services/quiz_source_resolver.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

## Product Framing

This feature should stay tightly contextual.

It is not a new standalone assistant workspace. It is a study aid attached to:

- one flashcard at a time
- one quiz attempt question at a time

That keeps the user inside the existing review/results surfaces and avoids duplicating the broader chat and voice-assistant products already in the repo.

## Recommended Approach

Add a card-scoped and question-scoped `Study Assistant` that lives directly inside the flashcards `Review` tab and quiz `Results` tab.

Recommended capabilities for v1:

- `Explain this card`
- `Give a mnemonic`
- `Ask a follow-up question`
- `Fact-check my explanation`
- `Create remediation quiz from missed questions`
- `Create remediation flashcards from missed questions`
- question-per-card history
- voice input via transcription
- optional spoken playback of assistant replies

Explicit non-scope for v1:

- full real-time websocket voice tutoring
- open-ended deck-wide tutoring over arbitrary card sets
- autonomous card edits or scheduler changes
- freeform access to unrelated notes, chats, or full-deck context

## Architecture

### UI Surfaces

`ReviewTab` gets a collapsible `Study Assistant` panel anchored to the active card.

The panel owns:

- quick actions for the current card
- freeform card-scoped chat
- per-card history
- voice transcript confirmation before send
- optional spoken playback of assistant responses

`ResultsTab` gets a `Remediate` panel scoped to the selected attempt and missed questions.

That panel supports:

- explain a missed question
- generate a follow-up question
- build a remediation quiz
- create remediation flashcards
- jump back into flashcards review with relevant context

### Backend Responsibility Split

Do not route this slice through the general voice-assistant websocket stack.

Instead:

- flashcards/quizzes own assistance context and persistence
- shared LLM infrastructure provides model execution
- existing audio APIs provide transcription and speech synthesis

This keeps the slice small, context-safe, and aligned with the current module.

## Data Model

Add two dedicated ChaChaNotes tables:

- `study_assistant_threads`
- `study_assistant_messages`

### `study_assistant_threads`

Fields:

- `id`
- `context_type: "flashcard" | "quiz_attempt_question"`
- `flashcard_uuid` nullable
- `quiz_attempt_id` nullable
- `question_id` nullable
- `last_message_at`
- `message_count`
- `deleted`
- `client_id`
- `version`
- `created_at`
- `last_modified`

V1 behavior:

- one active thread per flashcard
- one active thread per quiz-attempt question

This is enough to deliver “history of questions per card” without adding session-selection UX.

### `study_assistant_messages`

Fields:

- `id`
- `thread_id`
- `role: "user" | "assistant"`
- `action_type: "explain" | "mnemonic" | "follow_up" | "fact_check" | "freeform"`
- `input_modality: "text" | "voice_transcript"`
- `content`
- `structured_payload_json`
- `context_snapshot_json`
- `provider`
- `model`
- `created_at`
- `client_id`

`context_snapshot_json` should persist the flashcard or quiz-question snapshot used for that turn so history stays explainable even if the underlying card/question later changes.

## API Surface

### Flashcard Assistant

Add:

- `GET /api/v1/flashcards/{card_uuid}/assistant`
- `POST /api/v1/flashcards/{card_uuid}/assistant/respond`

`GET` returns:

- thread summary
- recent messages
- current flashcard context snapshot
- available actions

`POST` accepts:

- `action`
- `message` optional
- `provider` optional
- `model` optional
- `expected_thread_version` optional

`POST` returns:

- updated thread summary
- appended user message
- appended assistant message
- action-specific structured payload

For `fact_check`, the response payload should include:

- `verdict: "correct" | "partially_correct" | "incorrect"`
- `corrections: string[]`
- `missing_points: string[]`
- `next_prompt`

### Quiz Remediation

Do not add a one-off remediation generation pipeline.

Instead, extend `QuizGenerateSourceType` with:

- `quiz_attempt`
- `quiz_attempt_question`

Then reuse the existing quiz generation flow so missed-question remediation becomes a source-shape extension of the current system rather than a parallel subsystem.

`quiz_attempt_question` evidence should include:

- question text
- user answer
- correctness
- correct answer
- explanation
- source citations when present

### Voice And Speech

Assistant endpoints remain text-first.

Voice flow is composed from existing APIs:

- microphone audio -> `/api/v1/audio/transcriptions`
- confirmed transcript -> assistant `respond`
- assistant text -> optional `/api/v1/audio/speech` or browser speech

This delivers voice/chat tutoring now without introducing a second persistent assistant protocol.

## Context Assembly Rules

Assistant context must be narrow and server-side.

Flashcard assistance may include:

- active card fields
- source reference metadata
- recent thread history for that card

Quiz remediation may include:

- selected attempt question
- user answer and correctness
- explanation and citations
- recent thread history for that question

It must not automatically pull:

- the entire deck
- unrelated cards
- unrelated note/chat content
- unrelated quiz attempts

## UI Behavior

### Flashcards `Review`

Add a `Study Assistant` panel with:

- quick actions:
  - `Explain`
  - `Mnemonic`
  - `Follow-up question`
  - `Fact-check me`
- freeform ask box
- per-card thread history
- `Play reply`
- `Use microphone`

`Fact-check me` flow:

1. user chooses `Fact-check me`
2. user types or records an explanation
3. transcript is shown back for confirmation when voice is used
4. assistant returns verdict, corrections, missing points, and a suggested follow-up

### Quiz `Results`

Add a `Remediate` panel for selected missed questions with:

- `Explain mistake`
- `Create follow-up practice question`
- `Create remediation quiz`
- `Create remediation flashcards`
- `Study linked cards`

The best v1 flow is to build remediation quizzes from selected missed questions through the existing quiz pipeline and then reuse the existing take-quiz and flashcards handoff routes.

## Error Handling And Safety

Assistant failures must remain local to the assistant/remediation panel.

They must not block:

- card review
- rating
- undo
- cram mode
- quiz-results browsing
- quiz retake flows

Each panel should have local state:

- `idle`
- `transcribing`
- `responding`
- `speaking`
- `error`

If STT is unavailable:

- hide voice input

If server TTS is unavailable:

- fall back to browser speech when possible
- otherwise stay text-only

Voice transcripts must always be confirmed before persistence.

Assistant actions are read-only with respect to flashcard scheduling and content. They can explain and propose, but actual card edits, rating changes, and quiz creation remain explicit user actions.

## Testing

Backend coverage should include:

- thread/message persistence
- flashcard/question context assembly
- `quiz_attempt_question` source resolution
- fact-check structured response validation
- remediation quiz generation from missed questions

Frontend coverage should include:

- `ReviewTab` assistant actions
- per-card history rendering
- voice transcript confirm/send flow
- reply playback controls
- `ResultsTab` remediation actions
- unchanged flashcards/quiz handoff behavior

Regression coverage should explicitly protect:

- review keyboard shortcuts
- review undo
- quiz-results filters and selection
- existing flashcard and quiz generation

## Explicit Decisions

- Build contextual assistance inside `Review` and `Results`, not as a new workspace.
- Persist per-card and per-quiz-question history in dedicated study-assistant tables.
- Keep assistant endpoints text-first and compose voice on the client from existing audio APIs.
- Extend quiz source resolution with `quiz_attempt` and `quiz_attempt_question` instead of creating a special remediation-only generator.
- Keep assistant context narrow and server-controlled.

## Success Criteria

This design is successful if it:

- helps users resolve confusion without leaving the card or missed question
- adds usable question history per card
- supports spoken explanation plus fact-checking
- reuses the existing quiz pipeline for remediation
- avoids scope creep into a full tutoring platform
