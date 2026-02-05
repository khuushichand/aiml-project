# PRD: Chat Page Structural Refactoring (Code Arrangement)

## Objective

Decompose the oversized `PlaygroundForm.tsx` (5500+ lines) into well-scoped components, eliminate JSX duplication, and reorganize control flow to support progressive disclosure. No visual changes -- this PRD focuses purely on code health and component architecture.

---

## Background

The fullscreen chat composer (`PlaygroundForm.tsx`) has grown to 5500+ lines with significant structural problems:
- Lines 5036-5410 (Pro mode toolbar) and lines 5412-5643 (Normal mode toolbar) contain near-identical JSX for the same 18 controls, differing only in minor layout classes
- The textarea block (lines 4791-4986) mixes input handling, slash commands, mentions, collapsed message state, and draft persistence into one inline block
- Adding a new toolbar control currently requires editing two separate JSX blocks in a 5500-line file
- The header mixes concerns (navigation, connection status, chat identity, keyboard shortcuts)

---

## Deliverables

### S1: Extract `ComposerTextarea` Component

**New file**: `apps/packages/ui/src/components/Option/Playground/ComposerTextarea.tsx`
**Modify**: `PlaygroundForm.tsx`

Extract lines 4791-4986 into a self-contained component encapsulating:
- The `<textarea>` element with all event handlers (keydown, focus, blur, paste, composition, select, mouse)
- `SlashCommandMenu` rendering and positioning
- `MentionsDropdown` rendering
- Collapsed message display logic (the `isMessageCollapsed` / `collapsedDisplayMeta` handling)
- Draft saved indicator
- Inner border styling (`rounded-2xl border border-border/70`)

**Props interface**:
```typescript
type ComposerTextareaProps = {
  textareaRef: React.RefObject<HTMLTextAreaElement>
  value: string
  displayValue: string  // collapsed vs full
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  onPaste: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  onFocus: () => void
  placeholder: string
  disabled?: boolean
  isProMode: boolean
  isCollapsed: boolean
  onExpandCollapsed: () => void
  // Slash commands
  showSlashMenu: boolean
  slashCommands: SlashCommandItem[]
  slashActiveIndex: number
  onSlashSelect: (cmd: SlashCommandItem) => void
  onSlashActiveIndexChange: (idx: number) => void
  // Mentions
  showMentions: boolean
  filteredTabs: any[]
  mentionPosition: any
  onMentionSelect: (tab: any) => void
  onMentionsClose: () => void
  // Draft
  draftSaved: boolean
}
```

**Acceptance criteria**:
- PlaygroundForm renders `<ComposerTextarea>` instead of inline textarea block
- All existing textarea behavior (typing, slash commands, mentions, collapsed state, draft indicator) works identically
- No visual changes

---

### S2: Extract Unified `ComposerToolbar` Component

**New file**: `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`
**Modify**: `PlaygroundForm.tsx`

Replace the duplicated Pro mode block (lines 5036-5410) and Normal mode block (lines 5412-5643) with a single `ComposerToolbar` component.

**Key design decision**: The component receives `isProMode: boolean` and uses conditional CSS classes (e.g., `isProMode ? "flex-col gap-2" : "flex-row gap-1"`) rather than duplicating entire JSX trees.

**Props interface** (pass through existing state/callbacks):
```typescript
type ComposerToolbarProps = {
  isProMode: boolean
  isMobile: boolean
  isConnectionReady: boolean
  isSending: boolean
  // Control elements (pre-rendered by PlaygroundForm)
  modelSelectButton: React.ReactNode
  sendControl: React.ReactNode
  attachmentButton: React.ReactNode
  toolsButton: React.ReactNode
  voiceChatButton: React.ReactNode
  mcpControl: React.ReactNode
  modelUsageBadge: React.ReactNode
  // Callbacks
  onToggleTemporaryChat: (next: boolean) => void
  onToggleKnowledgePanel: (tab: string) => void
  onToggleWebSearch: () => void
  onOpenPromptInsert: () => void
  onOpenModelSettings: () => void
  // State
  temporaryChat: boolean
  contextToolsOpen: boolean
  webSearch: boolean
  selectedModel: string | null
  // ... remaining props from existing toolbar rendering
}
```

**Toolbar layout (single component, adaptive)**:
```
Pro mode:
  Row 1: [PromptSelect] [ModelSelect] [CharacterSelect] [MCP]
  Row 2: [ParameterPresets] | [SystemPromptTemplates] [CostEstimation]
  Row 3: [Ephemeral] [Search] [Web] [Tabs] [Files] | [InsertPrompt] [Mic] [TokenBar] [ChatSettings] [Voice] [Attach] [Tools] [Send]
  Row 4: [ConnectionHint] [PersistenceHint]

Normal mode:
  Row 1: [PromptSelect] [ModelSelect] [CharacterSelect] [MCP]
  Row 2: [Ephemeral] [Search] [Web] | [InsertPrompt] [Mic] [TokenBar] [ChatSettings] [Voice] [Attach] [Tools] [Send]
```

Pro-only controls rendered conditionally: `{isProMode && <ParameterPresets />}`, etc.

**Acceptance criteria**:
- ~600 lines of duplicate JSX removed from PlaygroundForm.tsx
- Both Pro and Normal modes render correctly with identical behavior
- Adding a new toolbar control requires only one code change

---

### S3: Extract `ComposerToolbarOverflow` Component

**New file**: `apps/packages/ui/src/components/Option/Playground/ComposerToolbarOverflow.tsx`
**Modify**: `ComposerToolbar.tsx`

