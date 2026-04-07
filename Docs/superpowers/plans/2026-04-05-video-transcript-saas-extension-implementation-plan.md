# Video Transcript SaaS Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private overlay product repo for a YouTube-first extension launcher and lightweight hosted transcript workspace, backed by a new idempotent `video-lite` orchestration contract in `tldw_server`, with eager summary generation owned by the backend workspace lifecycle.

**Architecture:** Keep backend auth/subscription/orchestration logic in `tldw_server`, but deliver the store-facing extension and hosted app from a separate private sibling repo. That private repo should reuse selected frontend surfaces from the existing app through an explicit upstream sync plus patch-overlay workflow, with private-only patches for branding, lightweight routes, launcher behavior, upgrade flow, and a hosted workspace that reads one backend-owned transcript-plus-summary contract.

**Tech Stack:** FastAPI, Pydantic, existing Jobs/media ingestion stack, AuthNZ repos/migrations, private Next.js app, private browser extension package, React, Zustand, Bun/Vitest, pytest, optional sync scripts for vendored frontend updates

---

## Execution Status

- Tasks `1` through `9` reflect baseline work that was already completed in earlier implementation passes and are retained as historical context.
- Do not re-run the "expected fail because files do not exist yet" steps from Tasks `1` through `9` against the current repo state.
- Tasks `1` through `9` are marked `[Completed Historical Baseline]` below; any remaining unchecked archival step text in those sections is not active todo state.
- Tasks `1` through `9` may still mention superseded anonymous or trial-era behavior; treat that wording as archival history, not active product direction.
- Active remaining work starts at Task `10` below.
- Use the actual case-sensitive backend test path `tldw_Server_API/tests/Media/test_video_lite_endpoint.py` in commands and commits.

## File Structure

**Private repo assumption:** unless renamed later, use `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private` as the sibling private project root.

### Backend In `tldw_server`

- Create: `tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py`
  - Request/response models for normalized source lookup, access-gated source-state responses, workspace payloads, summary lifecycle, and upgrade intent metadata.
- Create: `tldw_Server_API/app/services/video_lite_service.py`
  - Canonical orchestration logic: normalize source, reuse or start ingest, query source state, enforce auth/subscription gating, shape lightweight workspace payloads, and generate or reuse eager summaries.
- Create: `tldw_Server_API/tests/Media/test_video_lite_endpoint.py`
  - Endpoint coverage for idempotency, launcher states, entitlement states, and unsupported-source behavior.
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/__init__.py`
  - Register the new `video-lite` route surface.

Historical baseline note:
- earlier completed implementation passes introduced trial-ledger files, but that path is superseded and is not part of the active paid-only target state

### Private Overlay Repo

- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/README.md`
  - Explain repo purpose, relationship to `tldw_server`, and sync/patch workflow.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/package.json`
  - Root workspace scripts and shared dev dependencies.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/bunfig.toml`
  - Bun workspace configuration if used.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tsconfig.json`
  - Shared TypeScript config.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/package.json`
  - Hosted app package definition.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/next.config.js`
  - Hosted app runtime config.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/package.json`
  - Extension package definition.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/wxt.config.ts`
  - Extension build config.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/docs/upstream-sync.md`
  - Rules for what is synced from the existing app and what stays private-only.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/manifest.json`
  - Pinned upstream commit SHA plus exact synced path list.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
  - Script to copy or refresh selected upstream frontend surfaces from `tldw_server2/apps`.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/new.tsx`
  - Signed-in hosted intake page for pasted non-YouTube URLs.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/video/[sourceKey].tsx`
  - Hosted lightweight workspace route.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/upgrade.tsx`
  - Upgrade wrapper that preserves source and target-tab intent.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/login.tsx`
  - Product login entry that preserves lightweight return intent.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/components/VideoWorkspacePage.tsx`
  - Branded `Transcript` / `Summary` / `Chat` workspace backed by backend transcript and eager-summary state.
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-client.ts`
  - Client for the backend `video-lite` source and workspace contracts.
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

## Task 1 [Completed Historical Baseline]: Add The Backend `video-lite` Contract In `tldw_server`

Historical baseline only. This task is already completed in the current worktree and is preserved for implementation history.

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py`
- Create: `tldw_Server_API/app/services/video_lite_service.py`
- Create: `tldw_Server_API/tests/Media/test_video_lite_endpoint.py`
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

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`
Expected: FAIL because the schemas, service, and route do not exist yet.

- [ ] **Step 3: Write the minimal route and service**

```python
@router.post("/video-lite/source", response_model=VideoLiteSourceStateResponse)
async def resolve_video_lite_source(...):
    return await service.resolve_source_state(...)
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`
Expected: PASS for normalized-source and launcher-state responses.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py \
        tldw_Server_API/app/services/video_lite_service.py \
        tldw_Server_API/app/api/v1/endpoints/media/__init__.py \
        tldw_Server_API/tests/Media/test_video_lite_endpoint.py
git commit -m "feat: add video-lite source-state contract"
```

