# Hide Content Review Launcher Entry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep `/content-review` reachable by direct URL and Quick Ingest redirects while removing it from user-facing page discovery in the header shortcuts launcher and shortcut customization surface.

**Architecture:** Leave the route registry and page component intact so navigation by URL and programmatic redirects continue to work. Remove the launcher-specific `content-review` item from the header shortcut catalog and from the allowed shortcut ID list so the modal and settings no longer expose it.

**Tech Stack:** React, TypeScript, Vitest, Testing Library

---

### Task 1: Prove the launcher should not expose Content Review

**Files:**
- Modify: `apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx`

**Step 1: Write the failing test**

Add a test that renders the launcher modal open and asserts `Content Review` is not present in the list of available pages.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx -t "does not show Content Review in the launcher modal"`

Expected: FAIL because the launcher still includes `Content Review`.

### Task 2: Remove Content Review from launcher discovery data

**Files:**
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Modify: `apps/packages/ui/src/services/settings/ui-settings.ts`

**Step 1: Write minimal implementation**

Remove the `content-review` item from the `library` group in `HEADER_SHORTCUT_GROUPS`.

Remove `content-review` from `HEADER_SHORTCUT_IDS` so it is no longer a selectable shortcut entry in settings.

**Step 2: Run the targeted test to verify it passes**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx`

Expected: PASS.

### Task 3: Verify touched scope

**Files:**
- Verify: `apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx`
- Verify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Verify: `apps/packages/ui/src/services/settings/ui-settings.ts`

**Step 1: Run security scan on touched scope**

Run: `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Layouts apps/packages/ui/src/services/settings -f json -o /tmp/bandit_hide_content_review_launcher.json`

Expected: No new findings in touched code.

**Step 2: Summarize verification evidence**

Record the exact test command and Bandit results in the task summary before claiming completion.
