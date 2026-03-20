# Slides Visual Style Presets Design

**Date:** 2026-03-17

**Status:** Approved for planning

**Goal:** Add a first-class `Choose Visual Style` feature for slides and Presentation Studio that supports built-in and per-user custom presets, shapes generated slide structure and emphasis, remains visible across create and edit surfaces, and preserves stable exports by requiring renderer-safe fallbacks.

## Problem

The current slides stack already supports presentation-level `theme`, `template_id`, `settings`, `custom_css`, and `studio_data`, but it does not support a reusable pedagogical preset layer.

That gap matters because the user goal is not a cosmetic theme picker. The feature is intended to change how the system structures and emphasizes information for different learning and presentation modes, including:

- infographic style
- minimal academic style
- exam-focused bullet style
- diagram or map-based style
- timeline style
- data visualization style
- storytelling style
- high-contrast revision style

For students and exam-oriented learners, the same source material should produce meaningfully different decks depending on whether recall, conceptual flow, comparison, chronology, or visual reinforcement is the priority.

## User-Approved Decisions

1. Visual style affects both appearance and content structure, not just visual skin.
2. Changing style does not rewrite existing slides.
3. The style selector should be visible across generation flows, Presentation Studio, and existing presentation edit surfaces.
4. V1 supports built-in styles and user-created custom styles.
5. Custom styles are per-user in v1, with sharing deferred.
6. Styles may request structured visual artifacts where possible, but must fall back gracefully when specialized rendering is unavailable.

## Current State

### Existing Capabilities

- Slide presentations already persist `theme`, `marp_theme`, `template_id`, `settings`, `studio_data`, `slides`, and `custom_css`.
- Slide generation endpoints exist for prompt, chat, media, notes, and RAG sources.
- Presentation Studio already persists presentation-wide metadata and per-slide studio metadata.
- Exports for Reveal.js, Markdown, PDF, and video rendering operate on ordinary slide content plus selected images.

### Existing Gaps

- There is no `visual_style` field or resource in the API or DB.
- Templates are static file-backed definitions, not per-user editable resources.
- Slide generation uses a single generic prompt contract and is biased toward standard bullet decks.
- Export and rendering paths do not understand arbitrary structured visual metadata.
- Presentation Studio creates new blank projects immediately with hardcoded defaults before the user can choose a deck-level strategy.

## Goals

- Add a reusable visual style layer distinct from templates.
- Support at least 8 to 10 meaningful built-in presets.
- Allow user-defined custom presets per user.
- Keep style selection presentation-wide and visible across create and edit surfaces.
- Apply style changes to future generation only.
- Preserve stable rendering and version history even when style definitions later change.
- Support a narrow set of structured artifact modes in v1 without requiring a new rendering engine.

## Non-Goals

- Rewriting existing slides automatically when style changes.
- Replacing the current template system.
- Shipping a full custom chart, map, or infographic rendering engine in v1.
- Supporting shared or workspace-global custom styles in v1.
- Promising wholly new theme infrastructure beyond the current Reveal-based appearance pipeline.

## Recommended Architecture

Introduce a first-class `visual_style` resource separate from `template_id`.

### Separation of Concerns

- `template_id` remains a starter scaffold concept: default slides, default theme, and other bootstrapping defaults.
- `visual_style` becomes the reusable generation and teaching strategy concept: how content is organized, emphasized, and visually framed.

This separation prevents overloading the current template system and allows custom user styles without turning static file-backed templates into mutable user content.

## Visual Style Resource

Each style should contain:

- `id`
- `name`
- `scope`: `builtin` or `user`
- `description`
- `learning_goal`
- `generation_rules`
- `artifact_preferences`
- `appearance_defaults`
- `fallback_policy`
- `version`
- `created_by` for user styles
- timestamps for user styles

### `generation_rules`

These rules define how source material should be converted into slides. Example fields:

