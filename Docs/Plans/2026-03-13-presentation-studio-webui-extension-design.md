# Presentation Studio WebUI + Extension Design

Date: 2026-03-13
Owner: Codex collaboration session
Status: Approved (design)

## Context and Problem

The project already has partial presentation, image, and audio foundations:

- Shared WebUI and extension route/component architecture in `apps/packages/ui`.
- Existing slide and presentation CRUD/export APIs under `/api/v1/slides`.
- Existing TTS endpoints and Jobs-backed artifact flows under `/api/v1/audio`.
- Existing image-generation settings and prompt plumbing in shared UI.

What does not exist yet is a cohesive product surface for creating a narrated slideshow or presentation, editing it before finalization, and publishing a finished video.

The requested experience is:

- users can start from a blank project,
- create and reorder structured slides,
- upload or generate one image per slide,
- write narration per slide,
- generate TTS audio per slide,
- edit and review the project before finalization,
- publish a finished narrated video,
- use the extension as a quick-start and capture handoff into the WebUI editor.

## Goals

1. Create a dedicated `Presentation Studio` product surface for structured slideshow authoring.
2. Keep the editor shared at the UI layer where possible, with the full editor in WebUI and quick-start in the extension.
3. Reuse existing slides, TTS, image-generation, and Jobs patterns where they fit.
4. Support editable drafts, partial regeneration, and version-aware publishing.
5. Ship a realistic v1 without introducing freeform canvas or code-authored scene editing.

## Non-Goals

1. Building a code-first Three.js or custom-JS presentation runtime in v1.
2. Supporting arbitrary freeform object placement, layers, or keyframes in v1.
3. Hosting the full editor inside the extension in v1.
4. Treating `mp4` and `webm` video publish as a synchronous export bolted onto the existing slides export endpoint.
5. Reusing the current slides API unchanged and pretending it already supports all studio needs.

## User-Approved Product Decisions

- Product shape: hybrid flow, with draft generation/import opportunities later and a dedicated editor surface now.
- Primary start mode in v1: blank project.
- Primary output in v1: editable project plus rendered narrated video.
- Authoring model: structured slides, not code-authored scenes.
- Extension role: quick-start and capture only; the full editor and export live in WebUI.
- Slide visuals in v1: one image per slide plus simple layout and background controls.
- Timing model: each slide owns its narration script, and duration is derived from generated slide audio.

## Current Verified Constraints

### Shared route architecture already exists

The repo uses shared route components from `apps/packages/ui/src/routes` and thin wrappers in:

- `apps/tldw-frontend/pages`
- `apps/tldw-frontend/extension/routes`
- `apps/extension/entrypoints/*`

This makes a shared studio route the correct frontend architecture.

### Slides and presentations already exist, but they are not a studio model

The current slides schema supports:

- presentation CRUD and version history,
- slide ordering,
- exports to `revealjs`, `markdown`, `json`, and `pdf`,
- slide layouts: `title`, `content`, `two_column`, `quote`, `section`, `blank`.

The current API does not provide:

- a dedicated studio metadata field,
- asset-reference support for slide images,
- a narrated video render pipeline,
- presentation render job APIs,
- slides/studio/render capability flags.

### `settings` is not a free-form project metadata bucket

`presentation.settings` is currently restricted to a reveal.js-style allowlist, so project-level studio state cannot be safely stored there without backend changes.

### Slide metadata is flexible, but current image handling is inline-only

Slide metadata can carry editor-specific data, but current image validation rejects `asset_ref` and expects inline base64 image payloads. Repeated autosave against versioned presentations would therefore bloat storage unless asset-reference support is added.

### Existing TTS Jobs patterns can be reused

The repo already has:

- TTS job submission,
- artifact listing,
- SSE progress streaming,
- output artifact download patterns.

That makes Jobs the right default for narrated video rendering as well.

## Evaluated Approaches

### Approach 1: Recommended, dedicated `Presentation Studio` built on additive slides support

