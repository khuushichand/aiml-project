# Implementation Plan: Prompts Page - Responsive and Mobile Experience

## Scope

Components: Custom tab toolbar/table and bulk action controls in `apps/packages/ui/src/components/Option/Prompt/index.tsx`
Finding IDs: `8.1` through `8.3`

## Finding Coverage

- Narrow-screen filter/search layout: `8.1`
- Mobile table overflow discoverability and prioritization: `8.2`
- Touch target sizing for bulk controls: `8.3`

## Stage 1: Responsive Toolbar Layout
**Goal**: Make search/filter controls usable and readable on small screens.
**Success Criteria**:
- Fixed widths replaced with responsive/flex sizing by breakpoint.
- Controls wrap cleanly and use available horizontal space on mobile.
- Filter state remains stable during orientation or viewport changes.
**Tests**:
- Responsive component tests at mobile/tablet/desktop widths.
- Visual regression snapshots for wrapped toolbar states.
**Status**: Not Started

## Stage 2: Table Overflow Affordance and Column Strategy
**Goal**: Improve discoverability of horizontally scrollable data and reduce clutter.
**Success Criteria**:
- Scrollable table clearly signals overflow (fade/indicator).
- Lower-priority columns collapse or move to secondary affordance on mobile.
- Critical actions remain visible without requiring full horizontal scan.
**Tests**:
- Component tests for overflow indicator visibility.
- Responsive tests verifying column visibility rules by breakpoint.
- Interaction test for row actions under collapsed-column mode.
**Status**: Not Started

## Stage 3: Touch Target Compliance
**Goal**: Raise touch ergonomics for bulk operations.
**Success Criteria**:
- Bulk action buttons meet minimum target size on touch devices.
- Focus, hover, and active states remain visually consistent after size changes.
- Density adjustments do not regress desktop compact mode.
**Tests**:
- CSS/class tests for mobile target-size constraints.
- Accessibility checks for pointer target sizing and keyboard focus styles.
**Status**: Not Started

## Dependencies

- Touch-target and control-label changes should align with accessibility plan.