- `density_mode`: sparse, balanced, dense
- `bullet_bias`
- `narrative_bias`
- `comparison_bias`
- `chronology_bias`
- `exam_focus`
- `revision_focus`
- `speaker_notes_verbosity`
- `sectioning_pattern`

### `artifact_preferences`

Ordered preferences for structured visual treatment. V1 should support:

- `timeline`
- `comparison_matrix`
- `process_flow`
- `stat_group`

V1 may also store advisory-only preferences for:

- `chart_spec`
- `map_spec`

### `appearance_defaults`

Appearance defaults resolve into the already-supported presentation fields:

- `theme`
- `marp_theme`
- `settings`
- sanitized `custom_css`

These must remain compatible with the current allowed Reveal theme set and current CSS sanitization path.

## Presentation Persistence Model

The presentation must store both a style reference and a style snapshot.

### New Presentation Fields

- `visual_style_id`
- `visual_style_scope`
- `visual_style_name`
- `visual_style_version`
- `visual_style_snapshot`

### Existing Presentation Fields Retained

- `theme`
- `marp_theme`
- `settings`
- `custom_css`
- `studio_data`

### Why Snapshotting Is Required

If a user custom style is edited or deleted later, existing presentations must still:

- render the same way
- preserve history in version snapshots
- remain exportable without dereferencing a missing style record

The style record remains the reusable source for future generation, but the presentation keeps a resolved snapshot for stability.

## Built-In Style Set

V1 should ship with 10 built-in presets:

1. Infographic
2. Minimal Academic
3. Exam-Focused Bullet
4. Diagram or Map-Based
5. Timeline
6. Data Visualization
7. Storytelling
8. High-Contrast Revision
9. Comparative Matrix
10. Policy or Case Brief

Each built-in style must define:

- a concise user-facing description
- explicit generation rules
- appearance defaults
- structured artifact preferences
- fallback behavior

## Generation Contract

Style-aware generation should follow this sequence:

1. Resolve the selected style.
2. Merge style appearance defaults into the request unless explicitly overridden.
3. Build a style-specific generation prompt contract.
4. Generate ordinary slides using the current slide schema.
5. Optionally attach `metadata.visual_blocks` for supported structured artifacts.
6. Persist the presentation with both resolved presentation fields and style snapshot metadata.

### Prompting Requirement

Do not implement styles as a single generic prompt plus a style label.

Instead, styles must use prompt builders or prompt modules that change:

- slide pacing
- title treatment
- density
- bullet versus narrative balance
- chronology or comparison emphasis
- speaker-notes expectations
- artifact selection bias

This is necessary to create meaningful output differences between presets.

## Structured Visual Artifacts

V1 supports structured visual blocks only when they remain renderer-safe.

### Supported V1 Artifact Blocks

- `timeline`
- `comparison_matrix`
- `process_flow`
- `stat_group`

### Advisory-Only V1 Blocks

- `chart_spec`
- `map_spec`

### Critical Fallback Rule

Every generated structured block must also produce ordinary slide text in `content`.

That means:

- a timeline must still render as a readable chronological slide in exports
- a comparison matrix must still render as readable comparison content
- a process flow must still render as readable ordered steps
- a stat group must still render as readable key-value highlights

Structured metadata is additive. It must never be the only representation of the slide’s meaning.

## UX Design

The visual style selector is a presentation-wide strategy control, not a per-slide control.

### Generation Surfaces

Add `Choose Visual Style` beside existing deck-generation controls.

Each style option should show:

- name
- one-sentence promise
- indicators for artifact preferences such as timeline, comparison, flow, or stat-first

Built-in and custom styles should appear in one selector, clearly labeled by source.

### Presentation Studio

Display the selected style at the deck level, near title and other presentation metadata.

The UI copy must be explicit:

`Applies to future generated slides. Existing slides are unchanged.`

### Existing Decks

Users can switch style on existing decks, but that only changes:

