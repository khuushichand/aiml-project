# Companion Home Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the post-onboarding lightweight landing experience with a shared Companion Home dashboard while preserving hosted mode, first-run onboarding, and sidepanel chat-resume behavior.

**Architecture:** Build a new shared `CompanionHome` shell in `apps/packages/ui`, keep `/` as a wrapper or resolver route instead of blindly redirecting to `/companion`, and extract notifications into shared UI services before binding them into the dashboard. The home shell should aggregate existing Companion, reading, and notes data into typed cards with card-level fallback states and local per-surface layout overrides.

**Tech Stack:** React 18, React Router, Zustand, WXT extension shell, Next.js page wrappers, shared UI package (`@tldw/ui`), `@dnd-kit/react`, Vitest, Testing Library

---

### Task 1: Scaffold the shared Companion Home shell and swap the WebUI post-onboarding branch

**Files:**
- Create: `apps/packages/ui/src/components/Option/CompanionHome/CompanionHomeShell.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/index.ts`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomeShell.test.tsx`
- Modify: `apps/packages/ui/src/routes/option-index.tsx`
- Modify: `apps/packages/ui/src/routes/option-companion.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/core-route-identity.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/option-companion.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("keeps onboarding at / until first run completes", async () => {
  mocks.hasCompletedFirstRun = false
  render(<OptionIndex />)
  expect(screen.getByText("Home Onboarding")).toBeInTheDocument()
})

it("renders Companion Home from / after onboarding", async () => {
  mocks.hasCompletedFirstRun = true
  render(<OptionIndex />)
  expect(await screen.findByTestId("companion-home-shell")).toBeInTheDocument()
})

