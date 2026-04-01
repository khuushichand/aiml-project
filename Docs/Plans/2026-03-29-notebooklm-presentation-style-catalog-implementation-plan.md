# NotebookLM Presentation Style Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the PDF's 34 NotebookLM-inspired aesthetics as additive built-in `visual_style` presets with reusable style packs, profile-driven generation, styled Reveal/PDF exports, and a scalable Presentation Studio picker while preserving the current 10 built-ins and existing deck snapshots.

**Architecture:** Keep `theme` constrained to the existing Reveal theme set. Introduce a structured built-in catalog plus resolver that translates a built-in style id into compact snapshot metadata and deck-level appearance fields (`theme`, `settings`, `custom_css`) at create, patch, generate, and export time. Reuse a small family of CSS style packs and prompt profiles so the 34 new styles stay maintainable, then redesign the Presentation Studio selector around grouped searchable metadata rather than a flat `<select>`.

**Tech Stack:** FastAPI, Pydantic v2, existing Slides core modules, Bleach CSS sanitization, Reveal.js export bundle, React, Zustand, Vitest, pytest, Bandit.

---

## File Structure

**Create**
- `tldw_Server_API/app/core/Slides/visual_style_catalog.py` - immutable built-in style definitions for the original 10 presets plus the 34 NotebookLM additions.
- `tldw_Server_API/app/core/Slides/visual_style_profiles.py` - reusable prompt-profile definitions and style-specific prompt overrides.
- `tldw_Server_API/app/core/Slides/visual_style_packs.py` - style-pack metadata, CSS loading, token interpolation, and safe pack compilation helpers.
- `tldw_Server_API/app/core/Slides/visual_style_resolver.py` - resolves built-in styles into compact snapshots and deck-level appearance fields.
- `tldw_Server_API/app/core/Slides/style_packs/hand_drawn_surface.css`
- `tldw_Server_API/app/core/Slides/style_packs/technical_grid.css`
- `tldw_Server_API/app/core/Slides/style_packs/isometric_clean.css`
- `tldw_Server_API/app/core/Slides/style_packs/isometric_dark.css`
- `tldw_Server_API/app/core/Slides/style_packs/dashboard_glass.css`
- `tldw_Server_API/app/core/Slides/style_packs/editorial_print.css`
- `tldw_Server_API/app/core/Slides/style_packs/tactile_soft.css`
- `tldw_Server_API/app/core/Slides/style_packs/retro_pixel.css`
- `tldw_Server_API/app/core/Slides/style_packs/neon_cinematic.css`
- `tldw_Server_API/app/core/Slides/style_packs/brutalist_editorial.css`
- `tldw_Server_API/app/core/Slides/style_packs/heritage_formal.css`
- `tldw_Server_API/app/core/Slides/style_packs/pastel_character.css`
- `tldw_Server_API/tests/Slides/test_visual_style_resolver.py` - resolver, pack, and compact-snapshot regressions.
- `apps/packages/ui/src/components/Option/PresentationStudio/VisualStylePicker.tsx` - grouped, searchable built-in/custom style browser reused by new and detail surfaces.
- `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx` - picker grouping, search, and selection regressions.

