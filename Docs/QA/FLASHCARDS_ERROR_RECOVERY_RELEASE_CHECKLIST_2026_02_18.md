# Flashcards Error Recovery Release Checklist

Use this checklist before shipping flashcards changes that touch review, card edits, or mutation handlers.

## Review Flow Recovery Checks

- [ ] Trigger a simulated network error during rating submission; verify retry alert appears with `Retry` action.
- [ ] Click `Retry`; verify second submission succeeds and alert clears.
- [ ] Confirm retried submission preserves original answer timing value.
- [ ] Trigger a version-conflict style failure; verify `Reload card` action appears.
- [ ] Click `Reload card`; verify queue refetch runs and user can retry without leaving Review tab.

## Cards/Edit Recovery Checks

- [ ] Trigger edit save conflict (`expected_version` mismatch); verify latest card data reloads in-place.
- [ ] Confirm drawer stays open after conflict and user can resubmit save.
- [ ] Verify non-conflict save failures still show actionable coded error messages.

## Telemetry & Diagnostics Checks

- [ ] Confirm `flashcards_mutation_failed` events are recorded for review/cards failure paths.
- [ ] Confirm `flashcards_retry_requested` and `flashcards_retry_succeeded` events record on review retry flow.
- [ ] Confirm `flashcards_recovered_by_reload` events record on reload reconciliation paths.
- [ ] Verify latest telemetry state can be read from `tldw:flashcards:errorRecoveryTelemetry`.
