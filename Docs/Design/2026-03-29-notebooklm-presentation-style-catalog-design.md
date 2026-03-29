# NotebookLM Presentation Style Catalog Design

**Date:** 2026-03-29

**Status:** Drafted from codebase review and user-approved design discussion

## Goal

Add support for all 34 aesthetics described in `Visual Style Guide for NotebookLM Presentations.pdf` as first-class built-in presentation styles, while preserving the existing 10 built-in slide visual styles and keeping exports stable across Reveal bundle, Markdown, PDF, and Presentation Studio flows.

## Scope

This design covers:

- additive support for 34 new built-in NotebookLM-inspired presentation styles
- style-aware slide generation behavior
- styled exports for Reveal bundle and PDF
- Presentation Studio style selection UX
- compatibility with the current persisted presentation snapshot model

This design does not cover:

- replacing the existing 10 built-in style IDs
- fully generative art or image synthesis for painterly / anime / claymation looks
- shared user-custom visual styles beyond the current user-scoped model
- introducing a new presentation renderer outside Reveal / current HTML export paths

## Current State Review

### 1. `theme` is not the right extension point

The current presentation `theme` field is a narrow Reveal.js theme selector validated in:

- `tldw_Server_API/app/api/v1/endpoints/slides.py`
- `tldw_Server_API/app/core/Slides/slides_export.py`

Allowed values are limited to the bundled Reveal theme set:

- `black`
- `white`
- `league`
- `beige`
- `sky`
- `night`
- `serif`
- `simple`
- `solarized`
- `blood`
- `moon`
- `dracula`

Adding 34 NotebookLM aesthetics as new top-level `theme` values would conflict with current validation, asset lookup, and export assumptions.

### 2. The repo already has the correct abstraction: `visual_style`

The current slide stack already supports presentation-level `visual_style` metadata:

- built-in presets in `tldw_Server_API/app/core/Slides/visual_styles.py`
- prompt shaping in `tldw_Server_API/app/core/Slides/visual_style_generation.py`
- persistence and snapshotting in `tldw_Server_API/app/api/v1/endpoints/slides.py`
- frontend selection and storage in `apps/packages/ui/src/components/Option/PresentationStudio/PresentationStudioPage.tsx`
- custom user style management in `apps/packages/ui/src/components/Option/PresentationStudio/VisualStyleManager.tsx`

This existing layer is the correct integration point for the PDF aesthetics.

### 3. Export styling is possible, but constrained

Exports currently support:

- a Reveal theme CSS file
- a single optional `custom_css` payload persisted on the presentation
- sanitized HTML content and images

Important constraints from `tldw_Server_API/app/core/Slides/slides_export.py`:

- `@import` is blocked
- `url(...)` is blocked
- CSS is sanitized against an allowlist
- export HTML is simple and does not currently render rich custom visual-block HTML

This means NotebookLM styles must rely on:

- safe inline CSS only
- system or bundled fonts only
- gradients, borders, shadows, spacing, typography, and color treatment
- optional richer rendering for already-supported `visual_blocks`, if explicitly added

### 4. Visual blocks already exist, but only fall back to text

The current generation pipeline already supports:

- `timeline`
- `comparison_matrix`
- `process_flow`
- `stat_group`

These are normalized in `tldw_Server_API/app/core/Slides/visual_style_generation.py` and text fallbacks are compiled into `slide.content`. Export flows currently preserve the fallback text rather than rendering structured HTML widgets.

That is enough for option 2 if enhanced export rendering stays limited to these existing block types.

## Design Decisions

1. Keep the current 10 built-in visual styles unchanged for backward compatibility.
2. Add the 34 NotebookLM PDF aesthetics as additional built-in `visual_style` entries.
3. Implement the new styles as built-in catalog entries, not templates and not new top-level `theme` values.
4. Resolve each built-in style to:
   - a supported Reveal base theme
   - optional Reveal settings defaults
   - resolved safe `custom_css`
   - prompt-profile guidance
   - artifact preferences and fallback policy
5. Persist fully resolved style snapshots on the presentation so exports remain stable even if built-in style definitions later evolve.
6. Support styled exports through reusable CSS style packs and token overrides.
7. Do not promise image-generation fidelity for painterly or character-heavy styles in v1 of this effort.

