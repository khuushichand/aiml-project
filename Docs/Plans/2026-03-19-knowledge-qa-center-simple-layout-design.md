# Knowledge QA Simple Layout Centering Design

**Date:** 2026-03-19

**Goal**

Center the `/knowledge` simple-mode content column within the available workspace area without increasing the current readable width or changing research-mode side panels.

**Problem Summary**

The visible "Ask Your Library" experience is rendered by `KnowledgeQA` in the shared UI package, not by the thin Next.js route wrapper. The screenshot shows the simple empty state feeling left-justified even though some inner wrappers already use `mx-auto`. That means the fix should target the actual knowledge layout lane, not the global application shell.

**Relevant Files**

- `apps/packages/ui/src/routes/option-knowledge.tsx`
- `apps/packages/ui/src/components/Common/PageShell.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

**Design Decision**

Apply the centering fix in `KnowledgeQALayout.tsx`, scoped to the simple layout path (`effectiveSimple`), and preserve the existing `max-w-3xl` content width.

This keeps the change local to the knowledge workspace content lane and avoids collateral changes in:

- the global option layout shell
- the top header and page shell behavior
- research mode, which intentionally uses a left history pane and right evidence rail

**Why This Scope**

`option-knowledge.tsx` already uses `PageShell` with `max-w-full`, so the route shell is intentionally full-width. `KnowledgeQALayout.tsx` is where the empty-state hero, recent sessions, search composer, and results lane are assembled. That is the narrowest layer that can correct the perceived alignment while preserving the intended workspace structure.

**Non-Goals**

- Do not widen the content column.
- Do not change research-mode spacing or side panels.
- Do not rework the hero copy, search bar, or toolbar composition.
- Do not change unrelated routes in `OptionLayout` or `PageShell`.

**Risks**

1. A blanket centering change could fight research-mode layout and evidence-rail positioning.
2. A weak test could pass without proving the visual lane is centered.
3. Because layout bugs are visual, unit tests alone are insufficient.

**Mitigations**

1. Gate the alignment change to simple mode only.
2. Update the golden layout test to assert the class contract on the specific shell wrapper that we modify.
3. Run a local visual check after the tests pass.

**Testing Strategy**

- Update the knowledge golden layout test first so it fails against the current layout contract.
- Implement the smallest layout change needed in `KnowledgeQALayout.tsx`.
- Re-run the focused Vitest file.
- Perform a browser check on `/knowledge` to confirm the column is centered and width is unchanged.
