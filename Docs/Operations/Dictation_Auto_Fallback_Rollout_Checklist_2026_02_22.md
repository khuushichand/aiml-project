# Dictation Auto-Fallback Rollout Checklist (2026-02-22)

## Scope
- Surface: WebUI `/chat` Playground and extension sidepanel chat.
- Shared behavior: `auto | server | browser` dictation strategy with server error classification.
- Flag: `dictation_auto_fallback` (default behavior gate for `auto` mode resolution).

## Preconditions
- [ ] Stage 1-5 tests are green in CI for the release candidate.
- [ ] Extension e2e fallback suite passes:
  - `apps/extension/tests/e2e/sidepanel-dictation-fallback.spec.ts`
- [ ] WebUI `/chat` integration tests pass:
  - `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx`
- [ ] Taxonomy coverage validated for at least:
  - fallback-allowed: `provider_unavailable`
  - fallback-disallowed: `quota_error`

## Ramp Plan
1. **Phase 0 (internal only, 24h)**
   - Keep `dictation_auto_fallback` disabled by default.
   - Enable for internal QA accounts/workspaces only.
   - Verify no new blocker regressions in chat submission or speech controls.
2. **Phase 1 (10% of eligible users, 24-48h)**
   - Enable `dictation_auto_fallback` for 10% of users with server STT enabled.
   - Hold if rollback criteria are met.
3. **Phase 2 (50% of eligible users, 48h)**
   - Increase to 50% after Phase 1 passes success gates.
4. **Phase 3 (100%)**
   - Full rollout after Phase 2 stays within error budget for 48h.

## Success Metrics
- Reliability:
  - No increase >10% in dictation session failures vs pre-rollout baseline.
  - No increase >5% in "stuck dictation state" UI incidents (cannot re-start after stop/error).
- UX outcome:
  - For fallback-allowed classes, browser dictation starts successfully on next toggle in >=95% of attempts.
  - For fallback-disallowed classes, no unintended browser fallback.
- Safety:
  - No auth/quota errors misclassified as fallback-allowed classes.
  - No transcript payloads or audio bytes logged in diagnostics/console.

## Rollback Criteria
- Immediate rollback to previous behavior if any occurs:
  - Fallback is triggered for `auth_error` or `quota_error`.
  - Dictation toggle becomes unusable for >2% of active dictation users in a 1h window.
  - Reproducible regression where transcript insertion fails after successful transcription.
  - Critical extension/runtime failure tied to `tldw:upload` dictation path.

## Rollback Procedure
1. Disable `dictation_auto_fallback` rollout (set to 0% / off).
2. Keep explicit user override paths (`server` / `browser`) unchanged.
3. Announce incident in release channel with:
   - first observed timestamp,
   - impacted surface(s),
   - rollback completion timestamp.
4. Open follow-up fix issue with:
   - failing error class and sample status payload (sanitized),
   - reproduction steps,
   - target patch + re-enable conditions.

## Exit Criteria
- [ ] 48h at 100% rollout with no rollback triggers.
- [ ] Support/on-call confirms no unresolved P1/P2 dictation regressions.
- [ ] Release notes updated with fallback behavior and user-facing implications.