- Add a dedicated studio route family and project workspace.
- Reuse presentation records as the saved document.
- Add explicit studio metadata, asset references, and render jobs.
- Keep the full editor in WebUI and make the extension a seeded handoff surface.

Pros:

- best fit for the requested product,
- fits shared WebUI/extension architecture,
- reuses existing slide versioning and export foundations,
- keeps room for future `WorkspacePlayground` import,
- avoids overloading `WorkspacePlayground` with editor responsibilities.

Cons:

- requires additive backend work,
- needs a careful split between existing slide exports and new video render jobs.

### Approach 2: Thin UI directly over current slides APIs

- Treat the current presentation schema as fully sufficient.
- Build the editor mostly as a frontend wrapper over existing presentation CRUD.

Pros:

- smaller immediate backend scope,
- faster to prototype.

Cons:

- project-level studio metadata does not fit current `settings`,
- image asset lifecycle does not fit current inline-only image handling,
- video publish remains undefined,
- autosave/versioning will be inefficient if media stays embedded.

### Approach 3: Local-first draft model compiled into slides only at publish time

- Store the entire studio draft client-side or in a parallel draft system.
- Only convert into presentations or video outputs later.

Pros:

- maximal editor flexibility,
- easy experimentation with non-schema concepts.

Cons:

- duplicates existing presentation/version infrastructure,
- makes extension/WebUI continuity harder,
- creates a second source of truth,
- increases long-term migration risk.

## Selected Approach

Use Approach 1.

`Presentation Studio` should be a dedicated shared product surface that persists on top of the existing presentation model, but only after additive backend support is added for:

1. project-level studio metadata,
2. slide asset references,
3. narrated video render jobs,
4. capability detection for slides/studio/render availability.

## Route Architecture

### WebUI

- `/presentation-studio`
- `/presentation-studio/new`
- `/presentation-studio/:projectId`

### Extension

- `/presentation-studio/start`

### Optional later

- `/presentation-studio/:projectId/publish-history`

### Route responsibilities

- `/presentation-studio` shows recent projects, statuses, and resume actions.
- `/presentation-studio/new` creates a blank project with title, theme, default voice, and the first slide.
- `/presentation-studio/:projectId` is the full editor.
- `/presentation-studio/start` in the extension collects quick-start inputs and seeds a server-backed project, then opens the WebUI editor.

## Canonical Project Model

The user-facing concept is a `Presentation Studio Project`, but the saved document remains a presentation record with additive studio support.

### Existing presentation fields remain canonical for document content

- `title`
- `description`
- `theme`
- `marp_theme`
- `slides`

### New project-level studio field is required

Add a dedicated backend field such as `studio_data` or `project_metadata` for:

- project origin: `blank`, `workspace_playground`, `extension_capture`
- default TTS provider, model, and voice
- preferred publish formats
- draft and publish status
- latest successful render references
- editor-only project defaults

Do not rely on `presentation.settings` for this metadata.

### Slide model

Each slide remains structured:

- `order`
- `layout`
- `title`
- `content`
- `speaker_notes`
- `metadata`

### Narration source of truth

Use `speaker_notes` as the slide narration script in v1.

Reasons:

- it already exists in the schema,
- current generation paths already populate it,
- current search/export flattening already understands it,
- it avoids inventing a parallel narration field.

### Stable slide identity

Add a stable editor ID per slide in metadata:

- `metadata.studio.slideId`

This is needed for reorder handling, autosave merges, and asset binding.

### Layout scope for v1

Use current backend-supported layouts only:

- `title`
- `content`
- `two_column`
- `quote`
- `section`
- `blank`

If richer visual treatments are needed, store a visual preset in slide metadata rather than immediately expanding the backend layout enum.

## Editor Workflow And UI Composition

The editor should behave like a structured production studio, not a generic form or freeform canvas.

### Desktop layout

Use a three-pane workspace:

- left rail: slide list and project controls,
- center pane: active slide editor and visual preview,
- right rail: narration, image, and publish controls.

