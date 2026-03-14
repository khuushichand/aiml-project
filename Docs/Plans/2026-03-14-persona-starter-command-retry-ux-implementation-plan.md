# Persona Starter Command Retry UX Implementation Plan

**Goal:** Make starter-command creation failures in assistant setup explicit and easy to recover from without leaving the commands step.

**Architecture:** Keep the work frontend-only. Reuse the existing step-scoped `commands` error in `sidepanel-persona.tsx`, add clearer retry/skip guidance in `SetupStarterCommandsStep.tsx`, and cover the stay-in-step behavior with focused route tests. Do not add new backend APIs or persistence.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

**Status:** Complete

---

### Stage 1: Add Starter-Step Retry Guidance
**Goal:** Show explicit retry guidance when starter-command creation fails while keeping template, MCP, and skip actions available.

**Success Criteria:**
- The commands step renders the raw failure plus a short recovery hint.
- The existing retry affordances remain clickable after failure.
- Component tests cover the new guidance.

**Tests:**
- `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx`

**Status:** Complete

### Stage 2: Cover Route Behavior For Failed Starter Creation
**Goal:** Verify the route keeps setup on the commands step after a create failure and still allows the user to skip forward.

**Success Criteria:**
- A failed starter-command POST leaves the wizard on `commands`.
- The step-local guidance is visible through the route.
- Skipping after the failure advances to `safety`.

**Tests:**
- `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Status:** Complete

### Stage 3: Run Focused Regression Coverage And Commit
**Goal:** Verify the slice without destabilizing the rest of setup.

**Success Criteria:**
- Focused starter/setup suites pass.
- `git diff --check` is clean.

**Tests:**
- `bunx vitest run src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
- `bunx vitest run src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
- `git diff --check`

**Status:** Complete
