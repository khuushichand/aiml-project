# Prompt Assembly Preview and Context Inspector - PRD

## Summary
Provide a prompt preview panel that shows final prompt sections, token counts, and conflicts, while defining shared token budgets and truncation behavior across character chat features.

## Goals
- Make prompt assembly transparent with section-level visibility.
- Surface token budgets, truncation, and conflicts before generation.
- Define shared token budget caps and retention order.

## Non-Goals
- Editing prompt content directly in the preview.
- Changing core prompt assembly beyond visibility and budgets.

## Users and Use Cases
- Power user wants to know why the prompt behaves a certain way.
- Developer wants to debug prompt assembly conflicts.
- User wants to see token usage and truncation warnings.

## Scope
1. Stage G1 (MVP). Collapsible prompt preview showing final sections and token counts, active section indicators, and warnings for conflicts.
2. Stage G2. Preview-only toggles per section and model-specific token limit warnings.

## Requirements
Functional requirements:
- Add a collapsible prompt preview that shows final prompt sections and token counts.
- Highlight active sections: system prompt, character preset, author note, greeting, lorebook, actor or world book.
- Detect overlapping keys or contradictory system directives and show a warning.
- Include concise examples in the preview panel that explain conflict resolution semantics.
- Support preview-only toggles per section in Stage G2.
- Include model-specific context limits and budget warnings in Stage G2.

Non-functional requirements:
- The preview must match the actual prompt assembly output.
- Warnings must not block generation.

## Shared Token Budget Allocation
Global supplemental injection budget per prompt: 1200 tokens across greetings, presets, author notes, lorebook, and actor or world book injections.

Per-feature caps:
- Greeting: 120 tokens max.
- Author note: 240 tokens max total for shared plus active character note.
- Character presets: 180 tokens max.
- Lorebook entries: 420 tokens max total, cap each entry at 140 tokens.
- Actor and world book injections: 240 tokens max combined, actor up to 160 tokens and world book up to 80 tokens.

Retention and truncation strategy:
- Priority order for retention: presets, author note, lorebook, actor or world book, greeting.
- Apply per-feature caps first, then enforce the 1200 token total.
- If still over budget after capping, drop or further truncate lowest priority sections in order.
- Prompt preview must flag any truncated section.
- Prompt preview shows a caution warning above 90 percent of budget and an error at the hard cap.

Performance and validation:
- Prompt assembly enforces caps and total limit.
- Performance tests assert total supplemental tokens never exceed 1200 and record truncation events.

## UX Notes
- The preview panel is collapsible and defaults to closed.
- Show section names and token counts in a compact table.
- Use simple language for conflict warnings and examples.

## Data and Persistence
- No persistence required for the preview itself.
- Token counts and conflict signals are computed at prompt assembly time.

## API and Integration
- If prompt assembly is server-side, include a debug metadata object in the response with section tokens and conflicts.
- If prompt assembly is client-side, compute tokens locally with the active tokenizer.

## Edge Cases
- If token counts are unavailable, show "unknown" and suppress budget warnings.
- If a section is empty, hide it from the preview.

## Risks and Open Questions
- Tokenization differences across model providers.
- Potential perf overhead when computing tokens for long sections.

## Testing
- Unit tests for token budget enforcement and truncation order.
- Integration tests for preview accuracy against actual prompt assembly.
- UI tests for warning thresholds and preview toggles.