## Recommended Architecture

## Catalog Layer

Replace the current flat built-in preset declaration with a structured built-in catalog.

Each built-in entry should expose the existing public payload:

- `id`
- `name`
- `description`
- `generation_rules`
- `artifact_preferences`
- `appearance_defaults`
- `fallback_policy`

Each built-in entry should also carry internal metadata used by the resolver and UI:

- `category`
- `guide_number`
- `sort_order`
- `prompt_profile`
- `style_pack`
- `style_pack_version`
- `tags`
- `best_for`
- `preview_tokens`

Suggested internal model:

```python
@dataclass(frozen=True)
class BuiltinVisualStyleDefinition:
    style_id: str
    name: str
    description: str
    category: str
    guide_number: int | None
    sort_order: int
    version: int
    best_for: tuple[str, ...]
    tags: tuple[str, ...]
    prompt_profile: str
    style_pack: str
    style_pack_version: int
    base_theme: str
    generation_rules: dict[str, Any]
    artifact_preferences: tuple[str, ...]
    fallback_policy: dict[str, Any]
    appearance_overrides: dict[str, Any]
```

The public API should continue returning `VisualStyleResponse`, but the response should be derived from this richer catalog definition.

## Style Pack Layer

Introduce reusable style packs that can be compiled into safe `custom_css`.

Style packs represent families of export styling rather than one-off complete styles.

Recommended initial style packs:

- `hand_drawn_surface`
- `technical_grid`
- `isometric_clean`
- `isometric_dark`
- `dashboard_glass`
- `editorial_print`
- `tactile_soft`
- `retro_pixel`
- `neon_cinematic`
- `brutalist_editorial`
- `heritage_formal`
- `pastel_character`

Each built-in style should reference:

- one style pack
- a supported base Reveal theme
- small token overrides for colors, spacing, borders, shadows, typography tone, and slide chrome

This avoids maintaining 34 unrelated CSS blobs.

## Prompt Profile Layer

Replace the current style-ID-special-case prompt hints with reusable prompt profiles.

Recommended prompt profiles:

- `instructional_hand_drawn`
- `fine_art_human`
- `tactile_playful`
- `technical_precision`
- `metric_first`
- `narrative_journey`
- `corporate_strategy`
- `design_editorial`
- `playful_approachable`
- `retro_synthetic`
- `high_energy_marketing`

Prompt profiles should define:

- slide pacing
- title treatment
- density target
- bullet vs narrative bias
- artifact bias
- preferred framing language
- what to avoid

Each individual style can add minor prompt overrides on top of the profile.

## Resolver Layer

Add a resolver that turns a built-in catalog definition into the already-supported persisted output fields:

- `theme`
- `settings`
- `custom_css`
- `visual_style_snapshot`

Resolution order:

1. load built-in style definition
2. resolve base theme
3. load style-pack CSS
4. apply style token overrides
5. sanitize / validate generated CSS
6. emit resolved `appearance_defaults`
7. persist the resolved snapshot and presentation-level appearance fields

This keeps exports deterministic and decouples catalog authoring from persisted deck state.

## Proposed File Structure

Recommended backend files:

- `tldw_Server_API/app/core/Slides/visual_style_catalog.py`
- `tldw_Server_API/app/core/Slides/visual_style_profiles.py`
- `tldw_Server_API/app/core/Slides/visual_style_packs.py`
- `tldw_Server_API/app/core/Slides/visual_style_resolver.py`

Keep `tldw_Server_API/app/core/Slides/visual_styles.py` as the compatibility facade that exports:

- `list_builtin_visual_styles()`
- `get_builtin_visual_style()`

Recommended CSS asset files:

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

## Catalog Mapping For The 34 PDF Styles

The table below maps each PDF aesthetic into the recommended built-in implementation model.

