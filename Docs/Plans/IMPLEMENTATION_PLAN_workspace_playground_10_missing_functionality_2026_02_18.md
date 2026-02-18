# Implementation Plan: Workspace Playground - Information Gaps and Missing Functionality

## Scope

Features beyond immediate UX defects: export/import, shortcuts, versioning, annotations, collaboration, templates
Finding IDs: `10.1` through `10.10`

## Finding Coverage

- Near-term high-impact functionality: `10.4`, `10.8`, `10.7`
- Research-depth capabilities: `10.2`, `10.3`, `10.6`, `10.10`
- Ecosystem and long-term scale: `10.5`, `10.9`, `10.1`

## Stage 1: Immediate Power-User Baseline
**Goal**: Ship high-value capabilities that reduce lock-in and improve speed.
**Success Criteria**:
- Workspace export/import supports structured bundle format (JSON/ZIP manifest).
- Keyboard shortcuts implemented for pane focus, new workspace, new note, submit.
- Artifacts track `previousVersionId` for regenerate lineage.
**Tests**:
- Integration tests for export/import roundtrip fidelity.
- Shortcut tests for key bindings and focus behavior.
- Unit tests for artifact version linkage creation.
**Status**: Not Started

## Stage 2: Deep Research Workflow Features
**Goal**: Expand analytical depth and exploration flexibility.
**Success Criteria**:
- Source preview supports highlights/annotations.
- New `Compare sources` output type supports multi-source claim comparison.
- Chat branching supports variant paths from prior turns.
- Generation views show token/cost estimates and workspace cumulative totals.
**Tests**:
- Integration tests for annotation create/edit/delete lifecycle.
- Output generation tests for compare-source schema/prompt formation.
- Unit tests for conversation branch tree operations.
- Unit/integration tests for cost estimation display and aggregation.
**Status**: Not Started

## Stage 3: Templates, Citation Export, and Collaboration Roadmap
**Goal**: Improve onboarding repeatability and external interoperability.
**Success Criteria**:
- Workspace templates ship with at least three presets.
- Citation export supports BibTeX for workspace source set.
- Collaboration design and phased server-sync implementation plan documented.
**Tests**:
- Integration tests for template bootstrap and initial state correctness.
- Unit tests for BibTeX generation from source metadata.
- Contract tests for future sync payload shape/versioning.
**Status**: Not Started

## Dependencies

- Version lineage and compare views should align with Category 3 regenerate behavior.
- Collaboration work depends on backend API strategy outside the current localStorage-only model.
