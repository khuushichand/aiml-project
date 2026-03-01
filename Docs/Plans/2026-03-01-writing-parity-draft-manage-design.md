# Writing Workspace Parity Redesign: Draft/Manage

Date: 2026-03-01  
Status: Approved design  
Scope: WebUI + Extension writing workspace parity

## 1. Context

The writing workspace currently exposes a broad feature set, but the first-run experience is overloaded. The assignment is to improve UX while preserving capability coverage. The product direction for this effort is:

- Maintain **visual parity** between webui and extension.
- Optimize the shared experience for **drafting speed** first.
- Introduce a **mode switch** with default mode set to **Draft**.

## 2. Goals and Non-Goals

### Goals

1. Reduce pre-writing cognitive load while keeping existing feature breadth.
2. Enforce parity of structure, naming, and core interactions across webui and extension.
3. Improve the write-generate-revise loop with editor-first defaults.
4. Keep advanced controls discoverable but out of the default drafting path.

### Non-Goals

1. No backend API redesign or contract changes for writing endpoints.
2. No removal of existing advanced capability areas (templates, themes, context, token tools, wordcloud, diagnostics).
3. No net-new feature invention outside IA and interaction improvements needed for parity and drafting flow.

## 3. Approaches Considered

### Approach A: Visual Cleanup Only

- Keep current IA and reorder little; mostly spacing/typography polish.
- Pros: lowest risk and effort.
- Cons: minimal workflow gain; clutter remains.

### Approach B: Draft-First IA (Recommended)

- Introduce shared `Draft` and `Manage` modes.
- Move high-frequency writing actions into Draft and all advanced management into Manage.
- Pros: strong usability improvement with controlled implementation risk.
- Cons: moderate refactor of section layout and mode-aware rendering.

### Approach C: Full Component Unification Rewrite

- Rebuild around a single new shared workspace component and replace current structures.
- Pros: strongest long-term consistency.
- Cons: high scope and risk for current assignment.

**Decision:** Approach B is selected.

## 4. Approved Product Decisions

1. Parity level is **Visual parity**.
2. Primary workflow target is **Drafting speed**.
3. Workspace model is **Draft/Manage mode switch**.
4. Default initial mode is **Draft**.

## 5. Information Architecture

## 5.1 Top-Level Shared Shell

Both surfaces will render the same top-level shell and control taxonomy:

1. Header strip:
   - Mode switch (`Draft`, `Manage`)
   - Session selector
   - Model selector
   - Connectivity and save status
2. Main body:
   - Editor-dominant workspace in Draft
   - Management sections in Manage

Section naming, order, and labels must be identical across webui and extension.

## 5.2 Draft Mode (Default)

Draft mode is optimized for speed and continuity:

1. Editor-first center area:
   - Large prompt editor
   - `Edit | Preview | Split`
   - Inline search/replace
2. Primary action rail:
   - Generate, Stop (while running), Undo, Redo, Insert, Read Aloud
3. Lightweight side areas:
   - Left: compact sessions list + quick CRUD access
   - Right: compact drafting inspector (temperature, max tokens, streaming, stop mode)
4. Advanced tools hidden by default:
   - Context order editing, advanced sampler matrix, logit bias editors, token utilities, wordcloud controls, diagnostics panes

Draft mode keeps generation output and revision in the same place with no modal detours.

## 5.3 Manage Mode

Manage mode contains full control surfaces, grouped consistently:

1. Sessions (CRUD/import/export/usage metadata)
2. Styling and Prompting (Templates + Themes)
3. Generation Settings (core + advanced + extra body JSON)
4. Context (memory block, author note, world info, context order/length, context preview/export)
5. Analysis and Diagnostics (token count/tokenize, response inspector, wordcloud, activity stats)
6. Capability and support notices (disable-with-reason behavior)

Manage must preserve existing feature depth, with section-local loading/error states where possible.

## 6. Visual Parity Contract

The parity contract is mandatory:

1. Same mode names, section names, action labels, and iconography.
2. Same top-level section order and collapse defaults.
3. Same keyboard shortcuts and shortcut hints.
4. Same empty/loading/error pattern language.
5. Same save/generation status chip behavior.

Allowed differences are limited to responsive sizing and constrained-width adaptations in extension. Ordering and semantics cannot diverge.

## 7. Interaction Model Details

1. Default entry state:
   - Mode = Draft
   - Editor submode = Edit
2. Generation loop:
   - User writes -> Generate -> optional Stop -> immediate inline revision
3. Output-to-revision bridge:
   - Keep inline token reroll available behind a collapsed/expandable "Inspect response" area in Draft
4. Persisted preferences:
   - Mode selection
   - Key panel collapse states
   - Editor submode

## 8. Data Flow and State Design

No API changes are required. Existing data contracts and capability handshake remain in place.

Add a UI-state layer:

1. `workspaceMode: "draft" | "manage"` (persisted)
2. Draft panel open/collapse preferences (persisted)
3. Shared section registry:
   - section ids
   - labels
   - order
   - mode visibility

Both webui and extension must consume this single registry to prevent drift.

## 9. Error Handling and Recovery

1. Draft mode:
   - concise, inline errors near active controls (generate/save/find)
2. Manage mode:
   - section-scoped alerts per subsystem
3. Save conflict behavior:
   - preserve unsaved buffer
   - expose refresh/retry affordance
4. Capability-gated controls:
   - visible but disabled with explicit reason text in Manage
   - in Draft, only show controls relevant to fast-path writing

## 10. Testing and Validation

## 10.1 Success Criteria

1. New user can select/create session and generate in under 60 seconds on both surfaces.
2. Draft mode visibly reduces control density versus current workspace.
3. Manage mode retains full advanced functionality.
4. Webui and extension match visual parity contract.

## 10.2 Test Plan

1. Unit tests:
   - mode persistence defaults
   - section registry mode visibility and ordering
2. Integration tests:
   - Draft loop (edit/generate/stop/undo/redo/find)
   - Manage CRUD and tools (sessions/templates/themes/context/token/wordcloud)
3. E2E parity tests:
   - same section ids/order across both surfaces
   - same shortcuts and labels
   - same capability-gating semantics

## 11. Rollout Plan

1. Phase A: Introduce mode shell and move existing sections into Draft/Manage without behavior rewrites.
2. Phase B: Apply Draft-default collapse and streamlined control surface.
3. Phase C: parity hardening, accessibility pass, and regression coverage expansion.

## 12. Risks and Mitigations

1. Risk: hidden advanced controls reduce discoverability.
   - Mitigation: clear Manage entry point and concise in-context links from Draft.
2. Risk: parity drift over time between surfaces.
   - Mitigation: shared section registry + parity e2e assertions.
3. Risk: refactor introduces behavior regressions.
   - Mitigation: staged rollout with feature-preserving migration and focused regression tests.

## 13. Handoff

This design is approved and ready for implementation planning.  
Next step: produce a stage-based implementation plan via the writing-plans workflow.