| # | PDF Style | Suggested ID | Category | Prompt Profile | Style Pack | Base Theme | Artifact Bias | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Chalkboard | `notebooklm-chalkboard` | educational | `instructional_hand_drawn` | `hand_drawn_surface` | `black` | `process_flow`, `stat_group` | dark slate, chalk contrast |
| 2 | Whiteboard | `notebooklm-whiteboard` | educational | `instructional_hand_drawn` | `hand_drawn_surface` | `white` | `process_flow`, `comparison_matrix` | bright board, marker accents |
| 3 | Sketch Noting | `notebooklm-sketch-noting` | educational | `instructional_hand_drawn` | `hand_drawn_surface` | `white` | `process_flow`, `comparison_matrix` | workshop synthesis feel |
| 4 | Graphite and Charcoal Realism | `notebooklm-graphite-charcoal` | educational | `fine_art_human` | `editorial_print` | `serif` | `timeline` | monochrome, somber, restrained |
| 5 | Claymation | `notebooklm-claymation` | educational | `tactile_playful` | `tactile_soft` | `beige` | `process_flow`, `stat_group` | tactile look, not literal rendered clay |
| 6 | Exploded View Diagram | `notebooklm-exploded-view` | technical | `technical_precision` | `technical_grid` | `simple` | `process_flow`, `comparison_matrix` | orthographic, assembly framing |
| 7 | Blueprint | `notebooklm-blueprint` | technical | `technical_precision` | `technical_grid` | `night` | `process_flow`, `timeline` | cyan grid, white technical lines |
| 8 | Isometric 3D Illustration | `notebooklm-isometric-3d` | technical | `technical_precision` | `isometric_clean` | `white` | `process_flow`, `stat_group` | clean corporate spatial look |
| 9 | Minimalist 2D Data-Viz | `notebooklm-minimalist-data-viz` | technical | `metric_first` | `editorial_print` | `white` | `stat_group`, `comparison_matrix` | flat quantitative clarity |
| 10 | Dark-Mode SaaS Isometric | `notebooklm-dark-saas-isometric` | technical | `technical_precision` | `isometric_dark` | `night` | `process_flow`, `stat_group` | dark modules, neon edges |
| 11 | Professional Futuristic | `notebooklm-professional-futuristic` | technical | `corporate_strategy` | `dashboard_glass` | `moon` | `stat_group`, `comparison_matrix` | premium corporate future-tech |
| 12 | Neumorphic | `notebooklm-neumorphic` | technical | `corporate_strategy` | `tactile_soft` | `white` | `stat_group` | low-contrast tactile UI chrome |
| 13 | High-Contrast Monospace | `notebooklm-high-contrast-monospace` | technical | `technical_precision` | `neon_cinematic` | `black` | `stat_group`, `comparison_matrix` | terminal-style emphasis |
| 14 | Conceptual Journey Map | `notebooklm-journey-map` | narrative | `narrative_journey` | `editorial_print` | `beige` | `timeline`, `process_flow` | roadmap metaphor, left-to-right arc |
| 15 | Strategic Infographic | `notebooklm-strategic-infographic` | narrative | `corporate_strategy` | `editorial_print` | `white` | `stat_group`, `comparison_matrix` | problem-solution-impact |
| 16 | Executive Dashboard | `notebooklm-executive-dashboard` | narrative | `metric_first` | `dashboard_glass` | `night` | `stat_group`, `comparison_matrix` | dense KPI treatment |
| 17 | Watercolour | `notebooklm-watercolour` | narrative | `narrative_journey` | `editorial_print` | `beige` | `timeline` | soft atmospheric palette, not painted imagery |
| 18 | Heritage | `notebooklm-heritage` | narrative | `corporate_strategy` | `heritage_formal` | `serif` | `timeline`, `comparison_matrix` | formal institutional tone |
| 19 | Swiss Design | `notebooklm-swiss-design` | narrative | `design_editorial` | `editorial_print` | `white` | `comparison_matrix`, `stat_group` | strict grid and whitespace |
| 20 | Glass-morphic UI | `notebooklm-glassmorphic-ui` | narrative | `corporate_strategy` | `dashboard_glass` | `moon` | `stat_group` | frosted panels within sanitizer limits |
| 21 | Corporate Memphis | `notebooklm-corporate-memphis` | narrative | `playful_approachable` | `pastel_character` | `sky` | `process_flow`, `stat_group` | approachable startup tone |
| 22 | Papercraft | `notebooklm-papercraft` | playful | `tactile_playful` | `tactile_soft` | `beige` | `process_flow` | layered shadows and paper feel |
| 23 | Tactile 3D | `notebooklm-tactile-3d` | playful | `tactile_playful` | `tactile_soft` | `white` | `stat_group` | soft inflated UI style |
| 24 | Miniature World | `notebooklm-miniature-world` | playful | `tactile_playful` | `isometric_clean` | `sky` | `process_flow`, `timeline` | toy-like overview framing |
| 25 | Kawaii | `notebooklm-kawaii` | playful | `playful_approachable` | `pastel_character` | `sky` | `process_flow`, `stat_group` | pastel rounded friendliness |
| 26 | Pop Art | `notebooklm-pop-art` | nostalgic | `high_energy_marketing` | `editorial_print` | `white` | `stat_group` | thick contrast, halftone-inspired styling |
| 27 | Risograph Print | `notebooklm-risograph-print` | nostalgic | `design_editorial` | `editorial_print` | `beige` | `comparison_matrix`, `stat_group` | grain, spot-color editorial look |
| 28 | Retro 90s Gaming | `notebooklm-retro-90s-gaming` | nostalgic | `retro_synthetic` | `retro_pixel` | `black` | `process_flow`, `stat_group` | chunky UI and low-poly flavor |
| 29 | Oregon Trail | `notebooklm-oregon-trail` | nostalgic | `retro_synthetic` | `retro_pixel` | `simple` | `timeline`, `process_flow` | 8-bit frontier journey framing |
| 30 | Cyberpunk | `notebooklm-cyberpunk` | nostalgic | `high_energy_marketing` | `neon_cinematic` | `blood` | `stat_group`, `comparison_matrix` | neon, gritty, atmospheric |
| 31 | Anime Battle | `notebooklm-anime-battle` | nostalgic | `high_energy_marketing` | `neon_cinematic` | `moon` | `process_flow`, `stat_group` | high-energy launch / competition |
| 32 | Anime | `notebooklm-anime` | nostalgic | `playful_approachable` | `pastel_character` | `sky` | `timeline`, `process_flow` | bright cinematic narrative tone |
| 33 | Retro Print | `notebooklm-retro-print` | nostalgic | `design_editorial` | `editorial_print` | `beige` | `timeline`, `comparison_matrix` | archive / newspaper tone |
| 34 | Brutalist Design | `notebooklm-brutalist-design` | nostalgic | `design_editorial` | `brutalist_editorial` | `simple` | `comparison_matrix`, `stat_group` | harsh contrast and oversized type |

