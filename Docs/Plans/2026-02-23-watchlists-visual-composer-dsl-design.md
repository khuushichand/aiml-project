# Watchlists Visual Composer DSL Design (2026-02-23)

## Scope

Define the next-generation template authoring experience for `/watchlists` in WebUI and extension with:

- A Visual block composer for template construction.
- Full bidirectional Visual↔Code round-trip support.
- Inline section prompt generation for manual authoring/preview.
- A final flow-check pass to improve narrative cohesion.

This design intentionally keeps orchestration manual-only in v1 and does **not** auto-run during scheduled watchlist jobs unless explicitly enabled in a later phase.

## Product Decisions Confirmed

1. Manual-only orchestration in v1 (`authoring/preview` only), no automatic scheduled execution.
2. Primary direction: **Visual block composer DSL (most ambitious)**.
3. Round-trip requirement: **full bidirectional** Visual↔Code.
4. Advanced Jinja policy: **mixed model** with `RawCodeBlock` for unsupported syntax.
5. V1 block set: **core only**:
   - Header
   - Intro summary
   - Repeating item section
   - Group section
   - CTA/footer
   - Final flow-check block
   - Raw code block
6. Final flow-check control: **both modes** (`suggest-only` and `auto-apply`).
7. Storage model: **dual storage** (`content` + `composer_ast`).
8. UX placement: **inside existing TemplateEditor modal**.
9. Rollout: **on by default**.

## Goals

1. Let non-technical users compose high-quality briefings visually without losing expert code control.
2. Preserve Jinja runtime compatibility and current template execution path.
3. Support section-level prompt generation for newsletter components.
4. Add a final cross-section coherence pass that can suggest or auto-apply fixes.
5. Keep WebUI and extension behavior consistent via shared UI package.

## Non-Goals (v1)

1. No scheduled-job auto-orchestration.
2. No block marketplace/sharing system.
3. No full visual editing for all arbitrary Jinja constructs.
4. No replacement of Jinja runtime engine.

## Architecture Overview

### Approach Selected

**CST-first parser + AST projection** (recommended and approved):

- Parse Jinja into a lossless concrete syntax tree (CST).
- Project supported constructs into a typed composer AST.
- Represent unsupported constructs as `RawCodeBlock` nodes.
- Compile AST back to deterministic Jinja source.
- Re-parse edited code and reconstruct visual state (with raw nodes as needed).

This approach best satisfies full round-trip expectations while preserving advanced authoring flexibility.

### Why Not Alternatives

- AST-only compiler weakens round-trip fidelity for formatting/comments/ordering.
- External parser service adds operational burden and slows v1 delivery without immediate product gain.

## UX Design

### Surface Integration

Modify `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx`:

- Keep existing modal and form shell.
- Replace current tab model with authoring modes:
  - `Visual`
  - `Code`
  - `Preview`

### Visual Mode Layout

1. Left rail: ordered block list + add/reorder/duplicate/disable/delete.
2. Center panel: selected block configuration (fields + prompt settings).
3. Right panel: rendered preview + orchestration status and warnings.

### Block Capabilities (v1)

1. `HeaderBlock`
2. `IntroSummaryBlock` (supports inline section prompt)
3. `ItemLoopBlock`
4. `GroupSectionBlock`
5. `CtaFooterBlock`
6. `FinalFlowCheckBlock` (run mode: suggest-only or auto-apply)
7. `RawCodeBlock` (unsupported code passthrough)

### Manual Orchestration UX

- Per-block action: `Generate section`.
- Global action: `Run final flow check`.
- Explicit labeling in UI:
  - "Manual preview only"
  - "Not used in scheduled runs (v1)"

### Preview/Diff UX

- Preview tab supports:
  - current static/live render behavior,
  - plus flow-check diff panel.
- Diff actions:
  - accept all,
  - accept chunk,
  - reject chunk,
  - revert auto-apply.

### Code Mode Behavior

- User can directly edit Jinja.
- On save/switch:
  - parse code,
  - reconstruct visual AST,
  - unsupported sections become `RawCodeBlock`.