it("renders the same Companion Home shell on /companion", async () => {
  render(<OptionCompanion />)
  expect(await screen.findByTestId("companion-home-shell")).toBeInTheDocument()
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/routes/__tests__/core-route-identity.test.tsx \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomeShell.test.tsx
```

Expected: FAIL because `CompanionHomeShell` does not exist and `/` still renders `LandingHub`.

**Step 3: Write the minimal implementation**

```tsx
// apps/packages/ui/src/components/Option/CompanionHome/CompanionHomeShell.tsx
export const CompanionHomeShell = ({ surface }: { surface: "options" | "sidepanel" }) => (
  <section data-testid="companion-home-shell">
    <h1>Companion</h1>
    <p>Companion Home placeholder</p>
    <span>{surface}</span>
  </section>
)

// option-index.tsx
if (!hasCompletedFirstRun) return <OnboardingWizard ... />
return (
  <OptionLayout>
    <CompanionHomeShell surface="options" />
  </OptionLayout>
)

// option-companion.tsx
return (
  <RouteErrorBoundary routeId="companion" routeLabel="Companion">
    <OptionLayout>
      <CompanionHomeShell surface="options" />
    </OptionLayout>
  </RouteErrorBoundary>
)
```

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command.

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/CompanionHome \
  apps/packages/ui/src/routes/option-index.tsx \
  apps/packages/ui/src/routes/option-companion.tsx \
  apps/packages/ui/src/routes/__tests__/core-route-identity.test.tsx \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx
git commit -m "feat: scaffold companion home shell"
```

### Task 2: Add route wrappers and preserve sidepanel chat-resume behavior

**Files:**
- Create: `apps/packages/ui/src/routes/sidepanel-home-resolver.tsx`
- Create: `apps/packages/ui/src/routes/__tests__/sidepanel-home-resolver.test.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/routes/route-capabilities.ts`
- Modify: `apps/packages/ui/src/routes/sidepanel-companion.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-chat.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("keeps /companion available even when personalization capability is missing", () => {
  expect(isRouteEnabledForCapabilities("/companion", { hasPersonalization: false } as any)).toBe(true)
})

it("renders chat from sidepanel / when resumable chat exists", async () => {
  mockHasResumableChat(true)
  render(<SidepanelHomeResolver />)
  expect(await screen.findByTestId("sidepanel-chat-root")).toBeInTheDocument()
})

it("renders Companion Home from sidepanel / when no resumable chat exists", async () => {
  mockHasResumableChat(false)
  render(<SidepanelHomeResolver />)
  expect(await screen.findByTestId("companion-home-shell")).toBeInTheDocument()
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts \
  apps/packages/ui/src/routes/__tests__/sidepanel-home-resolver.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx
```

Expected: FAIL because `/companion` is still capability-gated and the sidepanel resolver does not exist.

**Step 3: Write the minimal implementation**

```tsx
// route-capabilities.ts
export const isCompanionAvailable = () => true

// sidepanel-home-resolver.tsx
export default function SidepanelHomeResolver() {
  const hasResume = useHasResumableChat()
  return hasResume ? <SidepanelChat /> : <SidepanelCompanion />
}

// route-registry.tsx
{ kind: "sidepanel", path: "/", element: <SidepanelHomeResolver /> }
```

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command.

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/routes/sidepanel-home-resolver.tsx \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/routes/route-capabilities.ts \
  apps/packages/ui/src/routes/sidepanel-companion.tsx \
  apps/packages/ui/src/routes/sidepanel-chat.tsx \
  apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts \
  apps/packages/ui/src/routes/__tests__/sidepanel-home-resolver.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx
git commit -m "feat: preserve sidepanel chat resume with companion home"
```

### Task 3: Extract a shared notifications domain for parity-critical inbox behavior

**Files:**
- Create: `apps/packages/ui/src/services/notifications.ts`
- Create: `apps/packages/ui/src/services/__tests__/notifications.test.ts`
- Modify: `apps/packages/ui/src/services/companion.ts`
- Modify: `apps/tldw-frontend/pages/notifications.tsx`

**Step 1: Write the failing tests**

```ts
it("lists notifications through shared UI services", async () => {
  mockBgRequest({ items: [{ id: 1, title: "Inbox item" }], total: 1 })
  const result = await listNotifications({ limit: 20, offset: 0 })
  expect(result.items[0]?.id).toBe(1)
})

it("marks notifications read through shared UI services", async () => {
  mockBgRequest({ updated: 1 })
  await expect(markNotificationsRead([1])).resolves.toEqual({ updated: 1 })
})

it("dismisses and snoozes notifications through shared UI services", async () => {
  await dismissNotification(1)
  await snoozeNotification(1, 15)
  expect(bgRequest).toHaveBeenCalledTimes(2)
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/notifications.test.ts \
  apps/packages/ui/src/services/__tests__/companion.test.ts
```

Expected: FAIL because the shared notifications module does not exist and Companion only supports fetch.

**Step 3: Write the minimal implementation**

```ts
export const listNotifications = (params?: { limit?: number; offset?: number }) =>
  bgRequest<NotificationsListResponse>({
    path: `/api/v1/notifications${buildQuery(params || {})}` as any,
    method: "GET"
  })

export const markNotificationsRead = (ids: number[]) =>
  bgRequest<{ updated: number }>({
    path: "/api/v1/notifications/mark-read" as any,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: { ids }
  })
```

Refactor the Next.js notifications page to consume the shared notifications service rather than its private copy.

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command.

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/notifications.ts \
  apps/packages/ui/src/services/__tests__/notifications.test.ts \
  apps/packages/ui/src/services/companion.ts \
  apps/tldw-frontend/pages/notifications.tsx
git commit -m "feat: extract shared notifications domain"
```

### Task 4: Build the Companion Home snapshot aggregator and dedupe rules

**Files:**
- Create: `apps/packages/ui/src/services/companion-home.ts`
- Create: `apps/packages/ui/src/services/__tests__/companion-home.test.ts`
- Modify: `apps/packages/ui/src/services/companion.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Write the failing tests**

```ts
it("aggregates inbox, goals, reading, notes, and activity into a home snapshot", async () => {
  const snapshot = await fetchCompanionHomeSnapshot("options")
  expect(snapshot).toMatchObject({
    inbox: expect.any(Array),
    needsAttention: expect.any(Array),
    resumeWork: expect.any(Array)
  })
})

it("dedupes needs-attention items when a canonical inbox item already exists", async () => {
  const snapshot = await fetchCompanionHomeSnapshot("options")
  expect(snapshot.needsAttention).not.toContainEqual(
    expect.objectContaining({ entityId: "reflection-1" })
  )
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/companion-home.test.ts \
  apps/packages/ui/src/services/__tests__/companion.test.ts
```

Expected: FAIL because `fetchCompanionHomeSnapshot` does not exist.

**Step 3: Write the minimal implementation**

```ts
export async function fetchCompanionHomeSnapshot(surface: "options" | "sidepanel") {
  const [companion, inbox, reading, notes] = await Promise.all([
    fetchCompanionWorkspaceSnapshot().catch(() => null),
    listNotifications({ limit: 20, offset: 0 }).catch(() => ({ items: [], total: 0 })),
    tldwClient.listReadingItems({ page: 1, size: 20 }).catch(() => ({ items: [] })),
    tldwClient.listNotes({ page: 1, results_per_page: 20, include_keywords: false }).catch(() => ({ items: [] }))
  ])

  return buildCompanionHomeSnapshot({ surface, companion, inbox, reading, notes })
}
```

Keep the first pass boring:

- canonical inbox wins
- `Needs Attention` only emits entities not already represented in inbox
- `Resume Work` only includes goals, reading items, and notes/doc entries

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command.

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/companion-home.ts \
  apps/packages/ui/src/services/__tests__/companion-home.test.ts \
  apps/packages/ui/src/services/companion.ts \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts
git commit -m "feat: add companion home snapshot aggregation"
```

### Task 5: Implement the core dashboard cards and degraded states

**Files:**
- Create: `apps/packages/ui/src/components/Option/CompanionHome/CompanionHomePage.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/cards/InboxPreviewCard.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/cards/NeedsAttentionCard.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/cards/ResumeWorkCard.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/cards/GoalsFocusCard.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/cards/RecentActivityCard.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/cards/ReadingQueueCard.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomePage.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/CompanionHome/CompanionHomeShell.tsx`

**Step 1: Write the failing tests**

```tsx
it("shows the setup band and non-personalized cards when personalization is unavailable", async () => {
  mockHomeSnapshot({ personalizationAvailable: false })
  render(<CompanionHomePage surface="options" />)
  expect(await screen.findByTestId("companion-home-setup-band")).toBeInTheDocument()
  expect(screen.getByTestId("companion-home-inbox")).toBeInTheDocument()
})

it("renders the core MVP cards in the default layout", async () => {
  render(<CompanionHomePage surface="options" />)
  expect(await screen.findByTestId("companion-home-resume-work")).toBeInTheDocument()
  expect(screen.getByTestId("companion-home-goals")).toBeInTheDocument()
  expect(screen.getByTestId("companion-home-activity")).toBeInTheDocument()
  expect(screen.getByTestId("companion-home-reading-queue")).toBeInTheDocument()
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomePage.test.tsx
```

Expected: FAIL because the page and card components do not exist.

**Step 3: Write the minimal implementation**

```tsx
export function CompanionHomePage({ surface }: { surface: "options" | "sidepanel" }) {
  const snapshot = useCompanionHomeSnapshot(surface)
  return (
    <section data-testid="companion-home-page">
      <SetupBand snapshot={snapshot} data-testid="companion-home-setup-band" />
      <InboxPreviewCard items={snapshot.inbox} />
      <NeedsAttentionCard items={snapshot.needsAttention} />
      <ResumeWorkCard items={snapshot.resumeWork} />
      <GoalsFocusCard items={snapshot.goals} />
      <RecentActivityCard items={snapshot.activity} />
      <ReadingQueueCard items={snapshot.readingQueue} />
    </section>
  )
}
```

Keep styling and layout simple until tests pass. Do not implement optional cards in this task.

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command.

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/CompanionHome \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomePage.test.tsx
git commit -m "feat: add core companion home cards"
```

### Task 6: Add modular layout persistence and customize-home interactions

**Files:**
- Create: `apps/packages/ui/src/store/companion-home-layout.ts`
- Create: `apps/packages/ui/src/store/__tests__/companion-home-layout.test.ts`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/CustomizeHomeDrawer.tsx`
- Create: `apps/packages/ui/src/components/Option/CompanionHome/__tests__/CustomizeHomeDrawer.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/CompanionHome/CompanionHomePage.tsx`

**Step 1: Write the failing tests**

```ts
it("loads the shared default layout and applies a surface override", async () => {
  const state = useCompanionHomeLayoutStore.getState()
  await state.load("sidepanel")
  expect(state.cards[0]?.id).toBe("inbox-preview")
})

it("prevents removal of system cards but allows core card hide and reorder", async () => {
  render(<CustomizeHomeDrawer surface="options" open />)
  expect(screen.getByText("Inbox Preview")).toBeInTheDocument()
  expect(screen.getByText("Remove")).toHaveAttribute("disabled")
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/store/__tests__/companion-home-layout.test.ts \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CustomizeHomeDrawer.test.tsx
```

Expected: FAIL because the layout store and customization UI do not exist.

**Step 3: Write the minimal implementation**

```ts
const DEFAULT_LAYOUT: CompanionHomeLayout = {
  shared: ["setup-band", "inbox-preview", "needs-attention", "resume-work", "goals", "activity", "reading-queue"],
  overrides: { options: null, sidepanel: null }
}

export const useCompanionHomeLayoutStore = create(...persist(...))
```

```tsx
<DragDropProvider onDragEnd={handleDragEnd}>
  <CustomizeHomeDrawer surface={surface} />
</DragDropProvider>
```

Use a constrained grid:

- system cards: collapsible only
- core/optional cards: hideable, reorderable, size presets only

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command.

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/store/companion-home-layout.ts \
  apps/packages/ui/src/store/__tests__/companion-home-layout.test.ts \
  apps/packages/ui/src/components/Option/CompanionHome/CustomizeHomeDrawer.tsx \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CustomizeHomeDrawer.test.tsx \
  apps/packages/ui/src/components/Option/CompanionHome/CompanionHomePage.tsx
git commit -m "feat: add companion home layout customization"
```

### Task 7: Add copy audits, parity tests, and regression coverage

**Files:**
- Modify: `apps/packages/ui/src/routes/app-route.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/empty.tsx`
- Create: `apps/tldw-frontend/e2e/workflows/companion-home.parity.spec.ts`
- Create: `apps/extension/tests/e2e/companion-home.parity.spec.ts`
- Create: `apps/test-utils/companion-home.contract.ts`
- Create: `apps/test-utils/companion-home.page.ts`
- Create: `apps/test-utils/companion-home.fixtures.ts`
- Modify: `apps/packages/ui/src/routes/__tests__/app-route-not-found.test.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/app-route-companion-message.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("uses home-oriented recovery copy instead of chat-only copy", async () => {
  render(<RouteNotFoundState routeLabel="/missing" kind="options" />)
  expect(screen.getByText("Go Home")).toBeInTheDocument()
})
```

```ts
test("companion home parity", async ({ mountCompanionHome }) => {
  await expect(await mountCompanionHome()).toMatchCompanionHomeContract()
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/routes/__tests__/app-route-not-found.test.tsx \
  apps/packages/ui/src/routes/__tests__/app-route-companion-message.test.tsx
```

Expected: FAIL because copy and parity harness are not updated yet.

**Step 3: Write the minimal implementation**

```tsx
// app-route.tsx
<Link to="/" data-testid="not-found-go-home">Go Home</Link>

// empty.tsx
const bannerHeading = hasCompletedFirstRun
  ? "Open Companion Home or chat after reconnecting"
  : "Finish setup to start using tldw Assistant"
```

Create the shared parity contract using the same layered pattern already used for other WebUI + extension parity suites.

**Step 4: Run the tests to verify they pass**

Run the same `bunx vitest run ...` command, then run the parity harness when the apps are ready.

Suggested parity commands:

```bash
bunx vitest run \
  apps/packages/ui/src/routes/__tests__/app-route-not-found.test.tsx \
  apps/packages/ui/src/routes/__tests__/app-route-companion-message.test.tsx
```

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/companion-home.parity.spec.ts --reporter=line
```

```bash
cd apps/extension && bunx playwright test tests/e2e/companion-home.parity.spec.ts --reporter=line
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/routes/app-route.tsx \
  apps/packages/ui/src/components/Sidepanel/Chat/empty.tsx \
  apps/packages/ui/src/routes/__tests__/app-route-not-found.test.tsx \
  apps/packages/ui/src/routes/__tests__/app-route-companion-message.test.tsx \
  apps/tldw-frontend/e2e/workflows/companion-home.parity.spec.ts \
  apps/extension/tests/e2e/companion-home.parity.spec.ts \
  apps/test-utils/companion-home.contract.ts \
  apps/test-utils/companion-home.page.ts \
  apps/test-utils/companion-home.fixtures.ts
git commit -m "test: add companion home parity and copy coverage"
```

### Task 8: Final verification and handoff

**Files:**
- Verify only the files touched above
- Reference: `Docs/Plans/2026-03-20-companion-home-dashboard-webui-extension-design.md`

**Step 1: Run targeted unit and route suites**

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomeShell.test.tsx \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CompanionHomePage.test.tsx \
  apps/packages/ui/src/components/Option/CompanionHome/__tests__/CustomizeHomeDrawer.test.tsx \
  apps/packages/ui/src/store/__tests__/companion-home-layout.test.ts \
  apps/packages/ui/src/services/__tests__/notifications.test.ts \
  apps/packages/ui/src/services/__tests__/companion-home.test.ts \
  apps/packages/ui/src/routes/__tests__/core-route-identity.test.tsx \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts \
  apps/packages/ui/src/routes/__tests__/sidepanel-home-resolver.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx
```

Expected: PASS.

**Step 2: Run parity and smoke coverage**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/companion-home.parity.spec.ts --reporter=line
cd apps/extension && bunx playwright test tests/e2e/companion-home.parity.spec.ts --reporter=line
```

Expected: PASS.

**Step 3: Run lint only on touched frontend paths if needed**

```bash
cd apps/tldw-frontend && bun run lint
```

Expected: PASS or only unrelated pre-existing findings.

**Step 4: Review the resulting UX manually**

Manual checklist:

- hosted mode still shows hosted landing
- first-run self-host still shows onboarding
- post-onboarding WebUI `/` shows Companion Home
- sidepanel `/` restores chat when resumable chat exists
- sidepanel `/` shows Companion Home when no resumable chat exists
- notifications and `Needs Attention` do not double-count the same entity
- system cards cannot be removed
- surface reset restores the shared default

**Step 5: Commit final polish**

```bash
git add <touched files>
git commit -m "feat: ship companion home dashboard"
```