## Generation Design

## Prompt Composition

The current prompt shaping should be refactored from style-ID-specific hints to profile-driven composition.

Each generated prompt should include:

- active visual style name
- short style description
- prompt profile guidance
- generation rules JSON
- artifact preference list
- fallback requirement
- style-specific "avoid" notes where appropriate

Recommended profile guidance examples:

- `instructional_hand_drawn`
  - prioritize pedagogical clarity
  - use approachable, explainer language
  - keep layout loose but readable
- `technical_precision`
  - prefer exact sequencing, component naming, system relationships
  - avoid decorative narrative filler
- `metric_first`
  - foreground numbers, ratios, comparisons, and takeaways
  - prefer stat groups and comparison blocks
- `design_editorial`
  - use concise, high-signal titles and controlled whitespace
  - avoid bullet bloat
- `retro_synthetic`
  - use stylized framing language and strong section labels
  - keep content readable even when tone is themed

## Artifact Strategy

Keep the existing supported artifact types:

- `timeline`
- `comparison_matrix`
- `process_flow`
- `stat_group`

Map styles to those artifacts rather than introducing new artifact primitives in this effort.

Examples:

- journey-oriented styles bias to `timeline`
- technical architecture styles bias to `process_flow`
- dashboard and data-viz styles bias to `stat_group`
- comparative and policy styles bias to `comparison_matrix`

Every generated artifact must still compile into meaningful plain text fallback.

## Export Design

## Resolved CSS Model

Built-in NotebookLM styles should resolve into:

- supported base Reveal theme
- optional sanitized settings overrides
- safe resolved `custom_css`

The `custom_css` should be produced by concatenating:

1. style-pack base CSS
2. per-style token block
3. optional small style-local rule block

No external fonts, images, or imported stylesheets should be used.

## HTML Hooks

Enhance export HTML generation to stamp stable style hooks on the document so CSS remains namespaced and testable.

Recommended hooks:

