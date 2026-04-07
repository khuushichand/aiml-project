# Chat Character Menu And System Prompt Editor Design

**Goal:** Restore the expected `/chat` toolbar behavior by making the character button open a searchable assistant menu with favorites and a bottom actor entry, and extend the prompt picker with a compact modal for viewing and editing the live conversation system prompt.

## Problem

Two recent UI paths no longer match user expectations:

- the `/chat` character control uses the newer `AssistantSelect` dropdown, which lacks the richer searchable menu behavior the older character control had
- the prompt picker only selects stored prompts and does not provide a direct way to inspect or edit the active conversation system prompt inline

The user wants the character control to keep persona access, keep favorites, and expose actor settings as a bottom action inside the same menu. The user also wants prompt editing to happen in a small dedicated modal instead of forcing a trip into the larger chat settings surface.

## Desired Behavior

### Character control

The `/chat` character button should:

- open a searchable assistant menu on click
- preserve access to both characters and personas
- support character favorites with visible star toggles
- keep an actor/settings action pinned at the bottom of the menu
- dispatch the existing `tldw:open-actor-settings` event from that bottom action

The toolbar control should not:

- regress into a plain popout launcher
- pull in unrelated identity-management actions from the older character picker

### Prompt control

The prompt picker should:

- keep its existing prompt selection behavior
- expose an `Edit system prompt` action in the menu
- open a small modal with the current live conversation system prompt
- allow save, cancel, and reset

The prompt editor should follow the existing conversation settings semantics:

- saving updates the live `systemPrompt` override
- editing does not silently remove the selected prompt template id
- reset restores the selected template content when a template is active
- reset falls back to the default empty prompt when no template is active
- when a template remains selected but the live system prompt has been edited, the modal should clearly indicate that a conversation-level override is active

## Approach

### 1. Upgrade `AssistantSelect` instead of reusing `CharacterSelect`

The older `CharacterSelect` already has search, favorites, and the actor footer, but it also bundles identity-management and character-management actions that are too broad for the `/chat` toolbar.

The recommended change is to keep `AssistantSelect` as the shared toolbar control and extend it with:

- search input
- persisted character favorites using the existing `favoriteCharacters` storage key
- richer character row rendering with star toggles
- the pinned actor action at the bottom

This keeps the change scoped to the current toolbar control instead of reintroducing the larger legacy menu.

The current `AssistantSelect` popup shell is a plain absolute-positioned panel. The upgrade should move to the same `Dropdown` and `popupRender` pattern already used by `PromptSelect` and the legacy `CharacterSelect`, so the richer menu inherits stable click-away, focus, and keyboard-dismiss behavior instead of layering more interaction onto the bespoke popup.

### 2. Keep personas in the same control

Personas should remain reachable from the same assistant menu rather than being dropped in favor of character parity.

The control should keep its current split between characters and personas, using the existing tab structure. Search should filter within the active tab. Favorites apply only to characters, matching the current stored favorite model.

Favorite star toggles must not also trigger character selection. The implementation should preserve the same event-guard pattern as the legacy character menu by stopping propagation on the favorite affordance.

### 3. Pin the actor action at the bottom

The actor action should not scroll away with the result list.

The menu layout should therefore become:

- search input
- tabs
- scrollable results region
- fixed footer action for actor/settings

The footer action should dispatch the existing `tldw:open-actor-settings` event and then close the menu.

### 4. Add a compact prompt editor modal to `PromptSelect`

`PromptSelect` should gain enough state to edit the live conversation system prompt without taking over the full chat settings UI.

The component should receive:

- the current `systemPrompt`
- a setter for `systemPrompt`
- optionally the selected prompt record or a way to derive reset content from the selected prompt id

The modal should:

- initialize its draft from the effective current system prompt
- save through the same `setSystemPrompt(...)` path already used elsewhere
- reset to the selected prompt content when a template is active
- otherwise reset to `""`
- show a small override status note when a selected template exists and the live system prompt differs from the template content

This preserves the existing model where `selectedSystemPrompt` identifies the template and `systemPrompt` holds the current conversation-level override.

Reset behavior should share the same semantics as `CurrentChatModelSettings`. If the selected prompt id cannot be resolved because the record is missing or lookup fails, reset should fall back to `""` rather than diverging between the two editors. Prefer a shared helper over duplicating this lookup logic.

The effective prompt rule must match chat send behavior:

- if `systemPrompt` is non-empty, it is the active conversation-level override
- otherwise, when `selectedSystemPrompt` resolves to a prompt, that prompt content is the active prompt
- otherwise, the active prompt is `""`

When saving from the modal while a template is selected, saving content that exactly matches the selected template should clear the override back to `""` instead of persisting a redundant conversation-level override.

### 5. Keep prompt selection behavior unchanged

Selecting a system prompt from the picker should continue to:

- mark that template as selected
- leave quick-prompt handling unchanged

The new modal is additive. It is not a replacement for prompt selection and should not change existing prompt library behavior.

## Files

- Modify: `apps/packages/ui/src/components/Common/AssistantSelect.tsx`
- Modify: `apps/packages/ui/src/components/Common/PromptSelect.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`
- Add or modify tests in `apps/packages/ui/src/components/Common/__tests__/`
- Update toolbar tests in `apps/packages/ui/src/components/Option/Playground/__tests__/`

## Testing

Write tests first for:

1. `AssistantSelect` opens a searchable menu and filters visible character options.
2. `AssistantSelect` can toggle a character favorite and renders favorite-first behavior.
3. `AssistantSelect` still exposes persona options.
4. `AssistantSelect` footer dispatches `tldw:open-actor-settings`.
5. `PromptSelect` exposes `Edit system prompt`.
6. `PromptSelect` opens the modal with the current live system prompt.
7. Saving from the modal updates the live system prompt through the supplied setter.
8. Reset restores selected template content when a template is active.
9. Clicking the favorite star does not also select the character row.
10. The assistant menu closes correctly on outside click and keyboard dismissal.
11. Reset falls back to `""` when the selected template id cannot be resolved.
12. The prompt editor modal shows override-active copy when the selected template and live system prompt differ.
13. Opening the prompt editor with a selected template and no stored override shows the template content rather than a blank draft.
14. Saving text equal to the selected template clears the conversation-level override instead of storing duplicate prompt text.

Regression verification:

- existing composer toolbar tests still pass after updating stale mocks
- prompt selection for system prompts and quick prompts remains unchanged

## Risks

- Reimplementing favorites inside `AssistantSelect` can drift from the older `CharacterSelect` if favorite matching logic is copied carelessly.
- Prompt reset behavior can become inconsistent if the modal derives its reset value differently from `CurrentChatModelSettings`.

## Recommendation

Proceed with a focused enhancement:

- enrich `AssistantSelect` to match the expected `/chat` assistant menu behavior
- keep persona access inside the same control
- add a small inline system-prompt editor modal to `PromptSelect`

This addresses the reported regressions without reviving the full legacy character menu or splitting prompt state across multiple sources of truth.