- the saved preferred generation strategy
- default style used by future “generate” actions

It does not rewrite current slides and it does not automatically replace current theme or CSS.

### New Blank Projects

`/presentation-studio/new` should no longer create a hardcoded default deck without style choice.

Recommended v1 behavior:

- show a lightweight pre-create step with title and style
- preselect a default built-in style
- create the deck with the resolved style snapshot and appearance defaults

This keeps style available everywhere without forcing a later patch round-trip immediately after creation.

## API Surface

Add a new API family under `/api/v1/slides/styles`.

### Read APIs

- `GET /api/v1/slides/styles`
- `GET /api/v1/slides/styles/{style_id}`

These return built-in styles plus current-user custom styles.

### Write APIs for User Styles

- `POST /api/v1/slides/styles`
- `PATCH /api/v1/slides/styles/{style_id}`
- `DELETE /api/v1/slides/styles/{style_id}`

Built-in styles are read-only.

### Presentation APIs

Add optional style fields to:

- presentation create
- presentation update
- presentation patch
- generation request models

The presentation response should include both style reference fields and resolved snapshot metadata.

## Storage Strategy

### Styles

Store built-in styles in code or bundled JSON and treat them as immutable versioned assets.

Store user styles in a per-user DB-backed table keyed by user identity.

### Presentations

Add new nullable columns for presentation-level style reference and snapshot fields.

Existing presentations without style data remain valid and should resolve as:

- `visual_style = null`
- or a server default style at UI display time, without mutating stored content until explicitly saved

## Backward Compatibility

Backward compatibility requirements:

- presentations without style metadata must continue to load normally
- existing exports must keep functioning without requiring style dereferencing
- old presentations remain editable in Presentation Studio
- generation endpoints continue to work when no style is selected

The default behavior when no style is set should be equivalent to the current generic slide-generation mode.

## Error Handling

### Invalid or Missing Custom Style

If a requested custom style does not exist, return a clear not-found error.

If a presentation references a deleted style, continue using:

- persisted snapshot metadata
- persisted resolved appearance fields

The deck remains valid even if the live style record is gone.

### Artifact Generation Failure

If a structured artifact block fails validation or cannot be rendered:

- keep the textual slide content
- drop or downgrade the artifact metadata
- return warnings where appropriate

Failure to produce a specialized artifact must not fail the whole deck unless the request explicitly demands strict artifact success in a future phase.

## Testing Strategy

### Unit

- style schema validation
- style default merging
- style snapshot persistence rules
- prompt-builder behavior per style family
- fallback compilation for supported artifact blocks

### Integration

- create/get/update/patch presentation flows with style fields
- generation flows from prompt/chat/media/notes/RAG with selected style
- built-in and custom style listing behavior
- deleted custom-style compatibility for existing decks

### UI

- style selector on generation surfaces
- style selector on Presentation Studio pre-create flow
- existing deck style visibility and edit behavior
- explicit non-rewrite copy and behavior

### Regression

- existing presentations without style fields still load and save
- Reveal, Markdown, PDF, and video paths still function from resolved slide content
- templates continue behaving as templates rather than style resources

## Rollout Strategy

Phase 1:

- built-in styles
- per-user custom styles
- presentation-level style persistence and snapshotting
- style-aware generation prompts
- renderer-safe artifact metadata with required textual fallback

Phase 2:

- richer Studio editing for visual blocks
- optional “apply appearance defaults now” action for existing decks
- shared or workspace-level style sharing
- stronger chart and map rendering support

## Recommended Implementation Direction

The implementation plan should prioritize:

1. backend style resource and presentation persistence
2. style-aware generation contract and fallback compilation
3. Presentation Studio create flow and deck-level style UX
4. custom-style CRUD and tests

This ordering keeps the feature coherent from API to UI while avoiding a misleading v1 that exposes style metadata without meaningful generation differences or export-safe behavior.
