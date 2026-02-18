# Implementation Plan: Characters - Visual Design and Card Density

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/CharacterGalleryCard.tsx`, `apps/packages/ui/src/components/Option/Characters/Manager.tsx`
Finding IDs: `C-22` through `C-23`

## Finding Coverage

- Gallery cards are too sparse for efficient scanning: `C-22`
- Avatar-less cards are visually indistinguishable: `C-23`

## Stage 1: Increase Gallery Information Density
**Goal**: Improve scannability without sacrificing interaction clarity.
**Success Criteria**:
- Card layout supports title, two-line description, and up to three tag pills.
- Card height and spacing are tuned for readability at common viewport widths.
- Existing action affordances remain visible and clickable.
**Tests**:
- Component tests for description/tag rendering and fallback handling.
- Visual regression snapshots for grid density at desktop/tablet/mobile widths.
- Interaction tests confirming click targets remain stable.
**Status**: Complete

## Stage 2: Introduce Deterministic Avatar Fallback Styling
**Goal**: Differentiate avatar-less characters at a glance.
**Success Criteria**:
- Fallback avatar uses deterministic background color derived from character name.
- First letter/monogram overlays on fallback avatar with sufficient contrast.
- Color generation remains stable across sessions and list re-renders.
**Tests**:
- Unit tests for hash-to-color determinism.
- Accessibility tests validating text/background contrast ratio.
- Component tests for fallback rendering when avatar is absent.
**Status**: Complete

## Stage 3: Add Density Toggle and Final Visual QA
**Goal**: Preserve current minimal view while shipping richer default/optional layouts.
**Success Criteria**:
- Optional "compact gallery" toggle exists if product direction keeps minimal mode.
- Preference persists per user/workspace.
- Final design QA confirms visual consistency across light/dark themes.
**Tests**:
- Integration tests for density toggle persistence.
- Visual regression tests for both compact and rich card modes.
**Status**: Complete

## Dependencies

- Stage 1 should align with Category 2 gallery metadata exposure changes.
- Stage 2 must reuse existing theming tokens to avoid hardcoded color drift.
