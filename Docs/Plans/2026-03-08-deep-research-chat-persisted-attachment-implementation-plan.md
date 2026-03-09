# Deep Research Chat Persisted Attachment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist one active deep-research attachment per saved server-backed chat thread and auto-restore it when that thread is reopened.

**Architecture:** Reuse the existing chat settings persistence seam. Validate a bounded `deepResearchAttachment` object in backend chat settings, extend package-side chat settings types/helpers to normalize it, and have `Playground.tsx` restore/persist the active attachment on committed state changes only.

**Tech Stack:** FastAPI, Pydantic, existing chat settings endpoints and DB helpers, React, TypeScript, package-side chat settings helpers, vitest, pytest.

---

### Task 1: Add Red Backend Tests For Persisted Attachment Validation

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py`

**Step 1: Write the failing tests**

Add endpoint tests that prove:

- `PUT /api/v1/chats/{chat_id}/settings` accepts a valid `deepResearchAttachment`
- unknown keys inside `deepResearchAttachment` are rejected
- the saved settings can be fetched back through `GET /api/v1/chats/{chat_id}/settings`
- a second user cannot read or update another user's persisted attachment

Use a bounded payload like:

```python
attachment = {
    "run_id": "run_123",
    "query": "Battery recycling supply chain",
    "question": "Battery recycling supply chain",
    "outline": [{"title": "Overview"}],
    "key_claims": [{"text": "Claim one"}],
    "unresolved_questions": ["What changed in Europe?"],
    "verification_summary": {"unsupported_claim_count": 1},
    "source_trust_summary": {"high_trust_count": 2},
    "research_url": "/research?run=run_123",
    "attached_at": "2026-03-08T20:00:00Z",
}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q
```

Expected:

- failures for missing validation/round-trip support

**Step 3: Write minimal implementation**

Do not change frontend code yet. Implement only the backend validation needed for these tests.

**Step 4: Run tests to verify they pass**

Re-run the same pytest command.

Expected:

- new persisted-attachment backend tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): validate persisted research attachments"
```

### Task 2: Implement Backend Validation For deepResearchAttachment

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`

**Step 1: Write the failing validation-focused tests**

Extend the backend tests so they also prove:

- required identity fields must be strings
- `verification_summary` only allows `unsupported_claim_count`
- `source_trust_summary` only allows `high_trust_count`
- list fields reject oversized payloads or invalid item shapes

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py -q
```

Expected:

- validation-shape failures

**Step 3: Write minimal implementation**

In `character_chat_sessions.py`:

- add a dedicated nested validator inside `_validate_chat_settings_payload(...)`
- validate:
  - allowed keys
  - string identity fields
  - bounded list/object shapes
  - ISO timestamp for `attached_at`
- rely on the existing overall settings byte cap for final size enforcement

**Step 4: Run tests to verify they pass**

Re-run the same pytest command.

Expected:

- persisted attachment validation tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): bound persisted research attachment settings"
```

### Task 3: Add Package-Side Types And Normalization For Persisted Attachments

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/types/chat-session-settings.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/chat-settings.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/__tests__/chat-settings.test.ts`

**Step 1: Write the failing tests**

Add tests that prove:

- chat settings normalization keeps a valid `deepResearchAttachment`
- malformed persisted attachment is ignored
- normalization does not crash on unknown/partial raw settings blobs
- the attachment shape round-trips through the package-side settings helpers

**Step 2: Run tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.test.ts
```

Expected:

- failures for missing persisted-attachment typing/normalization

**Step 3: Write minimal implementation**

In `chat-session-settings.ts`:

- add a typed `DeepResearchAttachmentRecord`
- add it to `ChatSettingsRecord` as optional `deepResearchAttachment`

In `chat-settings.ts`:

- normalize `deepResearchAttachment` through a bounded coercion helper

In `research-chat-context.ts`:

- add helper(s) to convert between live attached context and persisted settings shape if needed

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- new type/normalization tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/types/chat-session-settings.ts \
  apps/packages/ui/src/services/chat-settings.ts \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.test.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): normalize persisted research attachments"
```

### Task 4: Auto-Restore Persisted Attachment In Playground

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing tests**

Extend the playground integration tests to prove:

- reopening a saved chat with persisted `deepResearchAttachment` restores:
  - active attached context
  - baseline attached context
- switching from one saved chat to another restores the correct persisted attachment for each
- malformed persisted attachment is ignored safely
- temporary chats do not restore persisted attachment

**Step 2: Run tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected:

- failures for missing auto-restore behavior

**Step 3: Write minimal implementation**

In `Playground.tsx`:

- load chat settings for the current `serverChatId`
- restore `deepResearchAttachment` into both active and baseline state
- clear local attachment state when switching to a chat with no persisted attachment
- guard strictly on `serverChatId`

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- restore/switch tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): auto-restore persisted research attachments"
```

### Task 5: Persist Committed Attachment State Changes Only

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- attach from `Use in Chat` persists to settings for saved chats
- preview/debug `Apply` persists the new active attachment
- `Reset to Attached Run` persists the restored baseline
- `Remove Attachment` clears `deepResearchAttachment` from settings
- draft typing in the preview editor does not persist before `Apply`

**Step 2: Run tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx
```

Expected:

- failures for missing persisted writes or premature draft writes

**Step 3: Write minimal implementation**

In `Playground.tsx`:

- persist only on committed attachment transitions:
  - attach
  - apply
  - reset
  - remove
- skip persistence for temporary/local chats

Do not persist from per-keystroke draft state in `PlaygroundForm.tsx`.

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- commit-only persistence tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): persist committed research attachments"
```

### Task 6: Final Verification, Bandit, And Plan Closure

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-08-deep-research-chat-persisted-attachment-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q
```

Expected:

- persisted attachment backend tests pass

**Step 2: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  apps/packages/ui/src/services/__tests__/chat-settings.test.ts
```

Expected:

- persisted attachment frontend tests pass

**Step 3: Run broader adjacent regression coverage**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  apps/packages/ui/src/services/__tests__/tldw-chat.message-sanitization.test.ts
```

Expected:

- adjacent chat/research flows still pass

**Step 4: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  -f json -o /tmp/bandit_deep_research_chat_persisted_attachment.json
```

Expected:

- `0` new findings in touched backend code

**Step 5: Update plan status**

Mark each task complete and note any deviations directly in this plan file.

**Step 6: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  Docs/Plans/2026-03-08-deep-research-chat-persisted-attachment-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "docs(research): finalize persisted attachment plan"
```