On smaller screens, collapse into stacked panes while preserving the same editing model.

### Left rail

- project title and status,
- add slide,
- duplicate slide,
- delete slide,
- drag-reorder slide cards,
- quick per-slide state:
  - image present/missing,
  - audio ready/missing/stale,
  - render error,
  - current selection.

### Center pane

- layout selector,
- title field,
- body/content field,
- image preview area,
- simple background or visual preset controls,
- lightweight slide preview frame.

### Right rail

#### Narration

- narration editor bound to `speaker_notes`,
- generate audio,
- regenerate audio,
- audio player,
- derived duration display.

#### Image

- upload image,
- generate image from prompt,
- regenerate image,
- clear or replace image.

#### Publish

- latest publish status,
- publish to `mp4`,
- publish to `webm`,
- links to prior render artifacts,
- explicit split between:
  - `Export slides`
  - `Render video`

### Core user flow

1. Create blank project.
2. Add and order slides.
3. Edit title, body, and narration for each slide.
4. Upload or generate one image per slide.
5. Generate TTS audio per slide.
6. Review sequence-level timing through derived audio durations.
7. Publish a narrated video.

## Data Flow And Derivative Asset Model

Separate the system into three layers.

### 1) Editable project data

This is the source of truth.

- presentation fields store document content,
- studio_data stores project-level editor state,
- slide metadata stores lightweight editor and asset references.

### 2) Generated slide assets

These are derivatives:

- image assets,
- audio assets.

They should be stored out-of-line and referenced from the presentation, not embedded inline long-term.

### 3) Project-level rendered outputs

These are publish artifacts:

- `mp4`
- `webm`

They should be versioned and tracked separately from the mutable draft.

### Invalidation rules

- change narration => slide audio becomes stale,
- change image prompt or uploaded image => slide image becomes stale,
- reorder slides => rendered video becomes stale,
- change theme, visual preset, or project-level render settings => rendered video becomes stale.

## Asset Storage Design

The design requires additive asset-reference support.

### Slide images

Current inline base64 image support is acceptable for compatibility but is not suitable as the primary long-term storage model for Presentation Studio autosave.

Recommended direction:

- support `asset_ref` in slide image metadata, or
- add a dedicated slide-assets model keyed by `presentation_id` plus `slideId`.

### Slide audio

Use generated TTS artifacts as stored outputs and reference them from the slide.

Recommended metadata shape:

- `metadata.studio.audioAssetRef`
- `metadata.studio.audioDurationMs`
- `metadata.studio.audioStatus`

### Why asset references are required

- avoids version-history bloat,
- makes autosave practical,
- supports partial regeneration,
- keeps project payloads lightweight enough to patch frequently.

## Publish And Render Model

### Existing slide-native exports remain separate

Current slides exports continue to cover:

- `revealjs`
- `markdown`
- `json`
- `pdf`

### Narrated video publish is a new backend surface

`mp4` and `webm` publish should be implemented as a Jobs-backed render pipeline, not as a synchronous slide export format.

### Render job requirements

Add APIs for:

- submit render job for a presentation version,
- poll render status or stream progress,
- list render artifacts,
- download render artifacts.

### Render snapshot rule

Publish must target a specific saved presentation version.

If the user continues editing after submitting a render:

- the in-flight render uses the old saved version,
- the editor reflects newer draft changes,
- the project can show `draft newer than published output`.

This matches the current versioned presentation storage model.

## Autosave And Concurrency Model

The current slides API already uses optimistic locking with `ETag` and `If-Match`, so the editor must be version-aware.

### Recommended autosave behavior

1. Load presentation and current `ETag`.
2. Debounce autosave.
3. Save using `PATCH` or `PUT` with `If-Match`.
4. On `412 precondition_failed`, refetch, merge local unsaved changes, and retry.
5. On `428 if_match_required`, force recovery and refetch.

### What should autosave frequently

- project title and description,
- slide text fields,
- `speaker_notes`,
- slide order,
- lightweight visual presets,
- image prompts,
- asset references.

