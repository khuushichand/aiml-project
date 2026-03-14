# Persona Setup Handoff Regressions Design

**Date:** 2026-03-14

**Problem**

Recent setup UX changes introduced three regressions in the Persona Garden setup handoff flow:

1. The handoff summary is stored only in route-local draft state, so resuming setup on the `test` step after a reload can show default values instead of the persona's actual saved setup choices.
2. Completing setup back onto the `connections` tab drops the handoff card because that tab is not wrapped in the handoff renderer.
3. Completing setup back onto the `test-lab` tab shows a misleading primary CTA because the handoff card does not treat `test-lab` as a first-class target.

**Approaches Considered**

1. Persist a full review summary in backend setup state.
   This would make the handoff summary durable, but it expands API/schema scope for a small UI regression fix.

2. Derive the handoff summary from current frontend-known saved state.
   This keeps the fix frontend-only by rebuilding the summary from saved voice defaults, setup progress, and fetched connections/commands context where available. This is the recommended approach.

3. Keep the current draft-only model and just reset less often.
   This is insufficient because refresh/resume still loses prior step choices.

**Chosen Design**

Use a frontend-only derived summary path:

- Keep `setupReviewSummaryDraft` for in-session edits during setup.
- Add a derived helper that builds a fallback handoff summary from saved setup state and currently loaded persona defaults when the draft is incomplete or stale.
- Use that derived summary when completing setup and when resuming into the `test` step without an in-memory draft.
- Wrap the `connections` tab with the existing handoff renderer so the summary appears for that landing target too.
- Extend the handoff card primary CTA logic so `test-lab` maps to "Open Test Lab" instead of falling back to the profiles action.

**Testing**

- Add route coverage for a resumed `test` step completing setup with a derived summary.
- Add route coverage proving the handoff card renders when the post-setup target tab is `connections`.
- Add component coverage for the `test-lab` primary CTA label and action.

**Risk**

Low. The changes are isolated to Persona Garden setup UI state and handoff rendering. The main risk is deriving an incomplete summary from persisted state; tests should lock in the expected fallback behavior.
