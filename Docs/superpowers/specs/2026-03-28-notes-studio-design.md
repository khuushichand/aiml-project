# Notes Studio Design

## Summary

This design adds a `Notes Studio` action inside the existing Notes experience that turns a selected excerpt from a note into structured study notes with a student-notebook presentation.

V1 is intentionally narrow:

- source input comes from a selected excerpt in an existing note
- the default output is a new derived note
- the result is available both as a normal editable note and as a notebook-style Studio rendering
- templates support `lined`, `grid`, and `Cornell`
- diagram generation is optional and happens after note generation
- export is print-optimized HTML with browser PDF export

The design does not try to turn the current Markdown and WYSIWYG Notes editor into a full block editor. Instead, it introduces a dedicated Studio sidecar model for structured notebook state and keeps normal note content as a generated Markdown companion for compatibility.

## Goals

- Let users generate structured study notes from a selected excerpt inside an existing note.
- Preserve the existing Notes system as the canonical note container and workflow entry point.
- Support a notebook-style Studio presentation with `lined`, `grid`, and `Cornell` templates.
- Support an optional handwriting style without making notes unreadable by default.
- Produce a real note that remains searchable, exportable, and editable in the current Notes flows.
- Offer optional diagram suggestions after note generation without making the core note flow depend on diagrams.
- Provide a practical first export path for printing or tablet annotation.

## Non-Goals

- Whole-resource or whole-notebook study-note generation in V1.
- Chapter picker or resource-native source selection in V1.
- Freehand handwriting input or pen-based ink support.
- Full-fidelity server-side PDF rendering in V1.
- A new standalone document type outside Notes.
- Reverse-parsing arbitrary Markdown edits back into structured Studio state.

## Current State

- Notes are currently stored as plain note rows with `title`, `content`, timestamps, versioning, and note links. There is no first-class Studio note storage contract today.
- The Notes editor supports Markdown mode and a limited WYSIWYG mode. Its Markdown to HTML and HTML to Markdown conversion only round-trips a narrow subset of structures.
- Current single-note print export is generic sanitized Markdown rendered to HTML with print CSS.
- The shared Markdown stack recognizes diagram code blocks, but normal Notes rendering does not currently provide a notebook-native inline diagram experience.
- Notes import and export are optimized for plain notes and do not preserve Studio-specific structured state.

## Requirements Confirmed With User

- The primary output should be both:
  - a new editable note inside the existing Notes system
  - a print-ready notebook-style export path
- V1 source scope should be selected excerpts from an existing note, not chapter or resource-native selection.
- Template treatment should apply in the editor experience as a notebook surface, not only at export time.
- Diagram generation should be optional after note generation, not part of the first pass.
- The `Notes Studio` action should live inside the Notes editor.
- The user requested both:
  - create a derived note
  - replace the current selection
- For the initial V1 implementation scope, only `create a derived note` is in scope. `Replace selection` is deferred to a later phase to keep the first plan coherent.
- Compatibility with the current Markdown-based Notes system still matters, but limited structured Studio data is acceptable when explicitly modeled.
- Generated notes should be a hybrid:
  - AI fills the main content
  - some sections or prompts remain for the user to complete

## Design Constraints Discovered During Review

### Notes Storage Constraint

The current note storage path does not expose a real `metadata` field in note CRUD or schemas. V1 must therefore introduce explicit persistence support for Studio state rather than assuming it can ride on incidental extra fields.

### Editor Round-Trip Constraint

The current WYSIWYG conversion only safely round-trips simple headings, paragraphs, lists, code blocks, and inline formatting. Studio must not depend on body-level custom block syntax surviving ordinary Markdown or WYSIWYG edits.

### Import And Export Constraint

Generic note import and export currently preserve plain note fields, not structured Studio payloads. Studio-preserving import and export must therefore be explicitly defined rather than inherited from the plain-note pipeline.

### Diagram Constraint

Raw Mermaid fences are not sufficient as the primary Studio diagram presentation. Notes Studio needs its own renderer for notebook diagrams and should export rendered diagrams rather than relying on artifact-only code block behavior.

## Approaches Considered

### Approach 1: Markdown-Only Cosmetic Overlay

Store only plain Markdown and render notebook visuals as a styling layer over the normal note body.

Pros:

- Lowest storage and migration risk
- Minimal backend changes
- Full compatibility with existing Notes CRUD, import, and export

Cons:

