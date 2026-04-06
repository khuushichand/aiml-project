# Video Transcript SaaS Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private overlay product repo for a YouTube-first extension launcher and lightweight hosted transcript workspace, backed by a new idempotent `video-lite` orchestration contract in `tldw_server`.

**Architecture:** Keep backend and trial/orchestration logic in `tldw_server`, but deliver the store-facing extension and hosted app from a separate private sibling repo. That private repo should reuse selected frontend surfaces from the existing app through an explicit upstream sync plus patch-overlay workflow, with private-only patches for branding, lightweight routes, launcher behavior, and upgrade flow.

**Tech Stack:** FastAPI, Pydantic, existing Jobs/media ingestion stack, AuthNZ repos/migrations, private Next.js app, private browser extension package, React, Zustand, Bun/Vitest, pytest, optional sync scripts for vendored frontend updates

---

## File Structure

**Private repo assumption:** unless renamed later, use `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private` as the sibling private project root.

### Backend In `tldw_server`

- Create: `tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py`
  - Request/response models for normalized source lookup, source-state responses, trial state, and upgrade intent metadata.
- Create: `tldw_Server_API/app/services/video_lite_service.py`
  - Canonical orchestration logic: normalize source, reuse or start ingest, query source state, enforce trial semantics, and shape lightweight workspace payloads.
- Create: `tldw_Server_API/app/core/AuthNZ/repos/video_trial_repo.py`
  - Persistence for anonymous trial identity, normalized-source consumption, and retention timestamps.
- Create: `tldw_Server_API/tests/media/test_video_lite_endpoint.py`
  - Endpoint coverage for idempotency, launcher states, entitlement states, and unsupported-source behavior.
- Create: `tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py`
  - Repo-level tests for one-time quota debit per normalized source.
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/__init__.py`
  - Register the new `video-lite` route surface.
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
  - Add anonymous trial tables and indexes.

### Private Overlay Repo

- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/README.md`
  - Explain repo purpose, relationship to `tldw_server`, and sync/patch workflow.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/docs/upstream-sync.md`
  - Rules for what is synced from the existing app and what stays private-only.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
  - Script to copy or refresh selected upstream frontend surfaces from `tldw_server2/apps`.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/video/[sourceKey].tsx`
  - Hosted lightweight workspace route.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/upgrade.tsx`
  - Upgrade wrapper that preserves source and target-tab intent.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/login.tsx`
  - Product login entry that preserves lightweight return intent.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/components/VideoWorkspacePage.tsx`
  - Branded `Transcript` / `Summary` / `Chat` workspace.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-client.ts`
  - Client for the backend `video-lite` contract.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-intent.ts`
  - Shared helpers for preserving source key, target tab, and post-upgrade return intent.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/src/routes/sidepanel-video.tsx`
  - Minimal YouTube-aware launcher with `Ingest`, `Open transcript`, and `Quick chat`.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/src/background/video-lite.ts`
  - Background orchestration and deep-link logic for launcher actions.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/web/VideoWorkspacePage.test.tsx`
  - Hosted workspace tests.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/extension/sidepanel-video.test.tsx`
  - Extension route/launcher tests.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/shared/video-lite-intent.test.ts`
  - Intent and overlay-client tests.

