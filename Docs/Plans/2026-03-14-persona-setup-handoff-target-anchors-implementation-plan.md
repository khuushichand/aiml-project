# Persona Setup Handoff Target Anchors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make post-setup handoff actions in Persona Garden land on the exact section the user needs in Commands, Connections, Profiles, and Test Lab instead of only switching tabs.

**Architecture:** Keep the slice frontend-only. Extend the route handoff action model with typed section targets and a replayable focus-request token, then pass panel-specific focus requests into Commands, Connections, Profile/Assistant Defaults, and Test Lab. Each panel owns its refs, scroll/focus behavior, and transient highlight.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

---

### Task 1: Add Route-Level Handoff Target Requests

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing route tests**

Add route coverage for the new target-aware behavior:

```tsx
it("keeps the handoff visible and issues a focus request for same-tab command actions", async () => {
  renderPersonaGardenOnCommandsWithSetupHandoff({
    recommendedAction: "add_command"
  })

  await user.click(screen.getByRole("button", { name: "Open Commands" }))

  expect(screen.getByTestId("persona-setup-handoff-card")).toBeInTheDocument()
  expect(screen.getByTestId("persona-commands-name-input")).toHaveFocus()
})
```

Add cross-tab coverage too:

```tsx
it("retargets the handoff to connections and focuses the connection form", async () => {
  renderPersonaGardenWithSetupHandoffOnProfiles({
    recommendedAction: "add_connection"
  })

  await user.click(screen.getByRole("button", { name: "Open Connections" }))

  expect(screen.getByTestId("persona-setup-handoff-card")).toBeInTheDocument()
  expect(screen.getByTestId("persona-connections-name-input")).toHaveFocus()
})
```

Also add a guard proving `try_live` still just opens Live without a section-focus
request.

**Step 2: Run the targeted route tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "handoff visible and issues a focus request|retargets the handoff to connections|try_live"
```

Expected: FAIL because the route only opens tabs today.

**Step 3: Add the target request model in the route**

In `sidepanel-persona.tsx`, add typed section targets and a replayable request
token:

```ts
type SetupHandoffSectionTarget =
  | { tab: "commands"; section: "command_form" | "command_list" }
  | { tab: "connections"; section: "connection_form" | "saved_connections" }
  | { tab: "profiles"; section: "assistant_defaults" | "confirmation_mode" }
  | { tab: "test-lab"; section: "dry_run_form" }

type SetupHandoffFocusRequest = {
  tab: SetupHandoffSectionTarget["tab"]
  section: SetupHandoffSectionTarget["section"]
  token: number
}
```

Add:

```ts
const [setupHandoffFocusRequest, setSetupHandoffFocusRequest] =
  React.useState<SetupHandoffFocusRequest | null>(null)
const setupHandoffFocusTokenRef = React.useRef(0)
```

Replace the current `openSetupHandoffTab(tab)` logic with a target-aware helper
that:

- emits the existing `handoff_action_clicked` analytics event
- switches tabs as needed
- preserves the handoff for same-tab actions
- retargets the handoff for cross-tab actions
- stores a section request when the action has a concrete destination

**Step 4: Re-run the targeted route tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "handoff visible and issues a focus request|retargets the handoff to connections|try_live"
```

Expected: still FAIL until the destination panels consume the request.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder commit -m "feat: add setup handoff target requests"
```

### Task 2: Add Commands Panel Target Contract

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`

**Step 1: Write the failing Commands panel tests**

Add focused panel tests for the new props:

```tsx
it("focuses the command name input for command_form requests", async () => {
  render(
    <CommandsPanel
      selectedPersonaId="garden-helper"
      selectedPersonaName="Garden Helper"
      isActive
      handoffFocusRequest={{ section: "command_form", token: 1 }}
    />
  )

  expect(screen.getByTestId("persona-commands-name-input")).toHaveFocus()
})
```

Also add:

- `command_list` focuses the first command row when commands exist
- `command_list` falls back to the form when commands are empty
- a newer token replays the highlight/focus

**Step 2: Run the targeted Commands tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx -t "command_form requests|command_list focuses|falls back to the form|replays"
```

Expected: FAIL because `CommandsPanel` does not accept handoff requests.

**Step 3: Add the minimal panel contract**

In `CommandsPanel.tsx`, add props:

```ts
handoffFocusRequest?: {
  section: "command_form" | "command_list"
  token: number
} | null
```

Add refs for:

- command list container / first command row
- empty-state container
- command form root
- command name input

React to fresh tokens with an effect that:

- scrolls the chosen section into view
- focuses the best control
- sets a short-lived highlight state

Keep the fallback rules small:

- `command_list` with rows -> first row
- `command_list` without rows -> command form

**Step 4: Re-run the targeted Commands tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx -t "command_form requests|command_list focuses|falls back to the form|replays"
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder add apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder commit -m "feat: add commands handoff targets"
```

