# Chat Stream Hang Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `/chat` streaming turns from remaining in a pending "Thinking..." state for minutes when no visible assistant output is arriving.

**Architecture:** Tighten timeout handling inside the frontend chat stream wrapper instead of redesigning the full backend stream protocol. The fix adds a hard request timeout, makes the idle timeout configurable, and only treats visible progress as activity for the local idle timer.

**Tech Stack:** TypeScript, Vitest, shared UI chat services

---

### Task 1: Add Regression Tests For Streaming Timeout Semantics

**Files:**
- Modify: `apps/packages/ui/src/services/__tests__/tldw-chat.message-sanitization.test.ts`

- [x] **Step 1: Write failing tests**
- [x] **Step 2: Run targeted Vitest command and confirm the new tests fail for the expected reason**
- [x] **Step 3: Keep one passing baseline test for ordinary streamed token content**

### Task 2: Implement Frontend Chat Stream Timeout Fix

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/TldwChat.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts` only if needed for timeout typing

- [x] **Step 1: Resolve configured `chatRequestTimeoutMs` and `chatStreamIdleTimeoutMs` from stored config**
- [x] **Step 2: Add a hard request timeout controller path for streaming chat**
- [x] **Step 3: Reset local idle timeout only on visible progress chunks**
- [x] **Step 4: Preserve existing success/error behavior for normal text streaming**

### Task 3: Verify And Document Outcome

**Files:**
- Modify: `Docs/superpowers/plans/2026-03-27-chat-stream-hang-fix.md`

- [x] **Step 1: Run targeted Vitest suite for the touched chat service tests**
- [x] **Step 2: Run Bandit on the touched scope as required by repository guidance**
- [x] **Step 3: Mark task statuses in this plan before reporting completion**
