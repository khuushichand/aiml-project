# Chat Background Image Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the chat background image upload cap to 15 MB everywhere that setting can be changed, without affecting regular chat attachments.

**Architecture:** Keep validation client-side where it already exists, but remove duplicated magic numbers by exporting a shared chat background limit constant from the shared UI settings module. Reuse that constant in both upload handlers and cover the behavior with focused settings tests.

**Tech Stack:** React, TypeScript, Vitest, Testing Library

---

### Task 1: Add the failing regression test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Settings/__tests__/ChatSettings.test.tsx`
- Test: `apps/packages/ui/src/components/Option/Settings/__tests__/ChatSettings.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it("rejects background images above the 15 MB cap", async () => {
  toBase64Mock.mockResolvedValue(`data:image/png;base64,${"a".repeat(15_000_001)}`)
  // render, upload image, expect notification error, expect no save
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Settings/__tests__/ChatSettings.test.tsx`
Expected: FAIL because the current limit and copy still reflect the old ~3 MB cap and there is no explicit regression coverage for the 15 MB threshold.

- [ ] **Step 3: Write minimal implementation**

```ts
export const CHAT_BACKGROUND_IMAGE_MAX_BASE64_LENGTH = 15_000_000
export const CHAT_BACKGROUND_IMAGE_MAX_SIZE_MB = 15
```

```ts
if (base64String.length > CHAT_BACKGROUND_IMAGE_MAX_BASE64_LENGTH) {
  // show size error and return
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Settings/__tests__/ChatSettings.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-27-chat-background-image-limit.md apps/packages/ui/src/services/settings/ui-settings.ts apps/packages/ui/src/components/Option/Settings/ChatSettings.tsx apps/packages/ui/src/components/Option/Settings/system-settings.tsx apps/packages/ui/src/components/Option/Settings/__tests__/ChatSettings.test.tsx
git commit -m "fix: raise chat background image size limit"
```