**Modify**
- `tldw_Server_API/app/core/Slides/visual_styles.py` - compatibility facade backed by the new catalog/resolver.
- `tldw_Server_API/app/core/Slides/visual_style_generation.py` - replace style-id special cases with profile-driven prompt composition and built-in lookup by snapshot id.
- `tldw_Server_API/app/core/Slides/slides_export.py` - compile safe CSS, add HTML style hooks, render structured visual blocks, and suppress duplicate fallback text.
- `tldw_Server_API/app/api/v1/endpoints/slides.py` - compact built-in style responses, atomic deck-level style application, and summary/detail response shaping.
- `tldw_Server_API/app/api/v1/schemas/slides_schemas.py` - optional catalog metadata fields on visual style responses.
- `tldw_Server_API/tests/Slides/test_visual_styles.py` - built-in catalog count and compatibility-facade regressions.
- `tldw_Server_API/tests/Slides/test_slides_api.py` - create/patch/generate/export behavior when built-in styles are applied.
- `tldw_Server_API/tests/Slides/test_slides_db.py` - compact snapshot/version-payload persistence regressions.
- `tldw_Server_API/tests/Slides/test_slides_generator.py` - prompt-composer regressions.
- `tldw_Server_API/tests/Slides/test_slides_export.py` - sanitized CSS, HTML hooks, and structured visual-block rendering regressions.
- `tldw_Server_API/tests/Slides/test_presentation_rendering.py` - compatibility-only coverage so richer snapshots do not break render-job loading.
- `apps/packages/ui/src/components/Option/PresentationStudio/PresentationStudioPage.tsx` - replace the flat selector with the new picker and keep local theme state in sync for built-in style changes.
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts` - add catalog metadata to visual-style types and snapshot clones.
- `apps/packages/ui/src/services/tldw/domains/presentations.ts` - normalize catalog metadata from list/get responses.
- `apps/packages/ui/src/store/presentation-studio.tsx` - keep optimistic draft state aligned with built-in base themes without mutating slides.
- `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx`
- `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx`
- `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx`
- `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`
- `Docs/API/Slides.md` - document the expanded built-in catalog, compact snapshots, and reveal/pdf styling scope.

**Explicitly Deferred**
- Full visual parity in `tldw_Server_API/app/core/Slides/presentation_rendering.py` is not part of this plan. This phase only guarantees that richer style snapshots and deck-level base themes remain compatible with the current video renderer.

## Stage 1: Build The Catalog And Resolver Foundation

**Goal:** Introduce a structured built-in style catalog and resolver without changing external API behavior yet.

**Success Criteria:** The backend can enumerate 44 built-in styles, preserve the existing 10 built-ins unchanged, and resolve a built-in style id into compact snapshot metadata plus deck-level appearance output.

**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_visual_styles.py tldw_Server_API/tests/Slides/test_visual_style_resolver.py -q`

**Status:** Not Started

### Task 1.1: Lock The Built-In Catalog Contract

**Files:**
- Create: `tldw_Server_API/tests/Slides/test_visual_style_resolver.py`
- Modify: `tldw_Server_API/tests/Slides/test_visual_styles.py`

- [ ] **Step 1: Write the failing tests** using `@test-driven-development`

```python
def test_builtin_visual_style_registry_includes_existing_and_notebooklm_styles():
    styles = list_builtin_visual_styles()
    ids = [style.style_id for style in styles]
    assert len(ids) == 44
    assert "minimal-academic" in ids
    assert "notebooklm-chalkboard" in ids
    assert "notebooklm-brutalist-design" in ids


def test_resolver_returns_compact_snapshot_without_inline_css():
    resolved = resolve_builtin_visual_style("notebooklm-blueprint")
    assert resolved.snapshot["id"] == "notebooklm-blueprint"
    assert resolved.snapshot["resolution"]["style_pack"] == "technical_grid"
    assert "custom_css" not in resolved.snapshot
    assert resolved.theme == "night"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_visual_styles.py tldw_Server_API/tests/Slides/test_visual_style_resolver.py -q`

Expected: FAIL because the resolver module does not exist and the built-in catalog still contains only the original preset tuple.

- [ ] **Step 3: Implement the minimal catalog/resolver skeleton**

```python
@dataclass(frozen=True)
class BuiltinVisualStyleDefinition:
    style_id: str
    name: str
    category: str
    guide_number: int | None
    prompt_profile: str
    style_pack: str
    style_pack_version: int
    base_theme: str
    generation_rules: dict[str, Any]
    artifact_preferences: tuple[str, ...]
    fallback_policy: dict[str, Any]
    appearance_overrides: dict[str, Any]


def resolve_builtin_visual_style(style_id: str) -> ResolvedBuiltinVisualStyle | None:
    definition = get_builtin_visual_style_definition(style_id)
    if definition is None:
        return None
    return build_resolved_builtin_visual_style(definition)
```

Implement the new catalog files, move the 10 existing presets into the catalog unchanged, add the 34 NotebookLM entries from the approved design mapping, and keep `visual_styles.py` as a compatibility facade around the new source of truth.

