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