- If parse fails:
  - keep code source authoritative,
  - show recoverable parse errors,
  - visual mode enters degraded state until fixed.

## Data Model and Persistence

### Canonical Dual Storage

Template record stores:

1. `content` (existing runtime Jinja string)
2. `composer_ast` (JSON visual model)
3. `composer_schema_version` (string)
4. `composer_sync_hash` (string)
5. `composer_sync_status` (`in_sync | needs_repair | recovered_from_code`)

### Template Metadata Strategy

Extend watchlists template metadata sidecar (`*.meta.json`) to persist composer fields while preserving current version history behavior.

### Sync Contract

1. Visual edit → compile Jinja → update `content` + AST + sync hash.
2. Code edit → parse/project AST → update both stores.
3. Hash mismatch at load triggers repair attempt.
4. On repair failure: preserve code, mark degraded status, continue authoring safely.

## API and Backend Contracts

### Template CRUD Extensions

Update watchlists template schemas/endpoints to accept/return optional composer fields:

- `composer_ast`
- `composer_schema_version`
- `composer_sync_hash`
- `composer_sync_status`

Maintain backward compatibility for legacy templates with `content` only.

### New Manual Authoring Endpoints

1. `POST /api/v1/watchlists/templates/compose/section`
   - Inputs: `run_id`, block id/config, prompt profile/override.
   - Output: generated section content + diagnostics.
2. `POST /api/v1/watchlists/templates/compose/flow-check`
   - Inputs: ordered section outputs + mode.
   - Output: issues + diff; optionally revised composed text for auto-apply mode.

These endpoints are called only from manual authoring/preview flow in v1.

### Runtime Output Path

No change to scheduled output generation path in v1:

- Final rendered `content` remains standard Jinja used by existing output render pipeline.

## Error Handling and Recovery

1. Parse/projection error:
   - keep code source,
   - do not destroy user content,
   - show parser diagnostics.
2. Section generation failure:
   - mark block as failed,
   - keep current content unchanged.
3. Flow-check failure:
   - show error and keep draft unchanged.
4. Save path:
   - never silently discard AST or raw code block content.

## Security and Safety

1. Reuse existing Jinja sandbox and template validation protections.
2. Treat orchestration inputs as untrusted user text.
3. Log failures without logging secrets or sensitive prompt content.
4. Keep RawCodeBlock source strictly user-owned, not auto-expanded by hidden transforms.

## Testing Strategy

### Backend

1. Unit tests for parser/projection/compile/idempotence on supported grammar.
2. Unit tests for raw block preservation of unsupported syntax.
3. Integration tests for template CRUD round-trip with composer fields.
4. Endpoint tests for manual section generation and flow-check modes.

### Frontend

1. Visual mode block operations.
2. Visual↔Code↔Visual round-trip contracts.
3. RawCodeBlock rendering and preservation.
4. Diff accept/reject/revert behavior for flow-check output.

### End-to-End

1. WebUI path `/watchlists`.
2. Extension options path `/watchlists`.
3. Manual authoring orchestration sequence using run-backed preview.

## Rollout Plan

1. Ship v1 on by default (approved).
2. Start with core block set only.
3. Keep scheduled pipeline untouched.
4. Monitor:
   - template save failure rate,
   - parse recovery rate,
   - flow-check error rate,
   - visual mode adoption.

## Risks and Mitigations

1. **Risk:** Round-trip edge cases in complex Jinja.
   - **Mitigation:** RawCodeBlock fallback + deterministic parser tests.
2. **Risk:** User confusion between manual orchestration and scheduled runs.
   - **Mitigation:** explicit labels and help copy in editor.
3. **Risk:** Data drift between AST and content.
   - **Mitigation:** sync hash contract + repair workflow.

## Success Criteria

1. Users can build a multi-section template entirely in Visual mode.
2. Code edits reconstruct visual state without content loss.
3. Unsupported code is preserved as RawCodeBlock, not dropped.
4. Inline section generation and final flow-check work manually in preview.
5. Existing watchlists output generation remains backward compatible.

