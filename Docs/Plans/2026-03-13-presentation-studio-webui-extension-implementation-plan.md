# Presentation Studio WebUI + Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a dedicated Presentation Studio that lets users create structured narrated slide decks in the WebUI, seed projects from the extension, and publish versioned `mp4` or `webm` render artifacts through a Jobs-backed backend pipeline.

**Architecture:** Extend the existing slides/presentations model with explicit `studio_data`, lightweight slide-level asset references, and new presentation render jobs instead of overloading the current slide export endpoints. Keep the editor in shared UI code, mount it with thin WebUI wrappers, and limit the extension to a quick-start handoff flow that creates a server-backed project and opens the WebUI editor.

**Tech Stack:** FastAPI, SQLite slides DB migrations, core Jobs + WorkerSDK, existing output artifacts storage, ffmpeg render orchestration, React 18, TypeScript, Zustand, Next.js page wrappers, WXT extension routing, Vitest, Playwright, pytest, Bandit.

---

## Preflight

Before Task 1, create an isolated worktree and do all implementation there.

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2 worktree add \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-presentation-studio \
  -b codex/presentation-studio
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-presentation-studio
git status --short
```

Expected:

- new branch `codex/presentation-studio`
- clean worktree before implementation starts

## Implementation Order

1. Backend presentation schema and persistence for `studio_data`
2. Slide asset references for image and audio derivatives
3. Presentation render jobs and artifact endpoints
4. Frontend capability detection and API client support
5. Shared Presentation Studio routes, store, and editor shell
6. Extension quick-start handoff
7. Verification, docs, and cleanup

### Task 1: Add `studio_data` to the Presentation Model

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/slides_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/slides.py`
- Modify: `tldw_Server_API/app/core/Slides/slides_db.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/config_info.py`
- Test: `tldw_Server_API/tests/Slides/test_slides_api.py`
- Test: `tldw_Server_API/tests/Slides/test_slides_db.py`

**Step 1: Write the failing tests**

Add API and DB coverage for create/get/patch persistence:

```python
def test_create_presentation_persists_studio_data(client, auth_headers):
    payload = {
        "title": "Deck",
        "slides": [
            {
                "order": 0,
                "layout": "title",
                "title": "Deck",
                "content": "",
                "speaker_notes": "Intro",
                "metadata": {},
            }
        ],
        "studio_data": {
            "origin": "blank",
            "defaults": {"tts_provider": "openai", "tts_voice": "alloy"},
            "publish": {"formats": ["mp4", "webm"]},
        },
    }
    response = client.post("/api/v1/slides/presentations", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["studio_data"]["origin"] == "blank"
    assert body["studio_data"]["defaults"]["tts_voice"] == "alloy"


def test_patch_presentation_updates_studio_data(client, created_presentation, auth_headers):
    presentation_id, etag = created_presentation
    response = client.patch(
        f"/api/v1/slides/presentations/{presentation_id}",
        json={"studio_data": {"origin": "extension_capture"}},
        headers={**auth_headers, "If-Match": etag},
    )
    assert response.status_code == 200
    assert response.json()["studio_data"]["origin"] == "extension_capture"
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Slides/test_slides_db.py -k studio_data -v
```

Expected:

- FAIL because `studio_data` is not in the schema or DB yet

**Step 3: Write the minimal implementation**

Implement:

- `studio_data: dict[str, Any] | None` on presentation create, update, patch, and response models
- `_validate_studio_data()` in `slides.py` that accepts only dicts and preserves unknown nested keys for v1
- a `studio_data` column in `SlidesDatabase.presentations`
- version snapshot persistence for `studio_data`
- `config/docs-info` capability keys:
  - `hasSlides`
  - `hasPresentationStudio`

Implementation shape:

```python
class PresentationBase(BaseModel):
    ...
    studio_data: dict[str, Any] | None = None


def _validate_studio_data(studio_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if studio_data is None:
        return None
    if not isinstance(studio_data, dict):
        raise HTTPException(status_code=422, detail="invalid_studio_data")
    return studio_data
```

**Step 4: Run the tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Slides/test_slides_db.py -k studio_data -v
```

Expected:

- PASS for the new `studio_data` cases

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/slides_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/app/core/Slides/slides_db.py \
  tldw_Server_API/app/api/v1/endpoints/config_info.py \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Slides/test_slides_db.py
git commit -m "feat(slides): add studio metadata to presentations"
```