- Weak notebook semantics
- Hard to support Cornell sections cleanly
- Fragile diagram placement
- Poor long-term foundation for structured study-note features

### Approach 2: Studio Sidecar Plus Markdown Companion

Store structured Studio state in a dedicated sidecar model linked to a normal note. Generate a Markdown companion body for compatibility and plain-note editing.

Pros:

- Preserves existing Notes workflows
- Avoids forcing the current editor to become a full block editor
- Supports strong template semantics and notebook rendering
- Gives a clean place for provenance, diagram state, and export settings

Cons:

- Requires new persistence, API, and rendering support
- Needs an explicit stale-state policy when plain Markdown edits diverge

### Approach 3: Fully Separate Studio Document Type

Create a second document type optimized for notebook layouts and sync a simplified version into Notes.

Pros:

- Cleanest notebook-specific model
- Strongest visual and export fidelity potential

Cons:

- Splits the user mental model
- Adds workflow and navigation complexity
- Higher implementation and maintenance cost

## Recommendation

Use Approach 2.

Add explicit Studio sidecar storage linked to an ordinary note, and generate a Markdown companion body for compatibility. This provides notebook-specific structure without overloading the current Notes editor with unsupported rich block semantics.

## Proposed Architecture

### Note Ownership Model

Each Studio note remains an ordinary note record in the Notes system.

That note continues to supply:

- note identity
- title
- searchable plain content
- versioning
- backlinks and keywords
- compatibility with existing note lists, export, and copy flows

Studio-specific state is stored separately and rendered through a Studio-specific surface inside Notes.

### Studio Sidecar Model

Add a new server-side persistence model linked by `note_id`.

Recommended table name:

- `note_studio_documents`

V1 recommendation:

- store this table in the same Notes database as the `notes` table
- use a foreign key on `note_id`
- use `ON DELETE CASCADE` for hard-delete cleanup

Keeping the sidecar in the same database gives the implementation a practical path to transactional create and update behavior. A separate database or service boundary would make note-plus-Studio atomicity significantly harder for little V1 benefit.

Recommended fields:

- `note_id`: primary foreign key to the note
- `payload_json`: canonical structured Studio payload
- `template_type`: `lined`, `grid`, or `cornell`
- `handwriting_mode`: V1 enum with:
  - `off`
  - `accented`
- `source_note_id`: original note the excerpt came from
- `excerpt_snapshot`: the exact excerpt text or a normalized snapshot object
- `excerpt_hash`: stable hash for drift detection
- `diagram_manifest_json`: optional diagram requests and render outputs
- `companion_content_hash`: hash of the generated Markdown companion body
- `render_version`: renderer schema version
- `created_at`
- `last_modified`

The Studio payload is canonical for Studio rendering.

The note `content` field is a generated Markdown companion.

### Lifecycle And Delete Semantics

Studio sidecar behavior should be defined explicitly:

- creating a Studio note should create the note row and sidecar in one transaction
- updating Studio state and regenerating companion Markdown should update both in one transaction
- soft-deleting a note should leave the Studio sidecar intact so restore can recover the full Studio note
- restoring a note should reactivate the same Studio sidecar without regeneration
- hard-deleting a note should remove the Studio sidecar automatically through foreign-key cascade or equivalent cleanup

This keeps Studio notes aligned with the existing Notes trash model instead of silently losing structured state on soft delete.

### Canonical Data Rule

For Studio notes:

- `payload_json` is the source of truth for Studio view, template rendering, diagram placement, and export
- `notes.content` is a companion representation optimized for plain editing, search, copy, fallback export, and compatibility

The system should not attempt to fully reverse-parse arbitrary Markdown edits back into `payload_json`.

Instead:

- if the user edits a Studio note in plain Markdown mode outside Studio actions, mark the Studio document as `stale` or `customized`
- title-only, keyword-only, and backlink-only edits should not mark the Studio document stale
- content edits should mark the Studio document stale whenever the current companion Markdown hash no longer matches the sidecar's `companion_content_hash`
- Studio view should continue showing the last valid Studio render with a warning banner rather than hard-locking the note
- the warning banner should offer:
  - `Regenerate Studio view from current Markdown`
  - `Continue editing plain note`

This keeps the model understandable and avoids brittle reverse parsing.

### Studio Payload Shape

The canonical payload should be small and explicit. A suggested top-level shape:

- `meta`
- `sections`
- `layout`
- `summary`
- `prompts`
- `diagrams`

