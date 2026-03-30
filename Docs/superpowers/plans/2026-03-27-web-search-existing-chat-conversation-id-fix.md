# Web Search Existing Chat Conversation ID Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep a pre-existing server-backed chat on the same conversation when web search is enabled for the next turn.

**Architecture:** Resolve the active server chat ID once in `useChatActions`, thread it through chat-mode params, and pass it explicitly into `pageAssistModel` so `/api/v1/chat/completions` always receives the intended `conversation_id`. Lock the fix with regression tests at the action layer and pipeline/model seam.

**Tech Stack:** React hooks, Zustand, Vitest, TypeScript

---

## Stage 1: Red
**Goal:** Add regressions that describe the broken conversation handoff.
**Success Criteria:** Tests assert that existing server chat IDs are forwarded when web search is enabled.
**Tests:** `bunx vitest run ../packages/ui/src/hooks/chat/__tests__/useChatActions.image-event-sync.integration.test.tsx ../packages/ui/src/hooks/chat-modes/__tests__/chatModePipeline.conversation-id.test.ts`
**Status:** Complete

## Stage 2: Green
**Goal:** Thread explicit `conversationId` through the chat pipeline.
**Success Criteria:** `useChatActions` passes resolved server chat IDs into mode params and `runChatPipeline` passes them into `pageAssistModel`.
**Tests:** Same targeted Vitest command as Stage 1.
**Status:** Complete

## Stage 3: Verify
**Goal:** Confirm the fix holds and no new security findings were introduced in touched files.
**Success Criteria:** Targeted tests pass and Bandit reports no findings in touched scope.
**Tests:** `bunx vitest run ../packages/ui/src/hooks/chat/__tests__/useChatActions.image-event-sync.integration.test.tsx ../packages/ui/src/hooks/chat-modes/__tests__/chatModePipeline.conversation-id.test.ts` and `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/hooks/chat apps/packages/ui/src/hooks/chat-modes apps/packages/ui/src/models -f json -o /tmp/bandit_web_search_conversation_id_fix.json`
**Status:** Complete
