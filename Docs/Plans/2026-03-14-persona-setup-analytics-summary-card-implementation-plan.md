# Persona Setup Analytics Summary Card Implementation Plan

**Status:** Complete on 2026-03-14.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a compact setup analytics summary card to `Profiles` using the
existing persona setup analytics endpoint.

**Architecture:** Keep this slice frontend-only. Add route-owned setup
analytics state and fetching in `sidepanel-persona.tsx`, pass the typed payload
through `ProfilePanel`, and render a pure `PersonaSetupAnalyticsCard`
component when recorded setup runs exist.

**Tech Stack:** React, TypeScript, Vitest.

---

### Task 1: Add The Setup Analytics Summary Card Component

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/PersonaSetupAnalyticsCard.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupAnalyticsCard.test.tsx`

**Step 1: Write the failing component tests**

Add tests proving:

- the card hides when `summary.total_runs` is `0`
- the card shows loading copy when `loading` is true and no payload exists
- the card renders completion, handoff, and drop-off metrics
- step labels map correctly and unknown/missing drop-off falls back cleanly

Example cases:

```tsx
render(
  <PersonaSetupAnalyticsCard
    analytics={{
      persona_id: "garden-helper",
      summary: { total_runs: 0, completed_runs: 0, completion_rate: 0 },
      recent_runs: []
    }}
  />
)
expect(screen.queryByTestId("persona-setup-analytics-card")).not.toBeInTheDocument()
```

And:

```tsx
render(<PersonaSetupAnalyticsCard loading />)
expect(screen.getByText("Loading setup analytics...")).toBeInTheDocument()
```

**Step 2: Run the focused component test**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaSetupAnalyticsCard.test.tsx
```

Expected: FAIL because the component does not exist yet.

**Step 3: Write the minimal component**

Implement a compact presentational card that:

- accepts `analytics?: PersonaSetupAnalyticsResponse | null`
- accepts `loading?: boolean`
- returns `null` when `total_runs === 0`
- shows a compact loading state only when `loading && !analytics`
- renders:
  - completion rate
  - most common drop-off
  - dry-run completions
  - live-session completions
  - handoff click rate
  - target reached rate
  - first next-step rate

Use a local step-label map:

- `persona` -> `Persona choice`
- `voice` -> `Voice defaults`
- `commands` -> `Starter commands`
- `safety` -> `Safety and connections`
- `test` -> `Test and finish`

Fallback:

- unknown string -> readable title-cased/raw label
- null/empty -> `None yet`

**Step 4: Re-run the focused component test**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaSetupAnalyticsCard.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaSetupAnalyticsCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupAnalyticsCard.test.tsx
git commit -m "feat: add persona setup analytics summary card"
```

### Task 2: Fetch Setup Analytics In The Route And Wire Profiles

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing route tests**

Add route coverage proving:

- `Profiles` fetches `/setup-analytics`
- non-`Profiles` tabs do not fetch `/setup-analytics`
- returned analytics render the card
- zero-run analytics do not render the card

Use the existing fetch mock pattern already used for `/voice-analytics`.

**Step 2: Run the focused route test**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "setup analytics"
```

Expected: FAIL because the route does not fetch or render setup analytics yet.

**Step 3: Add typed route state and fetch**

In `sidepanel-persona.tsx`:

- define a narrow `PersonaSetupAnalyticsResponse` TypeScript type for frontend use
- add:
  - `setupAnalytics`
  - `setupAnalyticsLoading`
- add a route effect that:
  - checks `selectedPersonaId`
  - only fetches when `activeTab === "profiles"`
  - calls `/api/v1/persona/profiles/{persona_id}/setup-analytics?days=30&limit=5`
  - stores payload on success
  - clears payload on persona change or empty persona
  - fails closed on fetch error

In `ProfilePanel.tsx`:

- add optional props for setup analytics payload/loading
- render `PersonaSetupAnalyticsCard` between:
  - `PersonaSetupStatusCard`
  - `AssistantDefaultsPanel`

**Step 4: Re-run the focused route test**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "setup analytics"
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: load persona setup analytics in profiles"
```

### Task 3: Cover I18n And Panel Integration

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx`

**Step 1: Add the failing i18n assertion**

Extend the existing panel i18n test to assert the setup analytics card heading
uses `react-i18next`, for example:

```tsx
expect(
  screen.getByText("sidepanel:personaGarden.profile.setupAnalyticsHeading")
).toBeInTheDocument()
```

Use a mock setup analytics payload in the rendered `ProfilePanel` props so the
card appears.

**Step 2: Run the focused i18n test**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx
```

Expected: FAIL until the card is rendered with translated heading text.

**Step 3: Adjust rendering/test wiring**

Update the test fixture props and, if needed, the card heading key so the card
participates in the existing i18n coverage.

**Step 4: Re-run the focused i18n test**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx
git commit -m "test: cover setup analytics card i18n"
```

### Task 4: Run Final Verification And Close Out

**Files:**
- Modify: `Docs/Plans/2026-03-14-persona-setup-analytics-summary-card-implementation-plan.md`

**Step 1: Run focused frontend verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaSetupAnalyticsCard.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 2: Run a broader Persona Garden regression sweep**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__ src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 3: Run static verification**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder diff --check
```

Then:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui/src/components/PersonaGarden /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui/src/routes -f json -o /tmp/bandit_persona_setup_analytics_summary_card.json
```

Expected:

- `git diff --check` clean
- no new Bandit findings in touched frontend files

**Step 4: Mark the plan complete and commit**

Add a top-line completion note to this plan, then commit the slice.
