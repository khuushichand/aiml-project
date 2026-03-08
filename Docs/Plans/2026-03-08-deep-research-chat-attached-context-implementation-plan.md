# Deep Research Chat-Attached Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users attach a bounded, completed deep research run to the active chat session as reusable follow-up context without polluting the transcript or persisting the attachment to the thread.

**Architecture:** Keep the attached research context session-scoped in the web playground by storing it in local `Playground` state and passing it down to `PlaygroundChat` and `PlaygroundForm`. Fetch completed bundles through a shared package-side `TldwApiClient.getResearchBundle(...)` helper, clear the attached snapshot whenever the active `serverChatId` or `historyId` changes, extend the existing `/api/v1/chat/completions` request contract with an optional typed `research_context` payload whose nested models reject unknown keys, inject that payload into the model-facing prompt assembly in `chat_service.py`, and add a hidden metadata marker to research completion handoff messages so the chat UI can render `Use in Chat` without parsing free text. Only standard text follow-up requests should carry `research_context` in v1.

**Tech Stack:** FastAPI, Pydantic v2, existing chat service/orchestrator pipeline, React/TypeScript, existing package-side playground components, pytest, vitest, Bandit.

---

### Task 1: Add Red Backend Tests For The New Request Contract

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/schemas/test_chat_validators.py`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py`

**Step 1: Write the failing tests**

Add schema tests that prove:

- `ChatCompletionRequest` accepts a bounded `research_context`
- omitting `research_context` preserves current behavior
- invalid `research_context` payloads are rejected
- nested unknown keys inside `research_context` are rejected even though the parent request still allows extras

Use a focused request example shaped like:

```python
payload = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Use the attached research."}],
    "research_context": {
        "run_id": "run_123",
        "query": "battery recycling supply chain",
        "question": "What changed in the battery recycling market?",
        "outline": [{"title": "Overview"}],
        "key_claims": [{"text": "Claim one"}],
        "unresolved_questions": ["What changed in Europe?"],
        "verification_summary": {"unsupported_claim_count": 0},
        "source_trust_summary": {"high_trust_count": 3},
        "research_url": "/research?run=run_123",
    },
}
```

Add a new unit test module for the model-facing prompt assembly seam that asserts:

- the model payload can include the bounded research context block
- the original transcript messages remain untouched

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/schemas/test_chat_validators.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py \
  -q
```

Expected:

- failures referencing missing `research_context` schema support and missing prompt-assembly behavior

**Step 3: Write minimal implementation**

Do not touch the frontend yet.

Implement only enough schema scaffolding to make the first assertions possible:

- add typed helper models in `chat_request_schemas.py`
- make the nested `research_context` helper models explicitly reject unknown keys
- add optional `research_context` to `ChatCompletionRequest`

Use explicit top-level fields only. Do not add nested path selectors or raw bundle support.

**Step 4: Run tests to verify partial progress**

Re-run the same pytest command.

Expected:

- schema tests pass
- prompt-assembly tests still fail until Task 2

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
  tldw_Server_API/tests/schemas/test_chat_validators.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "test(chat): add research context request coverage"
```

### Task 2: Inject Research Context Into The Model Prompt And Mark Completion Messages

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/chat_handoff.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Research/test_research_jobs_worker.py`

**Step 1: Write the failing tests**

Extend the new chat-context unit test to prove:

- `chat_service.py` converts `research_context` into a bounded model-facing block
- that block is excluded from the persisted transcript message list
- `build_call_params` or its equivalent excludes `research_context` from raw provider pass-through

Extend the research handoff worker test to prove:

- the inserted completion handoff message gets a hidden metadata marker like:

```python
{
    "deep_research_completion": {
        "run_id": session.id,
        "query": session.query,
        "kind": "completion_handoff",
    }
}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py \
  tldw_Server_API/tests/Research/test_research_jobs_worker.py \
  -q
```

Expected:

- failures showing missing prompt injection and missing handoff metadata writes

**Step 3: Write minimal implementation**

In `chat_service.py`:

- add a helper that formats the bounded research context into a dedicated prompt block
- inject that block into the model-facing system layer or payload assembly, not into `request_data.messages`
- ensure `research_context` is excluded from provider call params

In `chat_handoff.py`:

- after `add_message(...)`, write message metadata extra for the inserted assistant message
- keep the visible message content unchanged

Use the existing metadata DB API instead of inventing a new message type.

**Step 4: Run tests to verify they pass**

Re-run the same pytest command.

Expected:

- both suites pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/app/core/Research/chat_handoff.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py \
  tldw_Server_API/tests/Research/test_research_jobs_worker.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): inject attached research context"
```

