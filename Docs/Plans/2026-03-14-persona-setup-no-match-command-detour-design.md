# Persona Setup No-Match Command Detour Design

**Date:** 2026-03-14

## Goal

When assistant setup reaches `Test and finish` and a dry-run returns `no direct command matched`, let the user create a saved command from that phrase without abandoning setup. After saving, return them to the setup test step with the phrase restored so they can confirm the same phrase now matches.

## Problem

The current setup test step can explain `dry_run_no_match`, but it cannot recover the user forward. The route already supports drafting commands from Test Lab, but setup gating hides the normal `Commands` tab whenever setup is required. The existing “rerun after save” flow also assumes a known command id and only supports editing an existing command, not creating a new one during setup.

## Constraints

- Setup must remain persona-scoped and `in_progress` until the user completes the test step.
- The solution should reuse the existing command draft flow where practical.
- This slice should stay frontend-only.
- The user should return to the setup test step explicitly after save, with the unmatched phrase restored.

## Recommended Approach

Use a route-owned setup detour state that temporarily suspends the setup overlay, opens `Commands` with the unmatched phrase drafted, and resumes the wizard after a successful save.

## Architecture

### 1. Route-Owned Setup Command Detour

Add route state in `sidepanel-persona.tsx`:

```ts
type SetupCommandDetour = {
  phrase: string
  returnStep: "test"
}
```

This state is distinct from:

- `draftCommandPhrase`
- `rerunAfterSaveCommandId`
- `lastTestLabPhrase`

The route also keeps a persistent `setupNoMatchPhrase: string | null` so the dry-run phrase survives after `CommandsPanel` consumes the initial draft payload.

### 2. Setup Gating Escape Hatch

The setup overlay remains the default while `personaSetupWizard.isSetupRequired` is true, except when the route has an active setup command detour. In that case, the route renders the normal tab surface and switches to `Commands` initially so the drafted command is immediately visible.

This is a controlled exception, not setup completion.

### 3. Source-Aware Command Drafts

The existing command draft path is extended with source metadata:

```ts
type CommandDraftSource = "test_lab" | "setup_no_match"
```

`CommandsPanel` uses this source to render the correct draft banner copy:

- Test Lab: existing message
- Setup no-match: `Drafted from assistant setup. Save this command, then return to finish setup.`

### 4. Dedicated Save Callback

`CommandsPanel` gains a dedicated callback for successful saves from a fresh draft flow:

```ts
onCommandSaved?: (savedCommandId: string, context: { fromDraft: boolean }) => void
```

The route uses this callback only for setup detours. It does not rely on `rerunAfterSaveCommandId`, because new command ids are unknown before save.

On successful save during an active setup detour:

- clear the setup detour active flag
- restore the setup overlay
- return to `current_step = "test"` without changing backend setup metadata
- restore the saved unmatched phrase into the setup test step
- set a small route-owned note like `Command saved. Run the same phrase again to confirm setup.`

This callback only auto-returns when the saved command came from the setup-created draft flow. Editing an unrelated command while the detour is active should not bounce the user back unexpectedly.

## UX Behavior

### Setup Test Step

For `dry_run_no_match`, `SetupTestAndFinishStep` shows:

- existing no-match explanation
- primary action: `Create command from this phrase`
- secondary fallback guidance to try live session instead

### Commands During Setup Detour

The Commands tab shows:

- the draft phrase prefilled through the existing draft path
- a setup-specific banner explaining the user will return to setup after save

### Resume To Setup

After save:

- route re-enters setup overlay
- current step is `test`
- dry-run textarea is prefilled with the original phrase
- success note appears once:
  - `Command saved. Run the same phrase again to confirm setup.`

No auto-rerun in V1. Confirmation stays explicit.

## Edge Cases

- If the user changes tabs manually during the detour, keep the detour state until they save the setup-created draft or reset/rerun setup.
- If the user edits or saves an unrelated command while the detour is active, do not auto-return to setup. Only the setup-created draft save should resume the wizard.
- If the user resets or reruns setup while the detour is active, clear:
  - `setupCommandDetour`
  - `setupNoMatchPhrase`
  - the one-shot setup success note
- Existing Test Lab draft flows remain unchanged.

## Testing Strategy

### Component

`SetupTestAndFinishStep.test.tsx`

- `dry_run_no_match` renders `Create command from this phrase`

### Route

`sidepanel-persona.test.tsx`

- clicking the no-match action exits the setup overlay into `Commands`
- commands render the setup-specific draft banner
- saving returns to setup overlay at `test`
- the unmatched phrase is restored into the dry-run textarea
- reset/rerun clears the pending detour state

## Out of Scope

- Auto-rerunning the dry-run after command save
- Backend setup metadata changes
- Reusing this detour for live-session failures