Required V1 payload fields:

- `meta.source_note_id`
- `meta.excerpt_snapshot`
- `meta.generated_at`
- `layout.template_type`
- `layout.handwriting_mode`
- `sections`

Optional V1 payload fields:

- `summary`
- `prompts`
- `diagrams`

Suggested `meta` contents:

- generation timestamp
- source note reference
- excerpt snapshot
- selected excerpt offsets for Markdown-mode generation when available
- generation model metadata
- stale state markers

Suggested section model:

- cue sections
- main notes sections
- summary section
- fill-in prompts

The payload should describe notebook meaning, not low-level presentational rectangles.

## User Flow

### Entry Point

The `Notes Studio` action lives inside the Notes editor and is only available from Markdown mode in V1.

Why Markdown mode only:

- selection offsets are explicit and stable
- replace-selection behavior is safer
- WYSIWYG round-trip rules are too lossy for excerpt-based Studio generation

If the user is currently in WYSIWYG mode, the UI should prompt them to switch to Markdown mode before invoking the action.

### Generation Flow

1. User selects an excerpt in the current note.
2. User clicks `Notes Studio`.
3. User chooses:
   - template: `lined`, `grid`, or `cornell`
   - handwriting mode: `off` or `accented`
   - output mode: `Create derived note`
4. System generates canonical Studio payload.
5. System generates companion Markdown content from the payload.
6. System creates a new note plus sidecar Studio document.
7. Studio view opens on the resulting note.
8. User may optionally add a diagram afterward.

### Replace Selection Rule

`Replace selection` remains a desired product behavior, but it should not be in the initial V1 implementation slice.

Reason:

- it introduces harder editor-boundary and transaction questions than derived-note creation
- it depends on deterministic safe-replacement rules in Markdown mode
- it is not necessary to validate the core Notes Studio architecture

Follow-up behavior after V1 foundation lands:

- only allow it in Markdown mode
- require a non-empty selection
- require block-aligned selection boundaries
- disallow replacement when the selection intersects fenced code blocks, tables, nested lists, or HTML blocks
- fallback behavior should be deterministic:
  - `Insert below selection`
  - or `Create derived note`

This keeps the first implementation slice coherent while preserving a path to the user-requested replacement workflow.

### Derived Note Rule

`Create derived note` is the default.

The derived note should preserve:

- backlink to the source note in the Studio payload
- excerpt snapshot and excerpt hash
- note title derived from the source title plus study-note semantics

The source note remains unchanged.

## Notebook Templates And Rendering

### Studio View

Studio notes should open in a dedicated `Studio view` inside the Notes experience.

This view is separate from the generic Markdown preview and generic WYSIWYG editor.

Studio view responsibilities:

- render template chrome for `lined`, `grid`, and `cornell`
- render cue and summary areas according to template semantics
- render selective handwriting styling
- render diagrams inline as notebook content
- support print/export using the same rendering contract

V1 Studio view should be render-first, not a full structured editor.

V1 allowed Studio-view interactions:

- template switching if supported by the final implementation slice
- handwriting toggle
- diagram add or retry actions
- regenerate-from-Markdown actions

V1 should not require direct block-level editing inside Studio view. Plain note editing continues to happen through the existing Markdown editor.

### Template Semantics

### Lined

Use a normal notebook page presentation optimized for general study notes.

Best suited for:

- humanities
- reading notes
- concept explanations

### Grid

Use graph-style background and section spacing optimized for STEM or diagram-heavy content.

Best suited for:

- formulas
- structured comparisons
- spatial or stepwise reasoning

### Cornell

Render explicit cue and notes areas plus a summary section.

The AI should fill:

- main notes
- some cue prompts
- summary

The AI should also intentionally leave some recall prompts or fill-in space for the user.

## Handwriting Mode

V1 handwriting is a simple toggle expressed as `handwriting_mode`.

Allowed V1 values:

- `off`: render all text with the standard notebook typography
- `accented`: apply handwriting styling to headings, cues, callouts, and prompt areas only

Default:

- `accented`

V1 rendering rule:

- dense body text remains in a readable notebook font in both modes
- `accented` affects notebook personality surfaces, not long-form study paragraphs

Later phases may add stronger handwriting treatments, but V1 should remain a two-state toggle.

## Diagram Handling

### Diagram Timing

Diagrams are a second-stage action, not part of the first generation pass.

After a Studio note is created, the UI may suggest:

- concept map
- flowchart
- comparison diagram