### What should not be autosaved inline repeatedly

- large embedded media blobs,
- heavyweight preview caches,
- transient render pipeline state.

## Capability Detection

Add explicit server capability flags for this feature set:

- `hasSlides`
- `hasPresentationStudio`
- `hasPresentationRender`
- optional later: `hasPresentationAssets`

### UI gating rules

- if `hasSlides` is false, hide the studio route,
- if `hasSlides` is true but `hasPresentationStudio` is false, show a feature-unavailable state,
- if render is unavailable, allow editing and slide-native export but disable `mp4` and `webm` publish.

## Extension Role

The extension provides quick-start and capture only.

### Supported v1 extension actions

- start blank project in WebUI,
- seed project title from page title,
- seed slide content or narration from selected text,
- seed the first slide image from a screenshot or captured image.

### Handoff rule

The extension should create or seed a server-backed project first, receive a `projectId`, and then open the WebUI editor at `/presentation-studio/:projectId`.

Do not rely on query-parameter-only handoff or local transient payloads.

## Failure Handling

Keep failures local whenever possible.

### Per-slide failures

- image generation failure affects only that slide,
- TTS generation failure affects only that slide,
- previous successful asset stays usable when possible,
- users can retry or replace the failed asset manually.

### Project-level failures

- render job failure does not corrupt the draft,
- last successful published artifact remains visible,
- editor should surface whether the draft is newer than the latest publish.

### Recommended states

Per-slide image and audio state:

- `missing`
- `ready`
- `generating`
- `failed`
- `stale`

Project render state:

- `not_published`
- `rendering`
- `published`
- `publish_failed`
- `published_stale`

## Testing Strategy

### Shared UI tests in `apps/packages/ui`

- route coverage for new studio routes,
- store and helper tests for invalidation rules,
- component tests for slide list operations,
- narration and image panel tests,
- autosave and conflict-handling tests,
- publish state and failure-state tests.

### WebUI tests

- page wrapper tests,
- editor boot smoke,
- autosave smoke,
- publish status polling behavior.

### Extension tests

- quick-start route behavior only,
- seeded project handoff tests,
- captured text or image handoff coverage.

### Backend tests

- schema and API coverage for project-level studio metadata,
- slide asset-reference validation,
- autosave and optimistic-lock conflict behavior,
- render job submit/status/artifact endpoints,
- presentation version to render snapshot mapping.

### End-to-end acceptance path

1. Create a blank project.
2. Add three slides.
3. Generate or upload images.
4. Generate TTS audio for each slide.
5. Reorder a slide.
6. Publish `mp4`.
7. Verify the artifact is listed and downloadable.

Also include a failure-recovery path for one failed slide asset followed by a successful publish.

## Recommended V1 Scope Guardrails

Ship in v1:

- blank project creation,
- structured slide editing,
- one image per slide,
- narration in `speaker_notes`,
- per-slide TTS generation,
- version-aware autosave,
- WebUI editor,
- extension quick-start handoff,
- Jobs-backed video rendering.

Explicitly defer:

- freeform canvas editing,
- arbitrary layers and positioning,
- custom scene code,
- Three.js authoring,
- full extension editor parity,
- manual duration editing as the primary model,
- transition scripting,
- large inline media persistence as the default.

## Future Expansion

After v1 is stable, the most natural next steps are:

1. import from `WorkspacePlayground`,
2. batch regenerate stale assets,
3. richer visual presets and templates,
4. better sequence preview,
5. optional manual duration overrides,
6. deeper extension capture flows,
7. eventual advanced animation or code-authoring experiments in a clearly separate mode.

## Success Criteria

1. Users can create a blank presentation project and edit it safely before finalization.
2. Narration, images, and final video outputs are treated as derivatives, not the draft source of truth.
3. The editor survives autosave conflicts and render failures without losing work.
4. The extension can seed a project and hand off cleanly to the WebUI.
5. The system uses explicit additive backend support rather than overloading current slide APIs beyond their existing contract.