## Task 2 [Completed Historical Baseline]: Add Trial Persistence And Idempotent Quota Debit

Historical baseline only. This task is already completed in the current worktree and is preserved for implementation history.

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

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`
Expected: FAIL because the repo and migration do not exist yet.

- [ ] **Step 3: Implement the repo, migration, and service wiring**

```python
class VideoTrialRepo:
    def consume_source(self, anonymous_id: str, normalized_source: str) -> TrialConsumeResult:
        ...
```

- [ ] **Step 4: Run the tests to verify idempotent debit behavior**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`
Expected: PASS, including retry and reopen paths not double-debiting quota.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/video_trial_repo.py \
        tldw_Server_API/app/core/AuthNZ/migrations.py \
        tldw_Server_API/app/services/video_lite_service.py \
        tldw_Server_API/tests/AuthNZ/repos/test_video_trial_repo.py \
        tldw_Server_API/tests/Media/test_video_lite_endpoint.py
git commit -m "feat: add video-lite trial ledger"
```

## Task 3 [Completed Historical Baseline]: Bootstrap The Private Overlay Repo As A Runnable Workspace

Historical baseline only. This task is already completed in the current private repo and is preserved for implementation history.

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/README.md`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/package.json`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/bunfig.toml`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tsconfig.json`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/package.json`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/next.config.js`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/package.json`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/wxt.config.ts`

- [ ] **Step 1: Write the failing bootstrap smoke checks**

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/package.json
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/package.json
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/wxt.config.ts
```

- [ ] **Step 2: Run the smoke checks to verify they fail**

Run:

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/package.json
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/package.json
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/wxt.config.ts
```

Expected: non-zero exit because the private repo workspace does not exist yet.

- [ ] **Step 3: Create the runnable private workspace skeleton**

```bash
# scaffold root workspace, hosted app package, and extension package
```

- [ ] **Step 4: Run the smoke checks to verify the workspace exists**

Run:

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/package.json
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/package.json
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/wxt.config.ts
```

Expected: success.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add README.md package.json bunfig.toml tsconfig.json web/package.json web/next.config.js extension/package.json extension/wxt.config.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "chore: bootstrap private overlay workspace"
```

## Task 4 [Completed Historical Baseline]: Create The Sync Workflow And Upstream Manifest

Historical baseline only. This task is already completed in the current private repo and is preserved for implementation history.

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/docs/upstream-sync.md`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/manifest.json`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`

- [ ] **Step 1: Write the failing sync/manifest smoke checks**

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/manifest.json
```

- [ ] **Step 2: Run the smoke checks to verify they fail**

Run:

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/manifest.json
```

Expected: non-zero exit because sync assets do not exist yet.

- [ ] **Step 3: Create the sync docs, script, and pinned manifest**

```bash
# create sync docs, manifest.json, and script that updates the pinned upstream commit
```

- [ ] **Step 4: Run the smoke checks to verify sync assets exist**

Run:

```bash
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh
test -f /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/manifest.json
```