### Task 3: Add Frontend Red Tests For Attach/Derive Behavior

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`

**Step 1: Write the failing tests**

Add a pure helper test that proves bundle normalization produces the bounded chat-safe subset:

- caps claims
- caps unresolved questions
- derives `source_trust_summary`
- excludes `report_markdown` and full source inventory

Extend the research-status integration test to prove:

- completed rows expose `Use in Chat`
- non-completed rows do not

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
```

Expected:

- failures for missing helper module and missing `Use in Chat` action

**Step 3: Write minimal implementation**

Create `research-chat-context.ts` with:

- typed `AttachedResearchContext`
- `deriveAttachedResearchContext(bundle, runId, query)`
- `isDeepResearchCompletionMetadata(...)` helper for completion-handoff messages

Keep the helper pure and bounded.

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- both tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "test(chat): add attached research context helpers"
```

### Task 4: Wire Attach Actions Into Chat Status Rows And Completion Messages

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/hooks/chat/useServerChatLoader.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

**Step 1: Write the failing tests**

Add integration coverage that proves:

- clicking `Use in Chat` on a completed linked run fetches the bundle through the shared package-side client and attaches context
- completion handoff messages with `metadataExtra.deep_research_completion` show the same action
- the action does not appear for unrelated assistant messages

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Expected:

- failures for missing callback plumbing and missing completion-message action

**Step 3: Write minimal implementation**

In `PlaygroundChat.tsx`:

- accept attach callback props from `Playground`
- pass `Use in Chat` handlers to the status stack and message cards

In `ResearchRunStatusStack.tsx`:

- render `Use in Chat` only for completed runs

In `Message.tsx`:

- render `Use in Chat` only when the message metadata indicates a deep research completion handoff

In `useServerChatLoader.ts`:

- ensure `metadataExtra` continues to flow through mapped messages used by the chat renderer

In `TldwApiClient.ts`:

- add the shared `getResearchBundle(runId)` helper used by the package-side chat UI

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx \
  apps/packages/ui/src/components/Common/Playground/Message.tsx \
  apps/packages/ui/src/hooks/chat/useServerChatLoader.ts \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): add use-in-chat research actions"
```

### Task 5: Add Local Attached-Context State And Outbound Request Wiring

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.research-context.integration.test.tsx`

**Step 1: Write the failing tests**

Add integration coverage that proves:

- attached context chip renders near the composer
- the chip stays active across sends
- sending includes `research_context` on the outbound `ChatCompletionRequest`
- attaching a second run replaces the first
- removing the chip stops sending `research_context`
- bundle fetch failure does not attach anything
- switching to a different `serverChatId` or `historyId` clears the attached context
- nonstandard send paths like image-command and compare-mode requests do not carry `research_context`

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.research-context.integration.test.tsx
```

Expected:

- failures for missing chip UI and missing request payload field

**Step 3: Write minimal implementation**

In `Playground.tsx`:

- add local `attachedResearchContext` state
- pass attach/remove callbacks to `PlaygroundChat` and `PlaygroundForm`
- clear the attached context whenever the active `serverChatId` or `historyId` changes

In `PlaygroundForm.tsx`:

- render `AttachedResearchContextChip`
- thread `attachedResearchContext` into `ChatCompletionRequest`
- keep the context active until removed or replaced
- suppress `research_context` for image-command, compare-mode, and other nonstandard send paths in v1

In `TldwApiClient.ts`:

- extend the frontend `ChatCompletionRequest` interface with typed optional `research_context`

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.research-context.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): keep research context attached in composer"
```

### Task 6: Run Focused Verification And Finalize

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-08-deep-research-chat-attached-context-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/schemas/test_chat_validators.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_research_chat_context.py \
  tldw_Server_API/tests/Research/test_research_jobs_worker.py \
  -q
```

Expected:

- all targeted backend tests pass

**Step 2: Run focused frontend verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.research-context.integration.test.tsx
```

Expected:

- all targeted frontend tests pass

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
  tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/app/core/Research/chat_handoff.py \
  -f json -o /tmp/bandit_deep_research_chat_attached_context.json
```

Expected:

- `0` new findings in touched code

**Step 4: Update the plan status**

Record:

- exact commands run
- pass/fail counts
- any skipped or intentionally deferred cases

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  Docs/Plans/2026-03-08-deep-research-chat-attached-context-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "docs(research): finalize chat attached-context plan"
```