Group toolbar controls into three visibility tiers:

| Tier | Controls | Visibility |
|------|----------|-----------|
| **1 - Always visible** | Model selector, Send/Stop, Attachments | Always |
| **2 - Secondary row** | Prompt selector, Character, Search & Context, Web search, Voice chat | Always on desktop, collapsed on mobile |
| **3 - Overflow** | MCP, Ephemeral toggle, Insert prompt, Dictation, Presets, Templates, Cost, Chat settings, Tabs/files counts, Connection hints | Behind `Popover` trigger |

The overflow trigger is a `SlidersHorizontal` icon button (already imported in PlaygroundForm.tsx) that opens an antd `Popover` with a structured layout of Tier 3 controls.

On mobile (`isMobile` prop), Tier 2 moves into the overflow as well.

**Acceptance criteria**:
- Desktop: 7-8 controls visible, rest in popover
- Mobile: 3-4 controls visible, rest in popover/bottom sheet
- All controls remain accessible and functional
- No controls are removed, only reorganized

---

### S4: Move ConnectionStatus to Composer Area

**Modify**: `apps/packages/ui/src/components/Layouts/ChatHeader.tsx`
**Modify**: `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`

Move `<ConnectionStatus>` from ChatHeader (line 89) into the ComposerToolbar. It is contextually more relevant near the "Connect to tldw" messaging and the send button.

**Acceptance criteria**:
- ConnectionStatus renders in the composer area (near the send button)
- Removed from the header
- Connection-related messaging still visible

---

### S5: Header Control Reorganization

**Modify**: `apps/packages/ui/src/components/Layouts/ChatHeader.tsx`

Move low-frequency header controls to the command palette (already accessible via Cmd+K):
- TTS clips button (lines 141-152)
- Keyboard shortcuts button (lines 165-188)
- Timeline button (lines 189-201)
- Shortcuts panel toggle - Signpost icon (lines 99-109)

Register these as command palette actions so they remain accessible.

**Remaining header items**: Sidebar toggle, Logo, Chat title, New chat, Search (Cmd+K), Settings

**Acceptance criteria**:
- Header renders 6 items instead of 10
- Moved features accessible via Cmd+K command palette
- Chat title visible on mobile (remove `hidden sm:block` from line 112)

---

### S6: Message Actions Overflow Restructuring

**Modify**: `apps/packages/ui/src/components/Common/Playground/MessageActionsBar.tsx`

Reorganize message actions into primary + overflow:

**Primary (visible on hover/tap)**: Copy, Edit, Regenerate (if last message)

**Overflow (behind "..." Popover)**: Reply, Branch, Continue, Save to Notes, Save to Flashcards, Generate Document, TTS, Delete

**Separate row**: Variant pager + Feedback buttons

Create a `MessageActionsOverflow` sub-component that renders overflow actions in a vertical Popover list with icon + label.

**Acceptance criteria**:
- 3 primary actions visible on hover (instead of up to 15)
- All actions remain accessible via overflow
- Variant pager and feedback buttons unaffected
- Mobile tap-to-toggle works (no hover dependency)

---

## File Impact Summary

| File | Action | Estimated Lines |
|------|--------|----------------|
| `PlaygroundForm.tsx` | Remove ~1200 lines (textarea + toolbar duplication) | -1200 |
| `ComposerTextarea.tsx` | New | ~200 |
| `ComposerToolbar.tsx` | New | ~400 |
| `ComposerToolbarOverflow.tsx` | New | ~150 |
| `ChatHeader.tsx` | Modify - remove 4 buttons, adjust layout | ~-60 |
| `MessageActionsBar.tsx` | Modify - add overflow pattern | ~+80 |
| **Net** | | **~-430 lines** |

## Implementation Order

```
S1 (ComposerTextarea) -- independent, safe first step
S2 (ComposerToolbar) -- depends on S1 being done
S3 (ToolbarOverflow) -- depends on S2
S4 (ConnectionStatus move) -- depends on S2
S5 (Header reorganization) -- independent of S1-S4
S6 (Message actions overflow) -- independent of S1-S5
```

## Critical Files Reference

| File | Path | Lines | Role |
|------|------|-------|------|
| PlaygroundForm | `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx` | 5500+ | Primary target |
| ChatHeader | `apps/packages/ui/src/components/Layouts/ChatHeader.tsx` | 234 | Header |
| MessageActionsBar | `apps/packages/ui/src/components/Common/Playground/MessageActionsBar.tsx` | 450 | Message actions |
| Playground | `apps/packages/ui/src/components/Option/Playground/Playground.tsx` | 595 | Root container |
| Layout | `apps/packages/ui/src/components/Layouts/Layout.tsx` | 500+ | App layout |

## Reusable Utilities

- `useMobile()` hook at `apps/packages/ui/src/hooks/useMediaQuery.ts`
- `useUiModeStore` at `apps/packages/ui/src/store/ui-mode.tsx`
- `Button` component at `apps/packages/ui/src/components/Common/Button.tsx`
- Antd `Popover`, `Drawer`, `Tooltip` -- already imported in PlaygroundForm

## Verification

1. Start dev server: `cd apps/tldw-frontend && npm run dev`, open `/chat`
2. Test both Pro and Normal UI modes (toggle in settings)
3. Send messages, verify streaming, regenerate, edit, branch
4. Test all overflow/popover menus open and function
5. Test command palette (Cmd+K) for moved header features
6. Test mobile viewport (Chrome DevTools at 375px)
7. Run existing frontend tests if available
