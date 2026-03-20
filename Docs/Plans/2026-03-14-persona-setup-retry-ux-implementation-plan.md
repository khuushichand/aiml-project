# Persona Setup Retry UX Implementation Plan

**Goal:** Improve setup failure and retry UX for the two highest-friction setup paths: connection creation in the safety step and test/finish failures in the final step.

**Architecture:** Keep the work frontend-only. Reuse the existing route-owned step error and `setupTestOutcome` state in `sidepanel-persona.tsx`, but make the final step outcome model richer and attach clearer retry/forward actions in the step components. Do not add new backend APIs.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

**Status:** Complete

---

### Stage 1: Make Safety-Step Failure Recovery Explicit
**Goal:** Turn connection-creation failures into step-local retry guidance instead of a plain red banner.

**Success Criteria:**
- The safety step shows a clear connection-specific retry message when connection creation fails.
- The user can correct fields and resubmit without losing the skip path.
- Tests cover the new failure copy and retained continue options.

**Tests:**
- `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx`
- `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Status:** Complete

### Stage 2: Add Structured Test-Step Failure Outcomes
**Goal:** Distinguish dry-run failure, dry-run no-match, live unavailable, and live send failure with explicit next actions.

**Success Criteria:**
- `SetupTestAndFinishStep` accepts a richer test outcome model including live send failure.
- The component renders distinct retry/forward copy for each failure state.
- Route logic maps dry-run and live-send failures into the structured outcome instead of only using step error banners.

**Tests:**
- `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx`
- `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Status:** Complete

### Stage 3: Run Focused Regression Coverage And Commit
**Goal:** Verify the retry UX slice without destabilizing the existing setup flow.

**Success Criteria:**
- Focused setup suites pass.
- Broader Persona Garden setup-related regressions pass.
- `git diff --check` is clean.

**Tests:**
- `bunx vitest run src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
- `bunx vitest run src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
- `git diff --check`

**Status:** Complete
