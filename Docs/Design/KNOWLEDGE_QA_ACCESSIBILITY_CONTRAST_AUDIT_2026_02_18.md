# Knowledge QA Accessibility Contrast Audit (Stage 3)

## Scope

- Token source: `apps/packages/ui/src/assets/tailwind-shared.css`
- Components sampled: `AnswerPanel`, `SearchBar`, `SourceList`, `SourceCard`
- Focused findings: `12.14` (citation + muted text contrast) and related readability pairings.

## Method

- WCAG contrast ratio formula (relative luminance, sRGB transfer curve).
- Measured in both light (`:root`) and dark (`.dark`) token sets.
- Added automated checks in:
  - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/contrastTokens.test.ts`

## Key Ratios

1. Citation badge foreground/background
- Light: `text-white` on `color-primary` -> **4.55:1** (pass)
- Dark: `text-slate-900` on `color-primary` -> **5.67:1** (pass)

2. Muted helper text on surface-2
- Light: `color-text-muted` on `color-surface-2` -> **5.12:1** (pass)
- Dark: `color-text-muted` on `color-surface-2` -> **8.27:1** (pass)

## Remediation Applied

1. Citation badges in `AnswerPanel` now use theme-aware text:
- Light keeps `text-white`.
- Dark uses `dark:text-slate-900` with non-darkening hover treatment.

2. Reduced low-contrast `bg-muted` + `text-text-muted` usage in Knowledge QA controls:
- Search keyboard hint `kbd` labels now use `text-text`.
- Source sort/action chips and uncited index badge use stronger text color on `bg-muted`.

## Outcome

- Stage 3 contrast requirement is met for citation markers and sampled muted text pairings.
- Automated tests now gate regressions for the audited token combinations.
