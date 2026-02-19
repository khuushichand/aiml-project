# Implementation Plan: HCI Review - Cross-Cutting UX Concerns

## Scope

Components: `components/ui/*`, `components/ResponsiveLayout.tsx`, `app/layout.tsx`, all pages
Finding IDs: `8.1` through `8.10`

## Finding Coverage

- `8.1` (Critical): No skip-to-main-content link
- `8.2` (Important): Buttons lack loading states during async operations
- `8.3` (Important): Tables have no sticky headers
- `8.4` (Important): No breadcrumb navigation
- `8.5` (Important): Keyboard shortcuts not discoverable without prior knowledge
- `8.6` (Important): Empty states inconsistent across pages
- `8.7` (Important): No horizontal scroll indicator on mobile for wide tables
- `8.8` (Nice-to-Have): Confirmation dialogs inconsistent (context provider vs standalone)
- `8.9` (Nice-to-Have): Saved views stored in localStorage only, not synced across devices
- `8.10` (Nice-to-Have): Page titles not set per route

## Key Files

- `admin-ui/app/layout.tsx` -- Root layout (ThemeProvider, Providers wrapper)
- `admin-ui/app/providers.tsx` -- Context provider stack (ErrorBoundary → Toast → Confirm → Permission → OrgContext → KeyboardShortcuts)
- `admin-ui/components/ResponsiveLayout.tsx` -- Sidebar + mobile drawer + main content area
- `admin-ui/components/ui/button.tsx` -- Button variants (default, destructive, outline, secondary, ghost, link)
- `admin-ui/components/ui/table.tsx` -- Semantic table components (Table, TableHeader, TableBody, TableRow, TableHead, TableCell)
- `admin-ui/components/ui/empty-state.tsx` -- EmptyState component (icon, title, description, actions)
- `admin-ui/components/ui/confirm-dialog.tsx` -- Dual-mode confirmation (context provider + standalone)
- `admin-ui/components/KeyboardShortcuts.tsx` -- Shortcut help dialog
- `admin-ui/lib/navigation.ts` -- Route definitions with keyboard shortcuts

## Stage 1: Skip Link + Sticky Headers + Button Loading States

**Goal**: Fix the three highest-impact UX issues that affect every page.
**Success Criteria**:
- `ResponsiveLayout.tsx` adds a skip link as the first focusable element: `<a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-background focus:text-foreground focus:border">Skip to main content</a>`.
- Main content area has `id="main-content"` and `tabIndex={-1}` for programmatic focus.
- `Table` component's `<TableHeader>` renders with `className="sticky top-0 z-10 bg-background"`.
- Sticky header works within scrollable containers (not just page scroll).
- `Button` component adds optional `loading` prop: when true, shows a `Loader2` spinner icon (from lucide-react), disables the button, and replaces children with `loadingText` if provided.
- Loading state preserves button width to prevent layout shift.
**Tests**:
- Unit test for skip link: renders, receives focus on Tab, has correct href.
- Unit test for sticky header: TableHeader has sticky class.
- Unit test for Button loading state: shows spinner, disables, preserves width.
- Accessibility test: skip link visible on focus, hidden otherwise.
**Status**: Complete

## Stage 2: Breadcrumbs + Empty States + Page Titles

**Goal**: Improve wayfinding and ensure consistent page behavior for edge cases.
**Success Criteria**:
- New `Breadcrumbs` component: auto-generates from current path using route config in `navigation.ts`.
- Breadcrumbs rendered below the page header on all detail/nested pages (e.g., `/users/123` shows "Users > User 123").
- Breadcrumb items are links except the last (current page).
- Breadcrumbs component placed in `ResponsiveLayout.tsx` for automatic rendering.
- Audit all pages with list/table views and ensure `EmptyState` component is used when data is empty.
- Target pages: users, organizations, teams, api-keys, jobs, incidents, logs, voice-commands.
- Each empty state has contextual message and primary CTA (e.g., "No users found. Create your first user.").
- Each page sets `document.title` via `useEffect` or Next.js `metadata` export.
- Title format: "{Page Name} | Admin Dashboard" (e.g., "Users | Admin Dashboard").
**Tests**:
- Unit test for Breadcrumbs rendering from various paths.
- Unit test for Breadcrumbs with dynamic segments (e.g., `/users/[id]`).
- Audit test: verify all list pages render EmptyState when data array is empty.
- Test that document.title changes on navigation.
**Status**: Complete

## Stage 3: Mobile Table Hints + Dialog Consistency + Shortcut Discoverability

**Goal**: Polish the remaining UX gaps.
**Success Criteria**:
- `Table` component wrapper adds horizontal scroll shadow indicators: right-edge fade gradient when content overflows horizontally, left-edge gradient when scrolled right.
- Gradient implemented via CSS pseudo-elements or scroll event listeners.
- Standardize all confirmation dialogs on the context provider pattern (`useConfirm` hook).
- Audit and migrate any standalone `ConfirmDialog` usage to `useConfirm()`.
- Remove standalone `ConfirmDialog` component export (or mark deprecated).
- Keyboard shortcut hints: sidebar footer shows "Press ? for shortcuts" text.
- First-time admin users see a dismissable tooltip banner: "Tip: Use keyboard shortcuts for faster navigation. Press Shift+? for help."
- Banner shown once per user (tracked in localStorage).
**Tests**:
- Unit test for table scroll shadow appearance on overflow.
- Unit test for confirm dialog via useConfirm hook.
- Unit test for shortcut hint banner (shown once, dismissable, persists dismissal).
**Status**: Complete

## Dependencies

- All changes in this plan are frontend-only with no backend dependencies.
- Stage 1 is fully self-contained and can be implemented immediately.
- Stage 2 breadcrumbs depend on `navigation.ts` route config having complete path-to-label mappings for all routes including dynamic segments.
- Stage 3 dialog migration requires auditing all pages that currently use standalone `ConfirmDialog`.
