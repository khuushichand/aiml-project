# Decision Record: Notes In-Editor Search Scope (Plan 04 Stage 3)

## Date

2026-02-18

## Context

Plan 04 Stage 3 called for evaluating dedicated in-note search while keeping discovery workflows stable.
The current editor is a textarea/split-preview workflow with browser-native find support.

## Decision

Defer custom in-editor search implementation for now and keep browser-native `Ctrl/Cmd+F` as the supported path.

## Rationale

- Browser find already works across the current editor/preview surface with zero backend changes.
- A custom in-editor search UI would require additional cursor state management, result navigation UX, and split-view parity work.
- Current roadmap priority remains search-result discovery quality and graph/navigation features.

## User-Facing Outcome

- Notes search now includes explicit guidance: "For in-note search, use browser Ctrl/Cmd+F."
- No behavior regression for existing browser find workflows.

## Revisit Trigger

Re-evaluate custom in-editor search when:
- editor migrates to a richer text engine, or
- user feedback shows browser-native find is insufficient for large-note workflows.
