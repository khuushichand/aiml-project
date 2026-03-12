# UI Typecheck Chat Cluster Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clear the current chat/playground TypeScript errors that are blocking targeted verification after the `chat bugfixes` cherry-pick and the local Playground search-navigation follow-up.

**Architecture:** Fix the chat/playground cluster in place by restoring missing imports and scope references, aligning option object shapes with current hook/mode types, and narrowing i18n return values where JSX expects `ReactNode`/string. Verify with targeted Vitest and `tsc` checks against only the touched files before re-running broader UI checks.

**Tech Stack:** TypeScript, React, Vitest, Bun, i18next, local UI package typecheck

## Progress

- Status: Tasks 1-5 completed for the original chat/playground scope.
- Status: Additional follow-up clusters completed in the same workspace:
  - Common component test/runtime typing fixes
  - Flashcards import normalizers
  - Media content viewer/test typing fixes
  - Notes manager/test typing fixes
  - Dictionaries manager/test typing fixes
  - Characters manager/test typing fixes
  - KnowledgeQA provider/context typing fixes
  - Watchlists translator/helper/test fixes plus overview/source form cleanup
  - Kanban playground typing fixes
  - Moderation playground test typing fixes
  - PromptBody search-pagination test typing fixes
  - Writing playground badge typing fix
  - Quiz test/runtime typing fixes
  - Review runtime/test typing fixes
  - Sidepanel and server-chat typing fixes
  - Background proxy test typing fixes
  - Hook translation-signature fixes for file upload and bulk chat operations
  - Watchlists TemplatesTab typing fixes plus template editor/preview test alignment
  - Common Playground store-slice typing fix
  - Common Playground source feedback typing fix
  - Dexie chat media update typing fix
  - Request-core path-normalization test tuple typing fix
  - OpenAPI guard path coverage for chat workflows and MCP Hub services
  - WorkspacePlayground typing fixes plus targeted workspace test alignment
  - WorldBooks typing fixes plus targeted manager/form-utils test alignment
  - Workspace split-storage and persistence rehydrate typing fixes
  - ACP sessions and watchlists onboarding telemetry test fixture typing fixes
- Status: The remaining scattered service/store/db/test tail is cleared.
- Status: Full UI typecheck now passes.

---

### Task 1: Capture The Failing Chat/Playground Cluster

**Files:**
- Modify: `docs/plans/2026-03-12-ui-typecheck-chat-cluster.md`
- Inspect: `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Inspect: `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Inspect: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Inspect: `apps/packages/ui/src/hooks/useMessage.tsx`
- Inspect: `apps/packages/ui/src/hooks/useMessageOption.tsx`
- Inspect: `apps/packages/ui/src/hooks/chat-modes/chatModePipeline.ts`
- Inspect: `apps/packages/ui/src/components/Sidepanel/Chat/body.tsx`

**Step 1: Reproduce the current compiler failures**

Run: `bun x tsc --noEmit -p apps/packages/ui/tsconfig.json`
Expected: FAIL with the current chat/playground cluster errors and many unrelated baseline errors.

**Step 2: Record the chat/playground subset**

Focus on:
- Missing symbols/scope: `controller`, `inactivityTimer`, `applyVariantToMessage`
- Invalid option keys: `serverChatId`, `compareAutoDisabledFlag`
- JSX/i18n type mismatches in `Playground.tsx` and `PlaygroundChat.tsx`
- Signature drift in `Sidepanel/Chat/body.tsx`

**Step 3: Keep edits constrained to this cluster**

Do not change unrelated feature areas while this batch is in progress.

### Task 2: Fix The Hard Compile Breaks First

**Files:**
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Modify: `apps/packages/ui/src/hooks/chat-modes/chatModePipeline.ts`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/body.tsx`
- Test: `apps/packages/ui/src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`

**Step 1: Restore missing import/scope references**

Add the missing `applyVariantToMessage` import in `chatModePipeline.ts`.
Replace the out-of-scope abort reference in `useChatActions.ts` with the actual active abort controller in that function.
Move/reshape inactivity timer cleanup so it references a variable that exists in the same scope.

**Step 2: Align callback signatures**

Update `Sidepanel/Chat/body.tsx` to call the current `editMessage` API with the supported argument list.

**Step 3: Verify the file-level compiler state**

Run targeted checks after the edits:
- `bun x tsc --noEmit -p apps/packages/ui/tsconfig.json 2>&1 | rg "useChatActions|chatModePipeline|Sidepanel/Chat/body"`
- `bun x vitest run src/components/Option/MCPHub/__tests__/policyHelpers.test.ts`

Expected: No remaining errors for those files; MCP Hub test still passes.

### Task 3: Fix Option-Shape Drift In Chat Hooks

**Files:**
- Modify: `apps/packages/ui/src/hooks/useMessage.tsx`
- Modify: `apps/packages/ui/src/hooks/useMessageOption.tsx`
- Inspect: `apps/packages/ui/src/hooks/chat/useChatActions.ts`

**Step 1: Match current hook/mode option types**

Remove or relocate unsupported option properties passed into `normalChatMode` / `useChatActions`.
Use the currently supported path for persona/server-chat state instead of forcing extra keys onto option objects.

**Step 2: Tighten unsafe casts**

Replace the direct `ServerChatSummary -> Record<string, unknown>` cast with a safer `unknown` bridge or helper that matches current typing.

**Step 3: Verify targeted compiler output**

Run: `bun x tsc --noEmit -p apps/packages/ui/tsconfig.json 2>&1 | rg "useMessage|useMessageOption"`
Expected: No remaining errors for those files.

### Task 4: Fix Playground JSX/I18n Typing

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

**Step 1: Narrow translation output at render sites**

Convert ambiguous `t(...)` results used in JSX attributes/text into explicit strings where the component contract requires `string`/`ReactNode`.

**Step 2: Remove stale message field access**

Use the typed message field (`messageType`) instead of legacy `message_type` access where the local `Message` type no longer exposes it.

**Step 3: Verify the playground subset**

Run: `bun x tsc --noEmit -p apps/packages/ui/tsconfig.json 2>&1 | rg "Playground\\.tsx|PlaygroundChat\\.tsx"`
Expected: No remaining errors for those files.

### Task 5: Re-Run Verification And Report Residual Debt

**Files:**
- Modify: `docs/plans/2026-03-12-ui-typecheck-chat-cluster.md`

**Step 1: Run full UI typecheck again**

Run: `bun x tsc --noEmit -p apps/packages/ui/tsconfig.json`
Expected: FAIL or PASS depending on remaining unrelated baseline errors.

**Step 2: Record actual residual failures**

If failures remain, summarize which clusters are still outstanding after this batch.

**Step 3: Run Bandit on touched scope**

Run: `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/Playground apps/packages/ui/src/hooks/chat apps/packages/ui/src/hooks/useMessage.tsx apps/packages/ui/src/hooks/useMessageOption.tsx apps/packages/ui/src/components/Sidepanel/Chat/body.tsx -f json -o /tmp/bandit_ui_chat_cluster.json`
Expected: Either 0 findings or explicit findings to fix before stopping.