- [ ] **Step 4: Run the focused backend tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_visual_styles.py tldw_Server_API/tests/Slides/test_visual_style_resolver.py -q`

Expected: PASS with 44 built-ins and compact resolver snapshots.

- [ ] **Step 5: Commit the foundation**

```bash
git add tldw_Server_API/app/core/Slides/visual_style_catalog.py \
  tldw_Server_API/app/core/Slides/visual_style_profiles.py \
  tldw_Server_API/app/core/Slides/visual_style_packs.py \
  tldw_Server_API/app/core/Slides/visual_style_resolver.py \
  tldw_Server_API/app/core/Slides/visual_styles.py \
  tldw_Server_API/tests/Slides/test_visual_styles.py \
  tldw_Server_API/tests/Slides/test_visual_style_resolver.py
git commit -m "feat: add notebooklm visual style catalog foundation"
```

## Stage 2: Apply Built-In Styles Atomically At The API Boundary

**Goal:** Make built-in style selection resolve deck appearance fields atomically and expose richer catalog metadata without bloating list payloads.

**Success Criteria:** Presentation create, generate, patch, and version payload flows apply built-in styles by id/scope, persist compact snapshots, and update `theme`, `settings`, and `custom_css` together when a built-in selection changes.

**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py tldw_Server_API/tests/Slides/test_slides_db.py -k "visual_style or styles_" -q`

**Status:** Not Started

### Task 2.1: Lock The API Contract Before Changing It

**Files:**
- Modify: `tldw_Server_API/tests/Slides/test_slides_api.py`
- Modify: `tldw_Server_API/tests/Slides/test_slides_db.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/slides_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/slides.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_styles_list_exposes_catalog_metadata_without_expanded_css(slides_client):
    payload = slides_client.get("/api/v1/slides/styles").json()
    chalkboard = next(style for style in payload["styles"] if style["id"] == "notebooklm-chalkboard")
    assert chalkboard["category"] == "educational"
    assert chalkboard["guide_number"] == 1
    assert "custom_css" not in chalkboard["appearance_defaults"]


def test_patch_presentation_re_resolves_theme_settings_and_css_for_builtin_style(slides_client):
    create_resp = slides_client.post(
        "/api/v1/slides/presentations",
        json={
            "title": "Deck",
            "theme": "black",
            "slides": [{"order": 0, "layout": "title", "title": "Deck", "content": "", "metadata": {}}],
        },
    )
    presentation_id = create_resp.json()["id"]
    patch_resp = slides_client.patch(
        f"/api/v1/slides/presentations/{presentation_id}",
        json={"visual_style_id": "notebooklm-blueprint", "visual_style_scope": "builtin"},
    )
    payload = patch_resp.json()
    assert payload["theme"] == "night"
    assert payload["settings"]["controls"] is True
    assert "technical_grid" in (payload["visual_style_snapshot"] or {}).get("resolution", {}).get("style_pack", "")
    assert ".tldw-style-pack--technical-grid" in (payload["custom_css"] or "")


def test_visual_style_snapshot_version_payload_stays_compact(tmp_path):
    payload = json.loads(_sample_visual_style_snapshot())
    payload["resolution"] = {
        "base_theme": "night",
        "style_pack": "technical_grid",
        "style_pack_version": 1,
        "token_overrides": {"accent": "#5eead4"},
        "resolved_settings": {"controls": True},
    }
    assert "custom_css" not in payload
```

- [ ] **Step 2: Run the API tests to confirm they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py tldw_Server_API/tests/Slides/test_slides_db.py -k "visual_style or styles_" -q`

Expected: FAIL because the current list responses lack category metadata and patching only updates visual-style identifiers, not the appearance fields.

- [ ] **Step 3: Implement atomic built-in resolution in the API**

```python
class VisualStyleResponse(VisualStyleBase):
    id: str
    scope: str
    category: str | None = None
    guide_number: int | None = None
    tags: list[str] = Field(default_factory=list)
    best_for: list[str] = Field(default_factory=list)
    version: int | None = None


def _resolve_presentation_visual_style_application(
    *,
    visual_style_id: str | None,
    visual_style_scope: str | None,
    db: SlidesDatabase,
) -> ResolvedPresentationStyle | None:
    if visual_style_id is None and visual_style_scope is None:
        return None
    return resolve_presentation_visual_style_application(
        visual_style_id=visual_style_id,
        visual_style_scope=visual_style_scope,
        db=db,
    )