Expected: success.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add docs/upstream-sync.md upstream/manifest.json scripts/sync-from-upstream.sh
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "chore: add overlay sync workflow"
```

## Task 5 [Completed Historical Baseline]: Sync Selected Existing App Surfaces Into The Private Repo

Historical baseline only. This task is already completed in the current private repo and is preserved for implementation history.

**Files:**
- Create or refresh via sync script:
  - `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/web/`
  - `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/extension/`
  - `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/shared-ui/`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/upstream/manifest.json`
  - Record source repo commit and exact synced path list.

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

- [ ] **Step 4: Record the exact upstream commit and synced paths in the manifest**

```json
{
  "source_repo": "/Users/macbook-dev/Documents/GitHub/tldw_server2",
  "source_commit": "abc123",
  "paths": ["apps/tldw-frontend/...", "apps/extension/...", "apps/packages/ui/src/..."]
}
```

- [ ] **Step 5: Re-run the sync script and verify vendored sources appear**

Run: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/scripts/sync-from-upstream.sh`
Expected: success with copied upstream surfaces and no accidental writes back into `tldw_server2`.

- [ ] **Step 6: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add upstream scripts/sync-from-upstream.sh docs/upstream-sync.md
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "chore: import upstream app surfaces"
```

## Task 6 [Completed Historical Baseline]: Add Private Overlay Client And Intent Helpers

Historical baseline only. This task is already completed in the current private repo and is preserved for implementation history.

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

## Task 7 [Completed Historical Baseline]: Build The Private Hosted Lightweight Workspace And Signed-In Intake

