# World Books Accessibility Stage 1 Baseline

Date: 2026-02-18  
Scope component: `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`  
Plan reference: `Docs/Plans/IMPLEMENTATION_PLAN_world_books_12_accessibility_2026_02_18.md`

## Automated Harness Added

- Test file: `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.accessibilityStage1.test.tsx`
- Audited views:
1. Main world-books list
2. Entries drawer
3. Relationship matrix modal
- Rules currently enforced in CI:
1. `button-name`
2. `link-name`
3. `label`
4. `aria-valid-attr`
5. `aria-valid-attr-value`
6. `aria-required-attr`

## Manual Audit Checklist

### Keyboard and focus

- [ ] Open entries drawer, verify focus moves inside drawer (`12.2`)
- [ ] Close drawer with `Esc`, verify focus returns to trigger (`12.2`)
- [ ] Open relationship matrix and keyboard-tab through attachment controls (`12.6`)
- [ ] Verify matrix has efficient keyboard navigation beyond tab-only flow (`12.6`)

### Screen reader semantics

- [ ] Confirm disclosure controls announce expanded/collapsed state (`12.3`)
- [ ] Confirm conflict indicators announce conflict meaning (`12.4`)
- [ ] Confirm switch controls announce state and intent clearly (`12.5`)
- [ ] Confirm field-level validation errors are announced with linked descriptions (`12.8`)

### Contrast

- [ ] Validate `text-text-muted` against light backgrounds for WCAG AA (`12.7`)
- [ ] Validate `text-text-muted` against dark backgrounds for WCAG AA (`12.7`)

## Baseline Finding Traceability

| Finding | Baseline Status | Evidence | Planned Stage |
|---|---|---|---|
| `12.1` Icon-only button labels | Partially verified | Stage 1 automated `button-name` rule across main/list/drawer/matrix views | Stage 2 hardening |
| `12.2` Drawer focus management | Open | No deterministic focus-return assertion yet | Stage 3 |
| `12.3` Disclosure announcement | Open | Native `<details>/<summary>` still used in multiple sections | Stage 2 |
| `12.4` Conflict announcement | Open | Conflict visuals and tooltip exist; explicit SR conflict announcement still incomplete | Stage 4 |
| `12.5` Switch semantics | Open | Switches present; explicit `On`/`Off` semantics not consistently enforced | Stage 2 |
| `12.6` Matrix keyboard model | Open | Matrix/list views exist; grid-style keyboard model not yet implemented | Stage 3 |
| `12.7` Contrast for muted text | Open | Contrast audit not yet captured for tokenized colors | Stage 4 |
| `12.8` Validation aria-describedby | Open | Not yet validated with explicit test assertions | Stage 4 |

## Stage 2 Delta (2026-02-18)

- `12.1` strengthened: icon-only world-book row actions remain explicitly aria-labeled and now have dedicated regression test coverage.
- `12.3` mitigated: disclosure summaries now report `aria-expanded` with explicit `aria-controls` wiring in create/edit/import and entry-authoring disclosure blocks.
- `12.5` mitigated: switch controls now expose explicit `On`/`Off` children and include explicit labels where controls were previously ambiguous (for example, bulk add mode).

## Stage 3 Delta (2026-02-18)

- `12.2` mitigated: entries drawer and relationship matrix workflows now persist trigger focus targets and restore focus to the initiating control on close, with regression coverage in `WorldBooksManager.accessibilityStage3.test.tsx`.
- `12.6` mitigated: matrix view checkboxes now expose grid metadata and arrow-key navigation (`Arrow`, `Home`, `End`) across matrix cells, with keyboard regression coverage.

## Stage 4 Delta (2026-02-18)

- `12.4` mitigated: keyword conflict tags now include explicit conflict-oriented `aria-label` text and a polite status announcement for aggregate conflict count.
- `12.8` verified: required-field validation continues to expose `aria-describedby` linkage; regression assertions now verify both invalid state and resolved described-by targets.
- `12.7` verified: token-level contrast checks for `--color-text-muted` against both light/dark backgrounds now run in `WorldBooksManager.accessibilityStage4.test.tsx`, enforcing WCAG AA threshold (>= 4.5:1) for body-sized text.
