# Chat Workflows Implementation Plan

## Stage 1: Persistence + API Surface
**Goal**: Add a dedicated Chat Workflows backend domain with template/run/answer persistence, request schemas, service logic, and FastAPI routes.
**Success Criteria**: Templates, generated drafts, runs, answers, transcript retrieval, cancellation, and continue-chat handoff are all available behind explicit Chat Workflows permissions.
**Tests**: `test_chat_workflows_db.py`, `test_chat_workflows_schemas.py`, `test_chat_workflows_service.py`, `test_chat_workflows_api.py`, AuthNZ dependency and permission tests.
**Status**: Complete

## Stage 2: Shared UI Data Layer
**Goal**: Expose Chat Workflows to the frontend through typed client helpers and TanStack Query hooks.
**Success Criteria**: The shared UI package can list templates, generate drafts, start runs, retrieve runs/transcripts, submit answers, cancel runs, and continue to chat.
**Tests**: `apps/packages/ui/src/services/tldw/__tests__/chat-workflows.test.ts`, `apps/packages/ui/src/hooks/__tests__/useChatWorkflows.test.tsx`
**Status**: Complete

## Stage 3: Authoring Experience
**Goal**: Ship a first-class Chat Workflows page with library, builder, and generated-draft entry flow.
**Success Criteria**: Users can create, edit, duplicate, and save templates from the dedicated page and reach the generator from workspace navigation.
**Tests**: `apps/packages/ui/src/components/Option/ChatWorkflows/__tests__/ChatWorkflowsPage.test.tsx`, `apps/packages/ui/src/routes/__tests__/chat-workflows-route.test.tsx`
**Status**: Complete

## Stage 4: Guided Run Experience
**Goal**: Add guided run playback, answer submission, completion handling, and chat handoff.
**Success Criteria**: A workflow can start from the library or an unsaved draft, show one active question at a time, render prior answers as locked history, and navigate into normal chat only after completion.
**Tests**: `apps/packages/ui/src/components/Option/ChatWorkflows/__tests__/ChatWorkflowsPage.test.tsx`, `apps/packages/ui/src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`
**Status**: Complete

## Stage 5: Documentation + Verification
**Goal**: Document the feature and verify the touched backend/frontend scope and security checks.
**Success Criteria**: Developer docs, published API docs, and feature status are updated; targeted pytest, Vitest, and Bandit runs are clean.
**Tests**: Chat Workflows pytest subset, shared UI Vitest suite, Playground integration test, Bandit on the touched backend scope.
**Status**: Complete
