# `/tts` Route Reuse of Speech Playground Design

**Date:** 2026-03-11
**Status:** Approved
**Scope:** Reuse the redesigned Speech Playground for the `/tts` route in both the web UI and extension route layer, without changing `/speech` behavior.

---

## Problem

The current `/tts` route still renders the legacy dedicated `TtsPlaygroundPage`, while the recent TTS redesign work landed in `SpeechPlaygroundPage`.

This causes a visible mismatch:

- `/tts` shows the older UI
- `/speech` contains the new TTS experience
- users expect `/tts` to be the dedicated entrypoint into the new TTS UI

The route/component split is currently:

- `apps/packages/ui/src/routes/option-tts.tsx` -> `TtsPlaygroundPage`
- `apps/packages/ui/src/routes/option-speech.tsx` -> `SpeechPlaygroundPage`
- `apps/tldw-frontend/pages/tts.tsx` -> shared `@/routes/option-tts`

---

## Decision

`/tts` should reuse `SpeechPlaygroundPage`, but as a dedicated TTS entrypoint rather than a loose alias.

The route must open the shared Speech Playground in TTS-only mode and keep route identity clear. The route should not drift into STT or Round-trip behavior under the `/tts` URL just because the shared page remembers a previous mode.

---

## Architecture

### Route mapping

- Change `apps/packages/ui/src/routes/option-tts.tsx` to render `SpeechPlaygroundPage`
- Keep `apps/packages/ui/src/routes/option-speech.tsx` rendering the same shared page in unlocked mode
- Leave `apps/tldw-frontend/pages/tts.tsx` and the extension options entrypoint unchanged, since they already consume the shared route layer

### Source of truth

`SpeechPlaygroundPage` becomes the single active implementation for the redesigned TTS surface.

The old `TtsPlaygroundPage` remains in the tree for now, but is no longer used by `/tts`. Cleanup or deletion is a follow-up task, not part of this route swap.

---

## Route And State Behavior

### Current enum nuance

In the current `SpeechPlaygroundPage` implementation, the mode values do not map to plain-English names:

- `listen` = TTS-only surface
- `speak` = STT-only surface
- `roundtrip` = combined Speech Playground

That existing enum should be respected by the route integration unless it is intentionally renamed in a separate refactor.

### Desired behavior

- `/tts` passes a route-level TTS intent into `SpeechPlaygroundPage`
- that route-level intent maps to the existing `listen` mode
- `/speech` remains the unlocked route that uses remembered mode state
- `/tts` must not overwrite the shared remembered mode just by loading

### Locked route semantics

When the page is rendered by `/tts`:

- route-locked TTS mode takes precedence over persisted `speechPlaygroundMode`
- the top mode selector is hidden
- attempts to switch into non-TTS modes are ignored by the page

This preserves clean route meaning:

- `/speech` = multi-mode Speech Playground
- `/tts` = dedicated TTS entry into the same redesigned UI

---

## Component Contract

`SpeechPlaygroundPage` should gain an explicit route-aware prop contract instead of overloading `initialMode`.

Recommended props:

- `lockedMode?: SpeechMode`
- `hideModeSwitcher?: boolean`

Behavior:

- `/tts` passes `lockedMode="listen"` and `hideModeSwitcher`
- `/speech` passes neither prop and keeps current unlocked behavior

This separates two concerns cleanly:

- `initialMode` means default selection behavior
- `lockedMode` means route-enforced behavior

---

## Error Handling And UX Safeguards

- Deep-linking to `/tts` must always land in the redesigned TTS surface, even if local storage previously remembered STT or Round-trip
- Missing or invalid stored mode must not break `/tts`, because the locked route prop wins
- If future code tries to call `setMode` while route-locked, the page should stay in the locked mode
- `/speech` must still expose the mode switcher and remembered-mode behavior exactly as today

---

## Testing Strategy

### Route identity coverage

Update `apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx` to verify:

- `/tts` renders `SpeechPlaygroundPage`
- `/tts` no longer renders `TtsPlaygroundPage`
- `/speech` still renders the shared Speech Playground in unlocked mode
- `/stt` remains unchanged unless intentionally refactored separately

### Speech page coverage

Update `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx` to verify:

- locked TTS mode hides the mode switcher
- locked TTS mode suppresses non-TTS regions
- unlocked mode still renders the normal mode selector

### Regression boundary

No change is required for the Next.js `/tts` page shim unless route-level tests reveal a break in the shared route import.

---

## Non-Goals

- deleting `TtsPlaygroundPage`
- refactoring `/stt` to use `SpeechPlaygroundPage`
- renaming the `listen` / `speak` enum values
- redesigning the `/speech` route

---

## Expected Outcome

After implementation:

- opening `/tts` shows the new Speech Playground TTS UI
- `/speech` still behaves as the multi-mode page
- route identity remains explicit and unsurprising
- extension and web UI both inherit the same fix through the shared route layer