### Task 2: Add Slide Asset References for Images and Audio

**Files:**
- Modify: `tldw_Server_API/app/core/Slides/slides_images.py`
- Create: `tldw_Server_API/app/core/Slides/slides_assets.py`
- Modify: `tldw_Server_API/app/core/Slides/slides_export.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/slides.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/slides_schemas.py`
- Test: `tldw_Server_API/tests/Slides/test_slides_images.py`
- Test: `tldw_Server_API/tests/Slides/test_slides_export.py`
- Test: `tldw_Server_API/tests/Slides/test_slides_api.py`

**Step 1: Write the failing tests**

Add validation and export coverage for referenced assets:

```python
def test_validate_images_payload_accepts_output_asset_ref():
    normalized = validate_images_payload(
        [{"asset_ref": "output:123", "mime": "image/png", "alt": "Cover"}]
    )
    assert normalized[0]["asset_ref"] == "output:123"


def test_export_markdown_resolves_output_asset_ref(tmp_path, monkeypatch):
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Slide",
            "content": "Hello",
            "speaker_notes": "Narration",
            "metadata": {"images": [{"asset_ref": "output:123", "mime": "image/png", "alt": "Cover"}]},
        }
    ]
    monkeypatch.setattr("tldw_Server_API.app.core.Slides.slides_assets.resolve_slide_asset", fake_asset)
    md = export_presentation_markdown(title="Deck", slides=slides, theme="black")
    assert "![Cover](" in md
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_slides_images.py \
  tldw_Server_API/tests/Slides/test_slides_export.py -k asset_ref -v
```

Expected:

- FAIL because `asset_ref` is currently rejected

**Step 3: Write the minimal implementation**

Implement:

- image metadata entries may be either:
  - inline `{data_b64, mime, alt, ...}`
  - reference-based `{asset_ref: "output:<id>", mime, alt, ...}`
- new helper module to parse and resolve `output:<id>` references against output artifacts
- slide export paths resolve referenced images before building markdown or reveal output
- slide metadata contract for audio derivatives:

```python
metadata["studio"] = {
    "slideId": "...",
    "imagePrompt": "...",
    "audio": {
        "asset_ref": "output:456",
        "duration_ms": 12345,
        "status": "ready",
    },
}
```

Guardrails:

- never allow both `data_b64` and `asset_ref` on the same image
- require `mime` and `alt` consistency for referenced images
- keep existing inline support for backward compatibility

**Step 4: Run the tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_slides_images.py \
  tldw_Server_API/tests/Slides/test_slides_export.py \
  tldw_Server_API/tests/Slides/test_slides_api.py -k "asset_ref or studio audio" -v
```

Expected:

- PASS for referenced-image and slide-audio metadata cases

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Slides/slides_images.py \
  tldw_Server_API/app/core/Slides/slides_assets.py \
  tldw_Server_API/app/core/Slides/slides_export.py \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/app/api/v1/schemas/slides_schemas.py \
  tldw_Server_API/tests/Slides/test_slides_images.py \
  tldw_Server_API/tests/Slides/test_slides_export.py \
  tldw_Server_API/tests/Slides/test_slides_api.py
git commit -m "feat(slides): support referenced slide assets"
```

### Task 3: Add Presentation Render Jobs and Versioned Artifacts

**Files:**
- Create: `tldw_Server_API/app/core/Slides/presentation_rendering.py`
- Create: `tldw_Server_API/app/services/presentation_render_jobs_worker.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/slides_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/slides.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/config_info.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Slides/test_presentation_render_jobs.py`
- Test: `tldw_Server_API/tests/Slides/test_presentation_rendering.py`

**Step 1: Write the failing tests**

Add endpoint and renderer tests:

```python
def test_submit_render_job_snapshots_current_presentation_version(client, created_presentation, auth_headers):
    presentation_id, etag = created_presentation
    response = client.post(
        f"/api/v1/slides/presentations/{presentation_id}/render-jobs",
        json={"format": "mp4"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["job_type"] == "presentation_render"
    assert body["presentation_version"] == 1


def test_render_worker_persists_output_artifact(tmp_path):
    result = render_presentation_video(...)
    assert result.output_format == "mp4"
    assert result.storage_path.endswith(".mp4")
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_presentation_render_jobs.py \
  tldw_Server_API/tests/Slides/test_presentation_rendering.py -v
```