```

Implementation requirements:
- keep built-in list/detail responses compact by returning catalog metadata and summary `appearance_defaults`, not expanded inline CSS blobs
- update `_visual_style_snapshot_from_response()` to persist a compact immutable `resolution` block instead of storing full CSS in snapshots
- update create, generate, `PUT`, and `PATCH` paths so built-in style application atomically writes `theme`, `settings`, `custom_css`, and the compact style snapshot
- preserve user style CRUD behavior and read-only protection for built-ins
- keep clearing a style explicit: clearing `visual_style_id`/`visual_style_scope` must null out style metadata without rewriting slides

- [ ] **Step 4: Re-run the focused API tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py tldw_Server_API/tests/Slides/test_slides_db.py -k "visual_style or styles_" -q`

Expected: PASS with compact snapshots and atomic built-in appearance application.

- [ ] **Step 5: Commit the API boundary work**

```bash
git add tldw_Server_API/app/api/v1/schemas/slides_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Slides/test_slides_db.py
git commit -m "feat: resolve builtin slide styles at the api boundary"
```

## Stage 3: Replace Style-Specific Prompt Hints With Profiles

**Goal:** Make slide generation scale to 34 additional styles without a growing table of style-id special cases.

**Success Criteria:** Built-in styles compose generation prompts from prompt profiles plus style-specific overrides, and the original 10 built-ins preserve their current behavioral intent.

**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_generator.py -k "visual_style or prompt" -q`

**Status:** Not Started

### Task 3.1: Move Prompt Shaping Onto The Catalog

**Files:**
- Modify: `tldw_Server_API/app/core/Slides/visual_style_generation.py`
- Modify: `tldw_Server_API/tests/Slides/test_slides_generator.py`
- Modify: `tldw_Server_API/app/core/Slides/visual_style_profiles.py`
- Modify: `tldw_Server_API/app/core/Slides/visual_style_catalog.py`

- [ ] **Step 1: Write failing prompt-composer tests**

```python
def test_generation_prompt_uses_prompt_profile_for_notebooklm_blueprint():
    prompt = build_visual_style_generation_prompt(
        {"id": "notebooklm-blueprint", "scope": "builtin", "name": "Blueprint"}
    )
    assert "component naming" in prompt
    assert "process_flow" in prompt


def test_generation_prompt_preserves_existing_timeline_behavior():
    prompt = build_visual_style_generation_prompt(
        {"id": "timeline", "scope": "builtin", "name": "Timeline"}
    )
    assert "chronology" in prompt
```

- [ ] **Step 2: Run the prompt tests to confirm they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_generator.py -k "visual_style or prompt" -q`

Expected: FAIL because the current implementation only knows a small `_STYLE_PROMPT_HINTS` table.

- [ ] **Step 3: Implement profile-driven prompt composition**

```python
PROMPT_PROFILES = {
    "technical_precision": (
        "Prefer exact sequencing, component naming, and system relationships.",
        "Avoid decorative narrative filler.",
    ),
    "metric_first": (
        "Foreground numbers, ratios, comparisons, and takeaways.",
        "Prefer stat groups or comparison blocks over decorative prose.",
    ),
}


def build_visual_style_generation_prompt(visual_style_snapshot: dict[str, Any] | None) -> str:
    builtin = resolve_builtin_visual_style_from_snapshot(visual_style_snapshot)
    lines = ["Adapt slide structure and emphasis to the selected visual style."]
    if builtin is not None:
        lines.extend(PROMPT_PROFILES[builtin.definition.prompt_profile])
    return "\n".join(lines)
```

Implementation requirements:
- resolve built-in metadata from `id` + `scope` when the snapshot refers to a built-in style
- compose prompt sections from prompt profile guidance, style description, generation rules, artifact preferences, and fallback instructions
- keep user-style snapshots working without catalog lookup
- retain the existing supported visual block types only: `timeline`, `comparison_matrix`, `process_flow`, `stat_group`

- [ ] **Step 4: Re-run the generator tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_generator.py -k "visual_style or prompt" -q`

Expected: PASS with catalog-backed prompt shaping.

- [ ] **Step 5: Commit prompt-profile integration**

```bash
git add tldw_Server_API/app/core/Slides/visual_style_profiles.py \
  tldw_Server_API/app/core/Slides/visual_style_catalog.py \
  tldw_Server_API/app/core/Slides/visual_style_generation.py \
  tldw_Server_API/tests/Slides/test_slides_generator.py
