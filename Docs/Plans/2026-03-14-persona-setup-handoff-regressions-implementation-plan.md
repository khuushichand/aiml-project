# Persona Setup Handoff Regressions Implementation Plan

**Goal:** Fix the Persona Garden setup handoff regressions identified in review without widening backend scope.

**Architecture:** Frontend-only. Keep existing setup state ownership in `sidepanel-persona.tsx`, derive a resilient handoff summary from saved persona state when needed, and extend the handoff renderer/CTA mapping to cover all supported target tabs.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

**Status:** In Progress

---

### Stage 1: Lock In The Broken Behaviors With Tests
**Goal:** Add focused failing tests for the stale summary fallback and missing handoff rendering cases.

**Success Criteria:**
- A route test fails until a resumed `test` step can complete with a derived summary instead of route defaults.
- A route test fails until the `connections` landing tab renders the handoff card.
- A component test fails until the `test-lab` primary CTA targets Test Lab.

**Tests:**
- `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx`

**Status:** Not Started

### Stage 2: Implement Minimal Route And Card Fixes
**Goal:** Make the tests pass with the smallest route-level changes.

**Success Criteria:**
- `sidepanel-persona.tsx` derives a stable handoff summary for resume/complete flows.
- The `connections` tab uses `withSetupHandoff`.
- `PersonaSetupHandoffCard` uses a target-aware primary CTA for `test-lab`.

**Tests:**
- Same as Stage 1

**Status:** Not Started

### Stage 3: Verify The Slice And Security Baseline
**Goal:** Prove the regression slice passes cleanly.

**Success Criteria:**
- Focused Vitest suites pass.
- `git diff --check` is clean.
- Bandit on the touched backend/frontend scope reports no new findings in changed files.

**Tests:**
- `bunx vitest run src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
- `git diff --check`
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/PersonaGarden apps/packages/ui/src/routes -f json -o /tmp/bandit_persona_setup_handoff_regressions.json`

**Status:** Not Started