Expected:

- FAIL because render-job endpoints and worker do not exist

**Step 3: Write the minimal implementation**

Implement a Jobs-backed render pipeline:

- endpoint `POST /api/v1/slides/presentations/{presentation_id}/render-jobs`
- endpoint `GET /api/v1/slides/render-jobs/{job_id}`
- endpoint `GET /api/v1/slides/presentations/{presentation_id}/render-artifacts`
- worker domain `presentation_render`
- render payload includes:
  - `presentation_id`
  - `presentation_version`
  - `format`
  - `theme`
  - slide asset refs
- worker resolves the exact presentation version snapshot before rendering
- renderer writes `mp4` or `webm` with ffmpeg and persists the result via existing output artifact helpers
- advertise `hasPresentationRender` in docs-info

Implementation shape:

```python
class PresentationRenderRequest(BaseModel):
    format: Literal["mp4", "webm"]


@router.post("/presentations/{presentation_id}/render-jobs")
async def submit_presentation_render_job(...):
    ...
```

**Step 4: Run the tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_presentation_render_jobs.py \
  tldw_Server_API/tests/Slides/test_presentation_rendering.py -v
```

Expected:

- PASS for job submission, version snapshotting, and artifact persistence

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Slides/presentation_rendering.py \
  tldw_Server_API/app/services/presentation_render_jobs_worker.py \
  tldw_Server_API/app/api/v1/schemas/slides_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/app/api/v1/endpoints/config_info.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Slides/test_presentation_render_jobs.py \
  tldw_Server_API/tests/Slides/test_presentation_rendering.py
git commit -m "feat(slides): add presentation render jobs"
```

### Task 4: Extend Frontend Capability Detection and API Client Support

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/server-capabilities.ts`
- Modify: `apps/packages/ui/src/services/__tests__/server-capabilities.test.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/tldw/openapi-guard.ts`
- Modify: `apps/packages/ui/src/routes/route-paths.ts`
- Test: `apps/packages/ui/src/routes/__tests__/route-paths.presentation-studio.test.ts`

**Step 1: Write the failing tests**

Add capability and client contract coverage:

```ts
it("detects presentation studio and render capability from docs-info", async () => {
  getDocsInfoMock.mockResolvedValue({
    capabilities: { hasSlides: true, hasPresentationStudio: true, hasPresentationRender: true }
  })
  const caps = await getServerCapabilities()
  expect(caps.hasPresentationStudio).toBe(true)
  expect(caps.hasPresentationRender).toBe(true)
})