git commit -m "feat: add profile-driven slide style prompting"
```

## Stage 4: Compile Style Packs And Improve HTML/PDF Exports

**Goal:** Make Reveal bundle and PDF exports visually reflect the new built-in styles while keeping CSS safe and structured visual-block rendering deterministic.

**Success Criteria:** Style packs compile into sanitized CSS, exports stamp stable style hooks, and supported visual blocks render structured HTML without duplicating their text fallback.

**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_export.py tldw_Server_API/tests/Slides/test_presentation_rendering.py -q`

**Status:** Not Started

### Task 4.1: Add The Styled Export Pipeline

**Files:**
- Create: `tldw_Server_API/app/core/Slides/style_packs/*.css`
- Modify: `tldw_Server_API/app/core/Slides/visual_style_packs.py`
- Modify: `tldw_Server_API/app/core/Slides/slides_export.py`
- Modify: `tldw_Server_API/tests/Slides/test_slides_export.py`
- Modify: `tldw_Server_API/tests/Slides/test_presentation_rendering.py`

- [ ] **Step 1: Write the failing export tests**

```python
@pytest.mark.parametrize(
    ("style_id", "expected_pack"),
    [
        ("notebooklm-blueprint", "technical_grid"),
        ("notebooklm-swiss-design", "editorial_print"),
        ("notebooklm-cyberpunk", "neon_cinematic"),
    ],
)
def test_export_bundle_writes_style_hooks_and_sanitized_css(style_id, expected_pack, tmp_path):
    slides = [{"order": 0, "layout": "content", "title": "Deck", "content": "Hello", "metadata": {}}]
    bundle_bytes = export_presentation_bundle(
        title="Deck",
        slides=slides,
        theme="night",
        settings={"controls": True},
        custom_css=".tldw-style-pack--technical-grid { color: #5eead4; }",
        assets_dir=tmp_path / "reveal",
    )
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        html = zf.read("index.html").decode("utf-8")
    assert 'data-visual-style="' + style_id + '"' in html
    assert 'data-style-pack="' + expected_pack + '"' in html


def test_export_bundle_renders_visual_blocks_without_duplicate_fallback(tmp_path):
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Timeline",
            "content": "- 1776: Event - Why it matters",
            "metadata": {
                "visual_blocks": [
                    {
                        "type": "timeline",
                        "items": [{"label": "1776", "title": "Event", "description": "Why it matters"}],
                    }
                ]
            },
        }
    ]
    bundle_bytes = export_presentation_bundle(
        title="Deck",
        slides=slides,
        theme="black",
        settings={"controls": True},
        custom_css=None,
        assets_dir=tmp_path / "reveal",
    )
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        html = zf.read("index.html").decode("utf-8")
    assert 'class="tldw-visual-block tldw-visual-block--timeline"' in html
    assert html.count("Why it matters") == 1
```

- [ ] **Step 2: Run the export tests to confirm they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_export.py tldw_Server_API/tests/Slides/test_presentation_rendering.py -q`

Expected: FAIL because exports do not know about style packs, root style hooks, or structured visual-block HTML.

- [ ] **Step 3: Implement the export pipeline**

```python
def compile_style_pack_css(*, style_id: str, style_pack: str, token_overrides: dict[str, str]) -> str:
    css = load_style_pack(style_pack)
    token_block = render_style_tokens(style_id=style_id, token_overrides=token_overrides)
    return css + "\n" + token_block
```

Implementation requirements:
- load CSS from the new pack files and compile a safe token block per built-in style
- extend `_ALLOWED_CSS_PROPERTIES` only for the properties actually needed by the approved packs
- treat `backdrop-filter` as progressive enhancement only, with a non-glass fallback declared in the same pack
- stamp `data-visual-style` and `data-style-pack` on the exported HTML shell
- render the existing visual block types as structured HTML in Reveal/PDF exports, but keep Markdown on the current text fallback path
- suppress duplicate textual fallback when structured block rendering succeeds
- keep `presentation_rendering.py` compatible with richer snapshots; do not attempt full video-style parity in this stage

- [ ] **Step 4: Re-run the export tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_slides_export.py tldw_Server_API/tests/Slides/test_presentation_rendering.py -q`