## Task 1: Add The Backend `video-lite` Contract In `tldw_server`

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py`
- Create: `tldw_Server_API/app/services/video_lite_service.py`
- Create: `tldw_Server_API/tests/media/test_video_lite_endpoint.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/__init__.py`

- [ ] **Step 1: Write the failing endpoint tests**

```python
def test_video_lite_returns_canonical_source_state(client, authed_headers):
    response = client.post(
        "/api/v1/media/video-lite/source",
        json={"source_url": "https://www.youtube.com/watch?v=abc123", "target_tab": "transcript"},
        headers=authed_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_key"] == "youtube:abc123"
    assert payload["state"] in {"not_ingested", "processing", "ready", "failed"}
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/media/test_video_lite_endpoint.py -v`
Expected: FAIL because the schemas, service, and route do not exist yet.

- [ ] **Step 3: Write the minimal route and service**

```python
@router.post("/video-lite/source", response_model=VideoLiteSourceStateResponse)
async def resolve_video_lite_source(...):
    return await service.resolve_source_state(...)
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/media/test_video_lite_endpoint.py -v`
Expected: PASS for normalized-source and launcher-state responses.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py \
        tldw_Server_API/app/services/video_lite_service.py \
        tldw_Server_API/app/api/v1/endpoints/media/__init__.py \
        tldw_Server_API/tests/media/test_video_lite_endpoint.py
git commit -m "feat: add video-lite source-state contract"
```

## Task 2: Add Trial Persistence And Idempotent Quota Debit

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/repos/video_trial_repo.py`
- Create: `tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/services/video_lite_service.py`

- [ ] **Step 1: Write the failing trial repo tests**

```python
def test_same_normalized_source_only_consumes_trial_once(repo):
    first = repo.consume_source("anon-1", "youtube:abc123")
    second = repo.consume_source("anon-1", "youtube:abc123")
    assert first.consumed is True
    assert second.consumed is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py tldw_Server_API/tests/media/test_video_lite_endpoint.py -v`
Expected: FAIL because the repo and migration do not exist yet.

- [ ] **Step 3: Implement the repo, migration, and service wiring**

```python
class VideoTrialRepo:
    def consume_source(self, anonymous_id: str, normalized_source: str) -> TrialConsumeResult:
        ...
```

- [ ] **Step 4: Run the tests to verify idempotent debit behavior**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py tldw_Server_API/tests/media/test_video_lite_endpoint.py -v`
Expected: PASS, including retry and reopen paths not double-debiting quota.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/video_trial_repo.py \
        tldw_Server_API/app/core/AuthNZ/migrations.py \
        tldw_Server_API/app/services/video_lite_service.py \
        tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py \
        tldw_Server_API/tests/media/test_video_lite_endpoint.py
git commit -m "feat: add video-lite trial ledger"
```

## Task 3: Create The Private Overlay Repo Skeleton And Sync Workflow

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/README.md`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/docs/upstream-sync.md`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`

- [ ] **Step 1: Write the failing repo-process smoke check**

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh
```

- [ ] **Step 2: Run the smoke check to verify it fails**

Run: `test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
Expected: exit code non-zero because the private repo skeleton does not exist yet.

- [ ] **Step 3: Create the private repo structure and sync docs**

```bash
# create sibling repo skeleton, document copied paths, define patch-only zones
```

- [ ] **Step 4: Run the smoke check to verify the skeleton exists**

Run: `test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
Expected: success.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add README.md docs/upstream-sync.md scripts/sync-from-upstream.sh
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "chore: scaffold private overlay repo"
```

## Task 4: Sync Selected Existing App Surfaces Into The Private Repo

**Files:**
- Create or refresh via sync script:
  - `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/web/`
  - `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/extension/`
  - `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/shared-ui/`

- [ ] **Step 1: Define the initial sync set in the sync script**

```bash
UPSTREAM_WEB_PATHS=(...)
UPSTREAM_EXTENSION_PATHS=(...)
UPSTREAM_SHARED_PATHS=(...)
```

- [ ] **Step 2: Run the sync script and verify it fails cleanly before configuration is complete**

Run: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
Expected: clear failure or TODO message until source paths are configured.

- [ ] **Step 3: Implement the initial sync workflow**

```bash
rsync -a /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/... \
  /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/...
```

- [ ] **Step 4: Re-run the sync script and verify vendored sources appear**

Run: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
Expected: success with copied upstream surfaces and no accidental writes back into `tldw_server2`.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add upstream scripts/sync-from-upstream.sh docs/upstream-sync.md
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "chore: import upstream app surfaces"
```

## Task 5: Add Private Overlay Client And Intent Helpers

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-client.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-intent.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/shared/video-lite-intent.test.ts`

- [ ] **Step 1: Write the failing shared tests**

```ts
it("preserves source key and target tab through upgrade intent", () => {
  const value = buildVideoLiteIntent({ sourceKey: "youtube:abc123", targetTab: "chat" })
  expect(parseVideoLiteIntent(value)).toEqual({ sourceKey: "youtube:abc123", targetTab: "chat" })
})
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/shared/video-lite-intent.test.ts -v`
Expected: FAIL because the overlay client and intent helpers do not exist yet.

- [ ] **Step 3: Implement the private overlay helpers**

```ts
export async function getVideoLiteSourceState(input: VideoLiteSourceRequest) {
  return await api.post("/api/v1/media/video-lite/source", input)
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/shared/video-lite-intent.test.ts -v`
Expected: PASS for source-key, target-tab, and post-login return parsing.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add web/lib/video-lite-client.ts web/lib/video-lite-intent.ts tests/shared/video-lite-intent.test.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: add overlay video-lite client helpers"
```

## Task 6: Build The Private Hosted Lightweight Workspace

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/components/VideoWorkspacePage.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/video/[sourceKey].tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/upgrade.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/login.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/web/VideoWorkspacePage.test.tsx`

- [ ] **Step 1: Write the failing hosted workspace tests**

```tsx
it("renders transcript, summary, and chat tabs for a ready source", () => {
  render(<VideoWorkspacePage initialState={readyState} />)
  expect(screen.getByRole("tab", { name: /transcript/i })).toBeVisible()
  expect(screen.getByRole("tab", { name: /summary/i })).toBeVisible()
  expect(screen.getByRole("tab", { name: /chat/i })).toBeVisible()
})
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/web/VideoWorkspacePage.test.tsx -v`
Expected: FAIL because the private hosted workspace does not exist yet.

- [ ] **Step 3: Implement the hosted overlay routes and workspace**

```tsx
export default function LiteVideoPage() {
  return <VideoWorkspacePage />
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/web/VideoWorkspacePage.test.tsx -v`
Expected: PASS for ready, processing, failure, trial-exhausted, and signed-in-unsubscribed states.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add web/components/VideoWorkspacePage.tsx web/pages/lite/video/[sourceKey].tsx web/pages/lite/upgrade.tsx web/pages/login.tsx tests/web/VideoWorkspacePage.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: add private hosted video-lite workspace"
```

## Task 7: Build The Private Extension Launcher Overlay

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/src/routes/sidepanel-video.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/src/background/video-lite.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/extension/sidepanel-video.test.tsx`

- [ ] **Step 1: Write the failing extension tests**

```ts
it("routes quick chat to upgrade with preserved chat intent for unsubscribed users", async () => {
  const result = await resolveLauncherAction({
    sourceState: "ready",
    entitlement: "signed_in_unsubscribed",
    action: "quick_chat"
  })
  expect(result.destination).toContain("/lite/upgrade")
  expect(result.intent.targetTab).toBe("chat")
})
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/extension/sidepanel-video.test.tsx -v`
Expected: FAIL because the extension overlay launcher does not exist yet.

- [ ] **Step 3: Implement the private extension launcher**

```ts
const state = await getVideoLiteSourceState({ sourceUrl: currentTabUrl, targetTab: "transcript" })
return routeLauncherAction(state, requestedAction)
```

- [ ] **Step 4: Run the tests to verify launcher behavior passes**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/extension/sidepanel-video.test.tsx -v`
Expected: PASS for `Ingest`, `Open transcript`, `Quick chat`, processing, failure, and upgrade cases.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add extension/src/routes/sidepanel-video.tsx extension/src/background/video-lite.ts tests/extension/sidepanel-video.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: add private extension video-lite launcher"
```

## Task 8: Verification, Security Checks, And Sync Discipline

**Files:**
- Modify: `Docs/superpowers/specs/2026-04-05-video-transcript-saas-extension-design.md`
  - Only if implementation choices resolve open questions.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/docs/verification.md`
  - Product verification commands and upstream-sync safety rules.

- [ ] **Step 1: Document the chosen sync and patch policy**

```md
## Sync Policy
- upstream paths are vendored from `tldw_server2/apps`
- private-only patches live outside `upstream/`
- no direct product work lands back in the OSS repo
```

- [ ] **Step 2: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/media/test_video_lite_endpoint.py \
  tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py -v
```

Expected: PASS for backend source-state and trial logic.

- [ ] **Step 3: Run Bandit on touched backend paths**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py \
  tldw_Server_API/app/services/video_lite_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/video_trial_repo.py \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  -f json -o /tmp/bandit_video_lite.json
```

Expected: JSON report written to `/tmp/bandit_video_lite.json` with no new high-signal findings in touched code.

- [ ] **Step 4: Run private repo verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test \
  tests/shared/video-lite-intent.test.ts \
  tests/web/VideoWorkspacePage.test.tsx \
  tests/extension/sidepanel-video.test.tsx -v
```

Expected: PASS for overlay client, hosted workspace, and extension launcher coverage.

- [ ] **Step 5: Commit docs updates**

```bash
git add Docs/superpowers/specs/2026-04-05-video-transcript-saas-extension-design.md \
        Docs/superpowers/plans/2026-04-05-video-transcript-saas-extension-implementation-plan.md
git commit -m "docs: update video-lite plan for private overlay repo"
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add docs/verification.md
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "docs: add overlay verification guide"
```

## Notes For The Implementer

- Do not ship the store-facing extension or hosted app from `apps/` inside `tldw_server`.
- Treat `tldw_server2/apps` as upstream input, not the delivery repo.
- Keep the private patch layer intentionally small and well-bounded.
- Prefer wrapper files and private routes over invasive edits to vendored upstream files when possible.
- Keep anonymous trial YouTube-only in both backend validation and frontend affordances.
- Do not debit trial quota on submission; debit only when a normalized source reaches transcript-ready.
- Preserve source key and target-tab intent through login and upgrade flows.