Historical baseline only. This task is already completed in the current private repo and is preserved for implementation history.

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/components/VideoWorkspacePage.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/new.tsx`
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

it("renders a signed-in paste-url intake flow for non-youtube sources", () => {
  render(<LiteNewPage />)
  expect(screen.getByLabelText(/source url/i)).toBeVisible()
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

- [ ] **Step 4: Implement the signed-in hosted intake page**

```tsx
export default function LiteNewPage() {
  return <SourceUrlIntakeForm />
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/web/VideoWorkspacePage.test.tsx -v`
Expected: PASS for ready, processing, failure, trial-exhausted, signed-in-unsubscribed states, and signed-in pasted-source intake.

- [ ] **Step 6: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add web/components/VideoWorkspacePage.tsx web/pages/lite/new.tsx web/pages/lite/video/[sourceKey].tsx web/pages/lite/upgrade.tsx web/pages/login.tsx tests/web/VideoWorkspacePage.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: add private hosted video-lite workspace"
```

## Task 8 [Completed Historical Baseline]: Build The Private Extension Launcher Overlay

Historical baseline only. This task is already completed in the current private repo and is preserved for implementation history.

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
Include coverage for exhausted-trial users reopening an already unlocked source without starting a new session.

- [ ] **Step 5: Commit in the private repo**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add extension/src/routes/sidepanel-video.tsx extension/src/background/video-lite.ts tests/extension/sidepanel-video.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: add private extension video-lite launcher"
```

## Task 9 [Completed Historical Baseline]: Verification, Security Checks, And Sync Discipline

Historical baseline only. This task is already completed for the already-landed baseline work and is preserved for implementation history.

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
  tldw_Server_API/tests/Media/test_video_lite_endpoint.py \
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

## Task 10: Refactor `video-lite` To Paid-Only Access Gating

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py`
- Modify: `tldw_Server_API/app/services/video_lite_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/video_lite.py`
- Modify: `tldw_Server_API/tests/Media/test_video_lite_endpoint.py`

- [ ] **Step 1: Write the failing access-gating tests**

```python
def test_video_lite_source_requires_login_when_signed_out(client):
    response = client.post(
        "/api/v1/media/video-lite/source",
        json={"source_url": "https://www.youtube.com/watch?v=abc123", "target_tab": "transcript"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["launcher_access"] == "login_required"
    assert payload["entitlement"] == "signed_out"
```

Also cover:

- signed-in unsubscribed requests returning `launcher_access == "subscription_required"`
- signed-in subscribed requests returning `launcher_access == "allowed"`
- workspace responses using paid-only entitlement values such as `signed_out`, `signed_in_unsubscribed`, and `signed_in_subscribed`

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`
Expected: FAIL because the current baseline still carries trial-aware assumptions.

- [ ] **Step 3: Implement the paid-only source and workspace contract updates**

```python
@router.get("/video-lite/workspace/{source_key}", response_model=VideoLiteWorkspaceResponse)
async def get_video_lite_workspace(...):
    return await service.get_workspace(...)
```

`POST /video-lite/source` should return:

- `launcher_access` in `{"login_required", "subscription_required", "allowed"}`
- `entitlement` in `{"signed_out", "signed_in_unsubscribed", "signed_in_subscribed"}`
- normalized source identity fields

The active implementation must remove trial-aware routing from the live contract path. Signed-out requests may resolve source identity for routing, but they must not start ingest.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`
Expected: PASS for paid-only launcher access and workspace entitlement behavior.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py \
        tldw_Server_API/app/services/video_lite_service.py \
        tldw_Server_API/app/api/v1/endpoints/media/video_lite.py \
        tldw_Server_API/tests/Media/test_video_lite_endpoint.py
git commit -m "feat: gate video-lite behind login and subscription"
```

## Task 11: Wire Resource-Governor Coverage And Paid Launcher Routing

**Files:**
- Modify: `tldw_Server_API/Config_Files/resource_governor_policies.yaml`
- Modify: `tldw_Server_API/tests/Resource_Governance/test_video_lite_route_map_coverage.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-client.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/extension/src/background/video-lite.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/extension/sidepanel-video.test.tsx`

- [ ] **Step 1: Write the failing RG and launcher-routing tests**

Cover:

- `/api/v1/media/video-lite/workspace/{source_key}` resolving to the intended policy
- extension launcher routing `login_required` into login
- extension launcher routing `subscription_required` into upgrade
- `Ingest` remaining unavailable until `launcher_access == "allowed"`

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run backend:
`source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Resource_Governance/test_video_lite_route_map_coverage.py -v`

Run frontend:
`cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/extension/sidepanel-video.test.tsx -v`

Expected: FAIL because the workspace RG mapping and paid-only launcher routing are not fully implemented yet.

- [ ] **Step 3: Implement RG mapping and launcher-routing updates**

Add the route-map entry and make the extension treat:

- `login_required` as login routing
- `subscription_required` as upgrade routing
- `allowed` as the only state that may continue into ingest or workspace launch

- [ ] **Step 4: Run the tests to verify they pass**

Run backend:
`source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Resource_Governance/test_video_lite_route_map_coverage.py -v`

Run frontend:
`cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/extension/sidepanel-video.test.tsx -v`

Expected: PASS for RG route coverage and launcher routing behavior.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/Config_Files/resource_governor_policies.yaml \
        tldw_Server_API/tests/Resource_Governance/test_video_lite_route_map_coverage.py
git commit -m "feat: add video-lite workspace RG policy"
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add \
  web/lib/video-lite-client.ts \
  extension/src/background/video-lite.ts \
  tests/extension/sidepanel-video.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: update paid-only launcher routing"
```

## Task 12: Add Eager Summary Generation And Workspace Rendering

**Files:**
- Modify: `tldw_Server_API/app/services/video_lite_service.py`
- Modify: `tldw_Server_API/tests/Media/test_video_lite_endpoint.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/lib/video-lite-client.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/pages/lite/video/[sourceKey].tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/web/components/VideoWorkspacePage.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/tests/web/VideoWorkspacePage.test.tsx`

- [ ] **Step 1: Write the failing eager-summary tests**

```python
def test_video_lite_generates_summary_once_when_transcript_ready(...):
    ...
```

```tsx
it("renders summary processing and summary ready states from backend workspace data", async () => {
  ...
})
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run backend:
`source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`

Run frontend:
`cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/web/VideoWorkspacePage.test.tsx -v`

Expected: FAIL because eager summary generation and workspace-backed rendering are not implemented yet.

- [ ] **Step 3: Implement eager summary generation and caching in the backend**

```python
async def ensure_workspace_summary(...):
    ...
```

Use one background-trigger path only. Transcript readiness should enqueue at most one summary job per normalized source or transcript hash using a dedupe key or equivalent lock. `GET /video-lite/workspace/...` must remain read-only and should not spawn duplicate LLM work during polling.

- [ ] **Step 4: Update the hosted page to fetch backend workspace state**

```tsx
export default function LiteVideoPage() {
  const workspace = await getVideoLiteWorkspace(...)
  return <VideoWorkspacePage initialState={workspace} />
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run backend:
`source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_video_lite_endpoint.py -v`

Run frontend:
`cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test tests/web/VideoWorkspacePage.test.tsx -v`

Expected: PASS for one-time summary generation, summary reuse on reopen, and hosted rendering of `processing`, `ready`, and `failed` summary states.

- [ ] **Step 6: Commit**

```bash
git add tldw_Server_API/app/services/video_lite_service.py \
        tldw_Server_API/tests/Media/test_video_lite_endpoint.py \
        Docs/superpowers/specs/2026-04-05-video-transcript-saas-extension-design.md \
        Docs/superpowers/plans/2026-04-05-video-transcript-saas-extension-implementation-plan.md
git commit -m "feat: add eager video-lite summaries"
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add \
  web/lib/video-lite-client.ts \
  web/pages/lite/video/[sourceKey].tsx \
  web/components/VideoWorkspacePage.tsx \
  tests/web/VideoWorkspacePage.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "feat: render eager video-lite summaries"
```

## Task 13: Verify The Remaining Delta Work

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw-video-lite-private/docs/verification.md`
  - Add the remaining contract and eager-summary verification steps.

- [ ] **Step 1: Run backend verification for the active delta**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Media/test_video_lite_endpoint.py \
  tldw_Server_API/tests/Resource_Governance/test_video_lite_route_map_coverage.py -v
```

Expected: PASS for source-state, launcher-entitlement, workspace-state, eager-summary, and RG coverage.

- [ ] **Step 2: Run Bandit on the touched backend paths**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/schemas/video_lite_schemas.py \
  tldw_Server_API/app/services/video_lite_service.py \
  tldw_Server_API/app/api/v1/endpoints/media/video_lite.py \
  -f json -o /tmp/bandit_video_lite_delta.json
```

Expected: JSON report written to `/tmp/bandit_video_lite_delta.json` with no new high-signal findings in touched code.

- [ ] **Step 3: Run private repo verification for the active delta**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private && bun test \
  tests/shared/video-lite-intent.test.ts \
  tests/web/VideoWorkspacePage.test.tsx \
  tests/extension/sidepanel-video.test.tsx -v
```

Expected: PASS for updated hosted workspace and launcher behavior.

- [ ] **Step 4: Commit verification docs updates**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private add docs/verification.md
git -C /Users/macbook-dev/Documents/GitHub/tldw-video-lite-private commit -m "docs: update video-lite delta verification guide"
```

## Notes For The Implementer

- Do not ship the store-facing extension or hosted app from `apps/` inside `tldw_server`.
- Treat `tldw_server2/apps` as upstream input, not the delivery repo.
- Keep the private patch layer intentionally small and well-bounded.
- Prefer wrapper files and private routes over invasive edits to vendored upstream files when possible.
- Treat the extension as launcher-only in V1; transcript reading and durable chat stay in the hosted workspace.
- Make launcher routing depend on identity-aware access state from the backend contract, not on source normalization alone.
- Use the exact `launcher_access` enum values locked in Task `10`; do not invent parallel frontend-only variants.
- Generate the default summary server-side as part of workspace readiness; do not make the hosted page the system of record for summary generation.
- Keep workspace reads read-only; do not let polling create duplicate summarization work.
- Do not add a client-triggered summary create, regenerate, or retry control in V1.
- Preserve source key and target-tab intent through login and upgrade flows.
