# Assistant Conflict Recovery UX Design

## Goal

Make flashcard study-assistant and quiz-remediation assistant threads recover cleanly from `409` thread-version conflicts instead of collapsing into a generic unavailable state.

## Scope

This slice only covers assistant conflict recovery UX.

In scope:
- Flashcard study assistant in review
- Quiz remediation assistant
- Conflict-specific retry and reload behavior

Out of scope:
- Server-side remediation conversion persistence
- Scheduler settings during deck creation/edit flows
- Backend API changes unless implementation reveals a missing response detail

## Current State

The backend already supports optimistic concurrency with `expected_thread_version`. The flashcards and quizzes assistant hooks attach the cached thread version automatically when callers do not provide one. On conflict, the backend returns `409`.

The UI still treats these failures as generic assistant outages:
- [FlashcardStudyAssistantPanel.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui/src/components/Flashcards/components/FlashcardStudyAssistantPanel.tsx)
- [ReviewTab.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx)
- [QuizRemediationPanel.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx)

That loses user momentum and hides the actual recovery path.

## Recommended Approach

Keep the backend contract unchanged and solve this at the panel boundary.

`FlashcardStudyAssistantPanel` becomes the shared recovery surface for both flashcards and quiz remediation. It will:
- detect `409` conflicts from `onRespond`
- refetch the latest assistant context through a new `onReloadContext` prop
- preserve the attempted request locally
- render a conflict-specific banner with retry/reload actions

`ReviewTab` and `QuizRemediationPanel` will remain thin coordinators. They will pass the query `refetch` function down to the panel and keep their existing mutation usage.

## Data Flow

### Normal send

1. User triggers quick action, follow-up, or transcript fact-check.
2. Panel calls `onRespond(request)`.
3. Existing mutation updates the assistant query cache.
4. Panel clears any transient conflict state.

### Conflict send

1. User triggers a send.
2. `onRespond(request)` throws an error with HTTP status `409`.
3. Panel stores the attempted request as `pendingRequest`.
4. Panel calls `onReloadContext()`.
5. Query refetches the latest thread and version.
6. Panel shows a conflict banner while leaving the refreshed thread visible.
7. User chooses:
   - `Reload latest`: clear `pendingRequest`, keep refreshed thread
   - `Retry my message`: resend `pendingRequest`
   - transcript-specific retry: same resend path, different label

The retry request should not manually set a new version in the panel. The existing mutation hooks already read the refreshed thread version from the query cache and will attach it automatically.

## UI Behavior

### Flashcards

The study assistant panel stays open during conflicts. The latest thread remains visible. The user sees:
- a conflict banner stating the conversation changed elsewhere
- `Reload latest`
- `Retry my message` or `Retry transcript review`, depending on the preserved request

### Quiz remediation

The remediation panel uses the same assistant surface, so it should recover in place with the same behavior. It should not collapse back to the results list or lose the active question focus.

### Error boundaries

Conflict state is separate from generic errors:
- `409` becomes recoverable conflict UX
- all other failures continue to show the existing generic assistant-unavailable messaging

## State Model

`FlashcardStudyAssistantPanel` will own:
- `assistantError`
- `pendingConflictRequest`
- `isConflictRecovering`

Where:
- `pendingConflictRequest` is the exact failed `StudyAssistantRespondRequest`
- `isConflictRecovering` covers the refetch/reload action state

This state resets when:
- `cardUuid` changes
- the user clicks `Reload latest`
- a retry succeeds

## Testing

Frontend coverage should prove:
- flashcard assistant `409` refetches and shows conflict-specific recovery actions
- quiz remediation `409` preserves the active question and pending request
- `Reload latest` clears the pending request without resending
- transcript/fact-check conflicts preserve transcript payload and use the transcript-specific retry label
- non-409 failures still show the generic unavailable path

Primary test files:
- [ReviewTab.assistant.test.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx)
- [ResultsTab.remediation.test.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx)

## Risks

- The panel must not duplicate or fight the optimistic cache updates already done in the hooks.
- Reload/retry must stay local to the active assistant thread and avoid broad invalidations.
- The retry path should preserve request payloads exactly, especially `voice_transcript` fact-check messages.

## Follow-on Slices

After this slice:
1. Server-side remediation conversion state
2. Scheduler settings in deck creation/edit flows