- root `body` or `.reveal` attribute: `data-visual-style="notebooklm-blueprint"`
- pack attribute: `data-style-pack="technical_grid"`

This supports cleaner selectors and future snapshot testing.

## Rich Rendering For Existing Visual Blocks

To improve option 2 fidelity without adding new primitives, extend the Reveal export renderer to render the existing visual block types as HTML when present:

- `timeline`
- `comparison_matrix`
- `process_flow`
- `stat_group`

Rules:

- render structured HTML blocks in export bundle / PDF HTML
- keep `slide.content` textual fallback for Markdown and resilience
- if structured block rendering fails, fall back to current content rendering

This is a renderer enhancement, not a new artifact system.

## CSS Sanitization Adjustments

The current CSS allowlist is likely too restrictive for some target looks, especially:

- blueprint grids
- glassmorphism-like panel styling
- dashboard widgets
- editorial / print accents

Review and carefully extend `_ALLOWED_CSS_PROPERTIES` only as needed.

Possible additions to evaluate:

- `background-image`
- `background-size`
- `background-position`
- `background-repeat`
- `border-collapse`
- `border-spacing`
- `gap`
- `column-gap`
- `row-gap`
- `backdrop-filter`

Any expansion should be conservative and covered by export tests.

## API Design

Extend `VisualStyleResponse` with optional fields for built-in browsing and display:

- `category`
- `guide_number`
- `tags`
- `best_for`

For user-created styles these fields remain `null` or empty.

The persisted presentation model can remain unchanged, but the built-in snapshot payload should optionally include:

- `category`
- `guide_number`
- `tags`

This preserves useful display metadata when a built-in catalog entry later evolves.

## Frontend Design

The current dropdown in `PresentationStudioPage.tsx` will not scale well to 44 built-in styles.

Replace it with a style picker that supports:

- grouping by category
- search
- compact metadata chips
- preview description
- "best for" summary

Suggested group order:

1. Existing built-ins
2. Educational and Explainer
3. Technical and Engineering
4. Narrative and Strategic
5. Playful and Tactile
6. Nostalgic and Artistic
7. Custom user styles

The picker should keep the current behavior:

- changing the deck-level visual style updates only future generation defaults
- existing slides are not rewritten
- built-in styles remain read-only
- user styles remain editable via the existing custom-style manager

## Backward Compatibility

- keep all existing built-in style IDs and semantics
- add the 34 NotebookLM styles as additive built-ins only
- preserve persisted snapshots on existing presentations
- do not change presentation appearance unless a user explicitly selects a new style

## Risks And Limitations

### High-confidence limitations

- Styles like Watercolour, Claymation, Anime, Anime Battle, and Miniature World can only be approximated as presentation skin plus generation behavior, not literal rendered artwork.
- No external font loading means some typography-heavy styles will be approximations.
- Sanitized CSS may limit fidelity for glassmorphism and some high-polish futuristic looks.

### Maintainability risks

- 34 additional styles can become noisy without a structured catalog and style-pack reuse.
- Frontend usability will degrade quickly if the selector remains a plain `<select>`.
- Export CSS drift is likely unless a golden visual subset is snapshot-tested.

## Testing Strategy

Add tests at four levels.

### Backend catalog tests

- built-in style count includes original 10 plus new 34
- all IDs are unique
- category ordering is stable
- resolved style snapshots include expected metadata

### Generation tests

- prompt composer injects correct prompt profile guidance
- artifact preferences are style-appropriate
- existing styles remain behaviorally unchanged

### Export tests

- resolved CSS sanitizes successfully
- no blocked constructs leak into exports
- style hooks are present in generated HTML
- visual block HTML rendering falls back safely

### Frontend tests

- grouped picker renders all catalog sections
- search narrows results
- selecting a built-in style persists the correct metadata
- changing style does not mutate existing slides

Recommended golden subset for regression coverage:

- Chalkboard
- Blueprint
- Swiss Design
- Executive Dashboard
- Glass-morphic UI
- Brutalist Design
- Risograph Print
- Cyberpunk

## Recommended Next Step

After spec approval, write an implementation plan that breaks the work into:

1. catalog and resolver refactor
2. prompt-profile integration
3. style-pack CSS pipeline
4. export renderer enhancements for existing visual blocks
5. Presentation Studio picker redesign
6. tests and verification