based on the generated Studio payload.

### Diagram Storage

Diagram requests and outputs live in the Studio sidecar, not only in note body Markdown.

Suggested diagram manifest contents:

- requested diagram type
- source section IDs
- canonical source graph syntax or intermediate graph representation
- rendered SVG cache and render hash
- generation status

V1 recommendation:

- store both the canonical diagram source representation and a cached rendered SVG
- treat the source representation as canonical for edits and retries
- treat rendered SVG as a cache optimized for Studio view and print/export

### Diagram Rendering

Studio view should render diagrams through a dedicated diagram component that outputs notebook-compatible SVG or image content.

Do not rely on plain Markdown fences as the notebook presentation layer.

The companion Markdown may include a simplified textual or fenced fallback when useful, but Studio view should not depend on it.

## Search, Import, Export, And Compatibility

### Search

Search should continue to use the note title and Markdown companion content.

This keeps Studio notes discoverable through the existing FTS note search without requiring Studio-specific indexing in V1.

The companion Markdown should contain semantically useful study content only. It should not include template chrome markers, layout tokens, or notebook-render-only metadata that would pollute note search results.

### Plain Export

Existing plain note export should continue to work and should export the note title and Markdown companion content.

That gives users a safe fallback representation even outside Studio-aware tooling.

### Studio-Preserving Export

Studio-preserving export should be explicitly modeled as a later extension or a separate export option, not assumed to be covered by plain note JSON or Markdown export.

V1 should clearly distinguish:

- plain note export
- Studio print/export

Studio-preserving JSON export and Studio-aware import are explicitly out of scope for V1 unless later planning reintroduces them as a separate slice.

### Import

Generic note import should keep working for plain notes.

Studio-preserving import should not be silently promised in V1 because the current note import path only meaningfully preserves plain note fields and keywords.

If Studio import is added later, it should use an explicit Studio-aware format.

## Print And PDF Export

### V1 Export Contract

V1 should provide:

- print-optimized HTML generated from the Studio renderer
- browser print-to-PDF as the first PDF path
- explicit paper sizes: `US Letter`, `A4`, and `A5`
- default paper size from browser locale in the web UI:
  - `US Letter` for US locale
  - `A4` otherwise

This is a practical first release, but it should be described honestly as print-optimized rather than deterministic, publication-grade PDF rendering.

### Rendering Requirements

The print renderer should support:

- explicit paper size selection
- page margins
- page breaks
- template backgrounds
- Cornell side column layout
- SVG diagram rendering
- font embedding or explicit font fallbacks

The export path should reuse Studio rendering logic as much as possible so the editor and export outputs remain aligned.

## Error Handling

- If Studio generation fails before note creation, create nothing and show a clear failure message.
- If note-row creation, sidecar persistence, or companion-Markdown generation fails during create or update, the operation should fail atomically and roll back.
- If diagram generation fails, keep the note usable and allow retry.
- If print export fails, offer plain note print export as a fallback.
- If a Studio note becomes stale because plain Markdown content was edited outside Studio mode, show a non-destructive warning and allow regeneration.

## Testing Strategy

### Backend

- sidecar table migration tests
- create, fetch, update, and delete Studio document tests
- excerpt provenance persistence tests
- drift and stale-state marker tests
- Studio note and sidecar lifecycle tests

### Frontend

- Markdown-mode excerpt selection flow tests
- derived-note creation tests
- Studio view template rendering tests
- handwriting-mode rendering tests
- stale-state warning tests
- diagram suggestion and retry tests

### Export

- print-HTML generation tests for each template
- page-break and page-size tests
- diagram export rendering tests
- plain export fallback tests

### Integration

- full flow from excerpt selection to Studio note creation
- source-note provenance linking
- note search over generated companion content
- generic note export behavior for Studio notes

## Phasing

### V1

- excerpt selection from Markdown mode
- default derived-note generation
- sidecar Studio storage
- Markdown companion content generation
- dedicated Studio view in Notes
- lined, grid, and Cornell templates
- selective handwriting styling
- post-generation diagram suggestions
- print-optimized HTML and browser PDF export

### Later Phases

- guarded `replace selection` workflow in Markdown mode
- replace-selection guardrail tests
- resource-native and chapter-native entry points
- Studio-aware import and structured export formats
- deterministic server-side PDF rendering
- richer editing inside Studio view
- broader handwriting controls
- batch or whole-resource study-note generation