### Task 3: Add Connections Panel Target Contract

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx`

**Step 1: Write the failing Connections panel tests**

Add tests that prove:

- `connection_form` focuses `persona-connections-name-input`
- `saved_connections` focuses the first saved connection row
- `saved_connections` falls back to the form when the list is empty

Example:

```tsx
it("focuses the connection form for connection_form requests", async () => {
  render(
    <ConnectionsPanel
      selectedPersonaId="garden-helper"
      selectedPersonaName="Garden Helper"
      isActive
      handoffFocusRequest={{ section: "connection_form", token: 1 }}
    />
  )

  expect(screen.getByTestId("persona-connections-name-input")).toHaveFocus()
})
```

**Step 2: Run the targeted Connections tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx -t "connection_form requests|saved_connections focuses|falls back to the form"
```

Expected: FAIL because `ConnectionsPanel` has no target-aware focus contract.

**Step 3: Add the minimal panel contract**

In `ConnectionsPanel.tsx`, add:

```ts
handoffFocusRequest?: {
  section: "connection_form" | "saved_connections"
  token: number
} | null
```

Add refs for:

- connection form root
- name input
- saved-connections container / first row

Use the same token-driven effect pattern as `CommandsPanel`.

**Step 4: Re-run the targeted Connections tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx -t "connection_form requests|saved_connections focuses|falls back to the form"
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder add apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder commit -m "feat: add connections handoff targets"
```

### Task 4: Add Profiles And Test Lab Target Contracts

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx`

**Step 1: Write the failing panel tests**

Add tests that prove:

- `confirmation_mode` focuses the confirmation mode select
- `assistant_defaults` focuses the defaults panel root
- `dry_run_form` focuses `persona-test-lab-heard-input`

Example:

```tsx
it("focuses confirmation mode for setup handoff requests", async () => {
  render(
    <AssistantDefaultsPanel
      selectedPersonaId="garden-helper"
      selectedPersonaName="Garden Helper"
      isActive
      handoffFocusRequest={{ section: "confirmation_mode", token: 1 }}
    />
  )

  expect(
    screen.getByLabelText("Confirmation mode")
  ).toHaveFocus()
})
```

**Step 2: Run the targeted panel tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx -t "confirmation mode|assistant defaults|dry_run_form"
```

Expected: FAIL because these panels do not accept target props.

**Step 3: Add the minimal target props**

In `AssistantDefaultsPanel.tsx`, add:

```ts
handoffFocusRequest?: {
  section: "assistant_defaults" | "confirmation_mode"
  token: number
} | null
```

Add refs for:

- panel root
- confirmation mode select

In `ProfilePanel.tsx`, thread the target through to `AssistantDefaultsPanel`.

In `TestLabPanel.tsx`, add:

```ts
handoffFocusRequest?: {
  section: "dry_run_form"
  token: number
} | null
```

and focus the heard-text textarea on fresh requests.

**Step 4: Re-run the targeted panel tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx -t "confirmation mode|assistant defaults|dry_run_form"
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder add apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder commit -m "feat: add profile and test lab handoff targets"
```

### Task 5: Wire Handoff Actions To Concrete Targets And Verify The Full Flow

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing integration tests**

Add route tests that prove action mapping is specific:

- `Review safety defaults` focuses confirmation mode
- `Open connections` focuses the form when the frozen summary says
  `connection.mode === "skipped"`
- `Open connections` focuses saved connections when the frozen summary says
  `connection.mode === "created"` or `"available"`
- `Open Test Lab` focuses the dry-run input

Example:

```tsx
it("opens saved connections for handoff review when a connection already exists", async () => {
  renderPersonaGardenWithCompletedSetupHandoff({
    targetTab: "connections",
    reviewSummary: {
      starterCommands: { mode: "added", count: 2 },
      confirmationMode: "destructive_only",
      connection: { mode: "created", name: "Slack" }
    }
  })

  await user.click(screen.getByRole("button", { name: "Open connections" }))

  expect(screen.getByTestId("persona-connections-row-slack")).toHaveFocus()
})
```

**Step 2: Run the targeted integration tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "Review safety defaults|Open connections|Open Test Lab"
```

Expected: FAIL until the action mapping is fully wired.

**Step 3: Finish the route/card wiring**

In `sidepanel-persona.tsx`:

- replace the old tab-only callbacks with target-aware callbacks
- map recommended action and review rows to concrete targets
- pass the panel-specific request down only to the active destination panel
- keep `try_live` tab-only

In `PersonaSetupHandoffCard.tsx`:

- keep the visual design
- only adjust callback names/signatures if needed so the route can distinguish
  the concrete actions

**Step 4: Run the focused route suite**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 5: Run the broader Persona Garden frontend regression sweep**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 6: Run final verification**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder diff --check
```

Then run Bandit on the touched frontend scope:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui/src/components/PersonaGarden /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui/src/routes -f json -o /tmp/bandit_persona_handoff_targets.json
```

Expected:

- `git diff --check` clean
- no new Bandit findings in changed source files

**Step 7: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder add apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder commit -m "feat: target setup handoff actions to panel sections"
```