Expected: PASS with sanitized CSS, hooks, and non-duplicated visual-block rendering.

- [ ] **Step 5: Commit the export pipeline**

```bash
git add tldw_Server_API/app/core/Slides/style_packs \
  tldw_Server_API/app/core/Slides/visual_style_packs.py \
  tldw_Server_API/app/core/Slides/slides_export.py \
  tldw_Server_API/tests/Slides/test_slides_export.py \
  tldw_Server_API/tests/Slides/test_presentation_rendering.py
git commit -m "feat: add notebooklm slide style export packs"
```

## Stage 5: Redesign Presentation Studio Style Selection

**Goal:** Replace the flat style selector with a grouped searchable picker and keep local deck theme state aligned with built-in style changes.

**Success Criteria:** Presentation Studio can browse 44 built-ins sanely, search/filter by metadata, preserve the custom-style manager for user styles, and avoid stale local `theme` values when a built-in style is selected.

**Tests:** `bunx vitest run src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`

**Status:** Not Started

### Task 5.1: Add Catalog Metadata And Picker Coverage First

**Files:**
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/VisualStylePicker.tsx`
- Create: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/PresentationStudio/PresentationStudioPage.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/tldw/domains/presentations.ts`
- Modify: `apps/packages/ui/src/store/presentation-studio.tsx`
- Modify: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
it("groups builtin styles by category and filters them by search text", async () => {
  render(
    <VisualStylePicker
      value={{ id: null, scope: null }}
      styles={styles}
      onChange={vi.fn()}
    />
  )
  expect(screen.getByText("Educational and Explainer")).toBeInTheDocument()
  await user.type(screen.getByLabelText("Search visual styles"), "blue")
  expect(screen.getByText("Blueprint")).toBeInTheDocument()
  expect(screen.queryByText("Kawaii")).not.toBeInTheDocument()
})

it("updates local theme when a builtin style is selected without mutating slides", async () => {
  const originalSlides = structuredClone(usePresentationStudioStore.getState().slides)
  applySelectedStyle(blueprintStyle)
  expect(store.getState().theme).toBe("night")
  expect(store.getState().slides).toEqual(originalSlides)
})
```

- [ ] **Step 2: Run the focused Vitest suites to confirm they fail**

Run: `bunx vitest run src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`

Expected: FAIL because the picker component and metadata fields do not exist, and the store leaves `theme` stale on built-in style changes.

- [ ] **Step 3: Implement the picker and local sync behavior**

```tsx
type VisualStylePickerProps = {
  value: { id: string | null; scope: string | null }
  styles: VisualStyleRecord[]
  onChange: (style: VisualStyleRecord | null) => void
}
```

Implementation requirements:
- extend `VisualStyleRecord` and visual-style snapshots with `category`, `guide_number`, `tags`, and `best_for`
- create a reusable picker with grouped sections, search, compact metadata chips, and a short detail panel
- use the picker in both the create and detail Presentation Studio surfaces
- keep `VisualStyleManager` as the editor for user styles only
- when a built-in style is selected locally, update `theme` from `appearance_defaults.theme` so autosave no longer re-sends a stale base theme
- do not rewrite slides, notes, or studio metadata on style changes

- [ ] **Step 4: Re-run the focused Vitest suites**

Run: `bunx vitest run src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`

Expected: PASS with grouped search, preserved slide arrays, and local theme synchronization for built-ins.

- [ ] **Step 5: Commit the Presentation Studio changes**

```bash
git add apps/packages/ui/src/components/Option/PresentationStudio/VisualStylePicker.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/PresentationStudioPage.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx \
  apps/packages/ui/src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/services/tldw/domains/presentations.ts \
  apps/packages/ui/src/store/presentation-studio.tsx
