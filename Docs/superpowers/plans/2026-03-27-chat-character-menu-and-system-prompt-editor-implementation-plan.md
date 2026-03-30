# Chat Character Menu And System Prompt Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the `/chat` assistant picker to a searchable favorites-aware menu with a pinned actor action, and add a compact prompt editor modal that edits the effective conversation system prompt without breaking existing template semantics.

**Architecture:** Keep the current shared toolbar controls and improve them in place. `AssistantSelect` becomes a richer `Dropdown`-based assistant menu with search, character favorites, persona tabs, and a footer actor action. `PromptSelect` gains a small modal backed by shared system-prompt helper logic so its reset and override behavior stays aligned with `CurrentChatModelSettings`.

**Tech Stack:** React, TypeScript, Ant Design `Dropdown` and `Modal`, TanStack Query, Plasmo storage hooks, Vitest, React Testing Library

---

## File Structure

- `apps/packages/ui/src/components/Common/system-prompt-utils.ts`
  Purpose: shared helper functions for resolving selected-template content, effective prompt content, and redundant override normalization.
- `apps/packages/ui/src/components/Common/__tests__/system-prompt-utils.test.ts`
  Purpose: lock the prompt-state rules so `PromptSelect` and `CurrentChatModelSettings` cannot drift.
- `apps/packages/ui/src/components/Common/PromptSelect.tsx`
  Purpose: keep prompt selection behavior and add the small system-prompt editor modal.
- `apps/packages/ui/src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx`
  Purpose: prove the modal opens with the effective prompt, saves through the setter, resets correctly, and shows override-active copy.
- `apps/packages/ui/src/components/Common/AssistantSelect.tsx`
  Purpose: upgrade the toolbar assistant menu to use `Dropdown`, search, character favorites, personas, and a pinned actor action.
- `apps/packages/ui/src/components/Common/__tests__/AssistantSelect.tabs.test.tsx`
  Purpose: keep existing tab coverage and extend it for richer menu behavior where sensible.
- `apps/packages/ui/src/components/Common/__tests__/AssistantSelect.behavior.test.tsx`
  Purpose: verify search, favorite toggles, favorite-first ordering, persona access, and actor footer dispatch.
- `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`
  Purpose: thread live `systemPrompt` state and setter into `PromptSelect`.
- `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
  Purpose: pass `systemPrompt` and `setSystemPrompt` into `ComposerToolbar`.
- `apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`
  Purpose: update stale shared-control mocks so toolbar tests still reflect the current control contract.
- `apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx`
  Purpose: reuse shared prompt reset helper so settings and prompt modal share the same semantics.

## Task 1: Extract Shared System Prompt State Helpers

**Files:**
- Create: `apps/packages/ui/src/components/Common/system-prompt-utils.ts`
- Create: `apps/packages/ui/src/components/Common/__tests__/system-prompt-utils.test.ts`
- Modify: `apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx`

- [ ] **Step 1: Write the failing helper tests**

Create `apps/packages/ui/src/components/Common/__tests__/system-prompt-utils.test.ts` covering:

1. `resolveSelectedSystemPromptContent` returns template content and falls back to `""` on missing record or lookup failure.
2. `resolveEffectiveSystemPromptState` returns template content when `systemPrompt` is empty and a template is selected.
3. `resolveEffectiveSystemPromptState` treats non-empty `systemPrompt` as the active override.
4. `normalizeSystemPromptOverrideValue` returns `""` when the draft equals the selected template content.

```ts
await expect(
  resolveEffectiveSystemPromptState({
    selectedSystemPrompt: "prompt-1",
    systemPrompt: "",
    getPromptByIdFn: async () => ({ id: "prompt-1", content: "Template body" } as any)
  })
).resolves.toMatchObject({
  templateContent: "Template body",
  effectiveContent: "Template body",
  overrideActive: false
})
```

- [ ] **Step 2: Run the helper test to verify it fails**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/system-prompt-utils.test.ts --reporter=verbose
```

Expected: FAIL because the helper module does not exist yet.

- [ ] **Step 3: Implement the shared helper module**

Create `apps/packages/ui/src/components/Common/system-prompt-utils.ts` with focused helpers:

- `resolveSelectedSystemPromptContent(selectedSystemPrompt, getPromptByIdFn?)`
- `resolveEffectiveSystemPromptState({ selectedSystemPrompt, systemPrompt, getPromptByIdFn? })`
- `normalizeSystemPromptOverrideValue({ draft, templateContent })`

Keep the helpers string-focused and side-effect free.

- [ ] **Step 4: Reuse the helper in `CurrentChatModelSettings`**

Update `apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx` so `resetSystemPrompt` delegates to `resolveSelectedSystemPromptContent(...)` instead of duplicating its own lookup logic.

- [ ] **Step 5: Re-run the helper test**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/system-prompt-utils.test.ts --reporter=verbose
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/packages/ui/src/components/Common/system-prompt-utils.ts \
  apps/packages/ui/src/components/Common/__tests__/system-prompt-utils.test.ts \
  apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx
git commit -m "refactor: share system prompt state helpers"
```

## Task 2: Add The Prompt Editor Modal To `PromptSelect`

**Files:**
- Modify: `apps/packages/ui/src/components/Common/PromptSelect.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`

- [ ] **Step 1: Write the failing prompt modal tests**

Create `apps/packages/ui/src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx` covering:

1. selecting `Edit system prompt` opens the modal
2. with `selectedSystemPrompt="prompt-1"` and `systemPrompt=""`, the textarea opens with the template content
3. saving edited text calls `setSystemPrompt("new text")`
4. saving text equal to the template content calls `setSystemPrompt("")`
5. reset restores template content when a template is selected
6. reset falls back to `""` when template lookup fails
7. override-active note renders when `systemPrompt` differs from the selected template content

```tsx
await user.click(screen.getByRole("button", { name: /prompt/i }))
await user.click(await screen.findByRole("menuitem", { name: /edit system prompt/i }))
expect(await screen.findByDisplayValue("Template body")).toBeInTheDocument()
```

Mock `getAllPrompts` and `getPromptById` directly in this test.

- [ ] **Step 2: Run the prompt modal test to verify it fails**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx --reporter=verbose
```

Expected: FAIL because `PromptSelect` does not yet expose the modal action or accept the new props.

- [ ] **Step 3: Extend `ComposerToolbar` and `PlaygroundForm` props**

Thread `systemPrompt` and `setSystemPrompt` from `PlaygroundForm` into `ComposerToolbar`, then into `PromptSelect`.

Keep the prop names literal:

- `systemPrompt: string`
- `setSystemPrompt: (prompt: string) => void`

- [ ] **Step 4: Implement the minimal modal in `PromptSelect`**

Update `PromptSelect.tsx` to:

- accept `systemPrompt` and `setSystemPrompt`
- keep the existing prompt groups and search
- add an `Edit system prompt` action within the dropdown
- open a compact modal with textarea, save, cancel, and reset
- initialize draft from `resolveEffectiveSystemPromptState(...)`
- show a small override-active note when a selected template exists and the stored override differs from the template content
- normalize saves through `normalizeSystemPromptOverrideValue(...)`

Use an Ant Design modal pattern consistent with existing local modal usage in this codebase.

- [ ] **Step 5: Update toolbar mocks**

Adjust `apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx` so it mocks `AssistantSelect` instead of the stale `CharacterSelect`, and so the `PromptSelect` mock accepts the broadened prop contract without type errors.

- [ ] **Step 6: Re-run prompt and toolbar tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx \
  src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Common/PromptSelect.tsx \
  apps/packages/ui/src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx \
  apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx
git commit -m "feat: add inline system prompt editor modal"
```

## Task 3: Upgrade `AssistantSelect` To A Rich Toolbar Menu

**Files:**
- Modify: `apps/packages/ui/src/components/Common/AssistantSelect.tsx`
- Modify: `apps/packages/ui/src/components/Common/__tests__/AssistantSelect.tabs.test.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/AssistantSelect.behavior.test.tsx`

- [ ] **Step 1: Write the failing assistant menu tests**

Create `apps/packages/ui/src/components/Common/__tests__/AssistantSelect.behavior.test.tsx` covering:

1. opening the dropdown reveals a search input
2. typing filters visible character options
3. favoriting a character does not select it
4. favorited characters render ahead of non-favorites in the characters tab
5. personas remain accessible from the personas tab
6. clicking the actor footer dispatches `tldw:open-actor-settings`
7. outside click or escape closes the menu

Use mocked `tldwClient.listAllCharacters`, `tldwClient.listPersonaProfiles`, `useSelectedAssistant`, and `useStorage("favoriteCharacters", [])`.

- [ ] **Step 2: Run the assistant menu tests to verify they fail**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  src/components/Common/__tests__/AssistantSelect.behavior.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the current assistant menu has no search, favorites, or actor footer.

- [ ] **Step 3: Implement the richer `AssistantSelect` menu**

Update `AssistantSelect.tsx` to:

- switch the dropdown variant to Ant Design `Dropdown` plus `popupRender`
- add search input with autofocus on open
- filter entries within the active tab
- persist character favorites in `favoriteCharacters`
- render character star toggles with `mousedown` and `click` propagation guards
- keep personas in their own tab
- add a pinned footer button that dispatches `tldw:open-actor-settings` and closes the menu

Do not bring over unrelated identity actions from `CharacterSelect`.

- [ ] **Step 4: Re-run the assistant tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  src/components/Common/__tests__/AssistantSelect.behavior.test.tsx \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/AssistantSelect.tsx \
  apps/packages/ui/src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  apps/packages/ui/src/components/Common/__tests__/AssistantSelect.behavior.test.tsx
git commit -m "feat: restore rich assistant picker menu"
```

## Task 4: Run Final Targeted Verification

**Files:**
- Modify: `Docs/superpowers/plans/2026-03-27-chat-character-menu-and-system-prompt-editor-implementation-plan.md`
- Modify: `IMPLEMENTATION_PLAN_chat_character_menu_and_system_prompt_editor.md`

- [ ] **Step 1: Run the full touched UI test set**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/Common/__tests__/system-prompt-utils.test.ts \
  src/components/Common/__tests__/PromptSelect.system-prompt-modal.test.tsx \
  src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  src/components/Common/__tests__/AssistantSelect.behavior.test.tsx \
  src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 2: Run Bandit on the touched scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  apps/packages/ui/src/components/Common \
  apps/packages/ui/src/components/Option/Playground \
  -f json -o /tmp/bandit_chat_character_menu_and_prompt_editor.json
```

Expected: JSON report written with no new findings in the touched scope.

- [ ] **Step 3: Mark both plan files complete**

Update this plan and `IMPLEMENTATION_PLAN_chat_character_menu_and_system_prompt_editor.md` with final statuses and verification notes before reporting back.