it("builds presentation studio route constants", () => {
  expect(PRESENTATION_STUDIO_PATH).toBe("/presentation-studio")
  expect(PRESENTATION_STUDIO_NEW_PATH).toBe("/presentation-studio/new")
  expect(PRESENTATION_STUDIO_DETAIL_PATH).toBe("/presentation-studio/:projectId")
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/server-capabilities.test.ts \
  apps/packages/ui/src/routes/__tests__/route-paths.presentation-studio.test.ts
```

Expected:

- FAIL because the capability flags and path constants do not exist

**Step 3: Write the minimal implementation**

Implement:

- new capability flags on `ServerCapabilities`
- fallback path detection for:
  - studio routes
  - render-job endpoints
- new client methods:
  - `createPresentation(...)`
  - `patchPresentation(...)`
  - `submitPresentationRenderJob(...)`
  - `getPresentationRenderJob(...)`
  - `listPresentationRenderArtifacts(...)`
- add route constants:
  - `PRESENTATION_STUDIO_PATH`
  - `PRESENTATION_STUDIO_NEW_PATH`
  - `PRESENTATION_STUDIO_DETAIL_PATH`
  - `PRESENTATION_STUDIO_START_PATH`

Reference implementation pattern:

- existing slide methods around `generateSlidesFromMedia()` and `getPresentation()`
- existing TTS job methods around `createTtsJob()` and `getTtsJobArtifacts()`

**Step 4: Run the tests to verify they pass**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/server-capabilities.test.ts \
  apps/packages/ui/src/routes/__tests__/route-paths.presentation-studio.test.ts
```

Expected:

- PASS for capability detection and route constants

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/tldw/server-capabilities.ts \
  apps/packages/ui/src/services/__tests__/server-capabilities.test.ts \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/services/tldw/openapi-guard.ts \
  apps/packages/ui/src/routes/route-paths.ts \
  apps/packages/ui/src/routes/__tests__/route-paths.presentation-studio.test.ts
git commit -m "feat(ui): add presentation studio API plumbing"
```

### Task 5: Build the Shared Presentation Studio Workspace and Editor Shell

**Files:**
- Create: `apps/packages/ui/src/store/presentation-studio.tsx`
- Create: `apps/packages/ui/src/hooks/usePresentationStudioAutosave.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/PresentationStudioPage.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/ProjectWorkspace.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/SlideRail.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/SlideEditorPane.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/MediaRail.tsx`
- Create: `apps/packages/ui/src/routes/option-presentation-studio.tsx`
- Create: `apps/packages/ui/src/routes/option-presentation-studio-new.tsx`
- Create: `apps/packages/ui/src/routes/option-presentation-studio-detail.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Modify: `apps/packages/ui/src/services/settings/ui-settings.ts`
- Test: `apps/packages/ui/src/routes/__tests__/option-presentation-studio-route-guards.test.tsx`
- Test: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`
- Test: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx`
- Create: `apps/tldw-frontend/pages/presentation-studio.tsx`
- Create: `apps/tldw-frontend/pages/presentation-studio/new.tsx`
- Create: `apps/tldw-frontend/pages/presentation-studio/[projectId].tsx`

**Step 1: Write the failing tests**

Add route and editor-shell coverage:

```tsx
it("guards the presentation studio routes behind capability checks", () => {
  mockCapabilities({ hasSlides: true, hasPresentationStudio: false })
  render(<OptionPresentationStudio />)
  expect(screen.getByText(/not available/i)).toBeInTheDocument()
})

it("marks audio stale when speaker_notes change", () => {
  const store = usePresentationStudioStore.getState()
  store.loadProject(sampleProject)
  store.updateSlide(sampleProject.slides[0].metadata.studio.slideId, { speaker_notes: "New narration" })
  expect(usePresentationStudioStore.getState().slides[0].metadata.studio.audio.status).toBe("stale")
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/routes/__tests__/option-presentation-studio-route-guards.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx
```

Expected:

- FAIL because the store, routes, and components do not exist yet

**Step 3: Write the minimal implementation**

Implement:

- shared Zustand store with:
  - project metadata
  - slide list
  - selected slide
  - stale and ready asset state
  - current `etag`
- autosave hook that debounces patches and handles `412` refetch-and-merge
- three-pane layout:
  - `SlideRail`
  - `SlideEditorPane`
  - `MediaRail`
- route wrappers matching the existing sources pattern
- WebUI page wrappers with `ssr: false`

Reference files to copy the shape from:

- `apps/packages/ui/src/store/audiobook-studio.tsx`
- `apps/packages/ui/src/routes/option-sources-new.tsx`
- `apps/tldw-frontend/pages/sources/new.tsx`

**Step 4: Run the tests to verify they pass**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/routes/__tests__/option-presentation-studio-route-guards.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx
```

Expected:

- PASS for route guards, store invalidation, and editor shell behavior

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/store/presentation-studio.tsx \
  apps/packages/ui/src/hooks/usePresentationStudioAutosave.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio \
  apps/packages/ui/src/routes/option-presentation-studio.tsx \
  apps/packages/ui/src/routes/option-presentation-studio-new.tsx \
  apps/packages/ui/src/routes/option-presentation-studio-detail.tsx \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/components/Layouts/header-shortcut-items.ts \
  apps/packages/ui/src/services/settings/ui-settings.ts \
  apps/packages/ui/src/routes/__tests__/option-presentation-studio-route-guards.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__ \
  apps/tldw-frontend/pages/presentation-studio.tsx \
  apps/tldw-frontend/pages/presentation-studio/new.tsx \
  apps/tldw-frontend/pages/presentation-studio/[projectId].tsx
git commit -m "feat(ui): add presentation studio editor shell"
```

### Task 6: Add the Extension Quick-Start Handoff

**Files:**
- Create: `apps/packages/ui/src/routes/option-presentation-studio-start.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/ExtensionStartPanel.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/extension/tests/e2e/page-inventory.ts`
- Test: `apps/packages/ui/src/routes/__tests__/option-presentation-studio-start.test.tsx`
- Test: `apps/extension/tests/e2e/presentation-studio-start.spec.ts`

**Step 1: Write the failing tests**

Add quick-start coverage:

```tsx
it("creates a server-backed project and opens the WebUI detail route", async () => {
  tldwClient.createPresentation = vi.fn().mockResolvedValue({ id: "pres-123", version: 1 })
  render(<OptionPresentationStudioStart />)
  await userEvent.click(screen.getByRole("button", { name: /start blank in webui/i }))
  expect(tldwClient.createPresentation).toHaveBeenCalled()
  expect(openWebUiMock).toHaveBeenCalledWith("/presentation-studio/pres-123")
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/option-presentation-studio-start.test.tsx
```

Expected:

- FAIL because the extension start route does not exist

**Step 3: Write the minimal implementation**

Implement:

- extension-only route `/presentation-studio/start`
- UI fields for:
  - project title
  - optional selected text or narration seed
  - optional screenshot or image upload
- blank-project CTA and seeded-project CTA
- create the project through `createPresentation()`
- open WebUI at `/presentation-studio/:projectId`

Keep v1 simple:

- active tab title is prefilled when available
- selected text and screenshot can be optional rather than mandatory
- no full editor inside extension

**Step 4: Run the tests to verify they pass**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/option-presentation-studio-start.test.tsx
```

Expected:

- PASS for project creation and WebUI handoff behavior

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/routes/option-presentation-studio-start.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/ExtensionStartPanel.tsx \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/extension/tests/e2e/page-inventory.ts \
  apps/packages/ui/src/routes/__tests__/option-presentation-studio-start.test.tsx \
  apps/extension/tests/e2e/presentation-studio-start.spec.ts
git commit -m "feat(extension): add presentation studio quick-start"
```

### Task 7: Verification, Docs, and Security Checks

**Files:**
- Modify: `apps/tldw-frontend/README.md`
- Modify: `Docs/API-related/API_README.md`
- Modify: `Docs/Published/Overview/Feature_Status.md`
- Optional Modify: `Docs/API-related/API_Tags_Index.md`
- Test: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx`
- Test: `tldw_Server_API/tests/Slides/test_presentation_render_jobs.py`

**Step 1: Add the missing docs tests or assertions**

Make sure there is at least one regression test for:

- stale-vs-ready asset badges
- conflict recovery after `412`
- published artifact listing

Example:

```tsx
it("shows draft newer than published output after local edits", async () => {
  render(<PresentationStudioPage />)
  await userEvent.type(screen.getByLabelText(/narration/i), "Updated")
  expect(screen.getByText(/draft newer than published output/i)).toBeInTheDocument()
})
```

**Step 2: Run targeted verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Slides/test_slides_images.py \
  tldw_Server_API/tests/Slides/test_slides_export.py \
  tldw_Server_API/tests/Slides/test_presentation_render_jobs.py \
  tldw_Server_API/tests/Slides/test_presentation_rendering.py -v

bunx vitest run \
  apps/packages/ui/src/services/__tests__/server-capabilities.test.ts \
  apps/packages/ui/src/routes/__tests__/option-presentation-studio-route-guards.test.tsx \
  apps/packages/ui/src/routes/__tests__/option-presentation-studio-start.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx
```

Expected:

- all targeted backend and frontend tests PASS

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/app/core/Slides \
  tldw_Server_API/app/services/presentation_render_jobs_worker.py \
  -f json -o /tmp/bandit_presentation_studio.json
```

Expected:

- no new high-signal findings in the touched code

**Step 4: Update docs**

Document:

- studio route locations,
- capability requirements,
- publish behavior and render jobs,
- extension quick-start behavior.

**Step 5: Commit**

```bash
git add \
  apps/tldw-frontend/README.md \
  Docs/API-related/API_README.md \
  Docs/Published/Overview/Feature_Status.md \
  Docs/API-related/API_Tags_Index.md
git commit -m "docs: describe presentation studio routes and render jobs"
```

## Completion Checklist

- backend accepts and persists `studio_data`
- slides accept lightweight asset references
- presentation render jobs create versioned output artifacts
- WebUI routes load and autosave with optimistic-lock handling
- extension quick-start seeds and opens a server-backed project
- targeted pytest, Vitest, and Bandit checks pass

## Suggested First Execution Slice

If implementation must be split across multiple sessions, do this first:

1. Task 1
2. Task 4
3. Task 5

That gives a non-rendering studio shell backed by real presentation persistence before tackling asset refs and video render jobs.