git commit -m "feat: add notebooklm visual style picker"
```

## Stage 6: Document, Verify, And Close

**Goal:** Update the public Slides docs and run the full targeted verification plus security pass for the touched production files.

**Success Criteria:** Docs describe the new catalog behavior accurately, targeted backend/frontend suites pass, and Bandit reports zero new findings in the touched backend scope.

**Tests:** `@verification-before-completion` on the targeted backend/frontend commands plus Bandit.

**Status:** Not Started

### Task 6.1: Finish The Public Contract And Verification Pass

**Files:**
- Modify: `Docs/API/Slides.md`
- Modify: all production files touched in Stages 1-5 as needed for final cleanup

- [ ] **Step 1: Update the Slides API docs**

Document:
- built-in visual styles remain additive and backward compatible
- list responses are catalog-oriented and snapshots are compact
- styled exports currently target Reveal bundle and PDF paths
- video render jobs remain compatibility-only with respect to the richer catalog in this phase

- [ ] **Step 2: Run the targeted backend verification**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_visual_styles.py tldw_Server_API/tests/Slides/test_visual_style_resolver.py tldw_Server_API/tests/Slides/test_slides_api.py tldw_Server_API/tests/Slides/test_slides_generator.py tldw_Server_API/tests/Slides/test_slides_export.py tldw_Server_API/tests/Slides/test_presentation_rendering.py -q`

Expected: PASS with the new catalog, API, generation, and export coverage all green.

- [ ] **Step 3: Run the targeted frontend verification**

Run: `bunx vitest run src/components/Option/PresentationStudio/__tests__/VisualStylePicker.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioCreatePayload.test.tsx src/components/Option/PresentationStudio/__tests__/PresentationStudioBootstrap.test.tsx src/components/Option/PresentationStudio/__tests__/presentation-studio.store.test.tsx`

Expected: PASS with grouped-picker and store-sync coverage green.

- [ ] **Step 4: Run Bandit on the touched backend production files**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Slides/visual_style_catalog.py tldw_Server_API/app/core/Slides/visual_style_profiles.py tldw_Server_API/app/core/Slides/visual_style_packs.py tldw_Server_API/app/core/Slides/visual_style_resolver.py tldw_Server_API/app/core/Slides/visual_style_generation.py tldw_Server_API/app/core/Slides/slides_export.py tldw_Server_API/app/api/v1/endpoints/slides.py -f json -o /tmp/bandit_notebooklm_style_catalog.json`

Expected: JSON report written to `/tmp/bandit_notebooklm_style_catalog.json` with zero new findings in the touched scope.

- [ ] **Step 5: Commit the verified implementation**

```bash
git add Docs/API/Slides.md \
  tldw_Server_API/app/core/Slides/visual_style_catalog.py \
  tldw_Server_API/app/core/Slides/visual_style_profiles.py \
  tldw_Server_API/app/core/Slides/visual_style_packs.py \
  tldw_Server_API/app/core/Slides/visual_style_resolver.py \
  tldw_Server_API/app/core/Slides/visual_styles.py \
  tldw_Server_API/app/core/Slides/visual_style_generation.py \
  tldw_Server_API/app/core/Slides/slides_export.py \
  tldw_Server_API/app/core/Slides/style_packs \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/app/api/v1/schemas/slides_schemas.py \
  tldw_Server_API/tests/Slides/test_visual_styles.py \
  tldw_Server_API/tests/Slides/test_visual_style_resolver.py \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Slides/test_slides_db.py \
  tldw_Server_API/tests/Slides/test_slides_generator.py \
  tldw_Server_API/tests/Slides/test_slides_export.py \
  tldw_Server_API/tests/Slides/test_presentation_rendering.py \
  apps/packages/ui/src/components/Option/PresentationStudio \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/services/tldw/domains/presentations.ts \
  apps/packages/ui/src/store/presentation-studio.tsx
git commit -m "feat: add notebooklm presentation style catalog"
```

## Execution Notes

- Treat the design doc at `Docs/Design/2026-03-29-notebooklm-presentation-style-catalog-design.md` as the source of truth for the 34-style mapping and the reviewed constraints around compact snapshots, atomic style application, and CSS fallbacks.
- Do not expand the top-level `theme` allowlist beyond the existing Reveal themes.
- Do not add new visual-block primitives in this implementation. Only render the four existing types more richly in HTML/PDF.
- Do not silently restyle the current video renderer. If a compatibility test fails, fix the compatibility bug; otherwise leave render-job styling parity for a separate design/plan.
