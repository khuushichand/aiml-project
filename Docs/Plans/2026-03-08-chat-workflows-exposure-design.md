# Chat Workflows Exposure Design

Date: 2026-03-08
Status: Approved

## Summary

Restore Chat Workflows as a first-class web route in the Next.js shell and verify that existing discoverability surfaces reach a resolvable `/chat-workflows` page. The backend API and shared UI feature already exist; the immediate problem is route exposure and shell parity.

## Investigated Context

- The backend feature is implemented and mounted:
  - `tldw_Server_API/app/api/v1/endpoints/chat_workflows.py`
  - `tldw_Server_API/app/main.py`
- The shared UI already contains the route and feature page:
  - `apps/packages/ui/src/routes/route-registry.tsx`
  - `apps/packages/ui/src/routes/option-chat-workflows.tsx`
  - `apps/packages/ui/src/components/Option/ChatWorkflows/ChatWorkflowsPage.tsx`
- The web app is missing the Next.js page shim used by peer workspace routes:
  - Missing: `apps/tldw-frontend/pages/chat-workflows.tsx`
  - Existing peers:
    - `apps/tldw-frontend/pages/mcp-hub.tsx`
    - `apps/tldw-frontend/pages/workflow-editor.tsx`

## User-Confirmed Scope

1. Fix direct route exposure for Chat Workflows.
2. Also cover discoverability surfaces that should lead users to Chat Workflows.
3. Do not widen scope into changing backend chat-workflow behavior.

## Problem Statement

The shared UI route registry advertises `/chat-workflows`, and launcher/navigation code already points to that path, but the Next.js web shell does not define the corresponding page entrypoint. That leaves the feature partially integrated: present in shared routing metadata and internal navigation intents, but not resolvable as a real page in the web application.

## Goals

- Make `/chat-workflows` load in the web app using the same dynamic-page pattern as peer routes.
- Ensure existing navigation and launcher surfaces that target `/chat-workflows` lead to a working page.
- Add regression coverage so future shared-route additions are less likely to be omitted from the web shell.

## Non-Goals

- Redesign the Chat Workflows feature UI.
- Change the Chat Workflows API contract or backend permissions model.
- Introduce a generic route-generation system for all Next.js pages.
- Expand the feature into new navigation locations beyond already intended discoverability surfaces.

## Approaches Considered

### 1. Minimal Route Repair

Add only `apps/tldw-frontend/pages/chat-workflows.tsx`.

Pros:
- Smallest possible fix.
- Lowest risk of unrelated regressions.

Cons:
- Does not verify whether discoverability surfaces are actually working.
- Leaves this class of regression easy to miss again.

### 2. Targeted Parity Repair

Add the missing Next.js page shim and verify existing nav/launcher entry points that are already supposed to reach `/chat-workflows`.

Pros:
- Fixes the actual user-facing gap.
- Matches the requested scope.
- Keeps changes constrained to routing/discoverability.

Cons:
- Slightly larger than the minimal fix because tests and nav checks are included.

### 3. Systemic Route Generation

Refactor the web app so Next.js page shims are derived automatically from the shared route registry.

Pros:
- Strongest long-term protection against parity drift.

Cons:
- Oversized for the current bug.
- Introduces architecture churn unrelated to the immediate failure.

## Recommended Approach

Use Approach 2: targeted parity repair.

The issue is not missing feature implementation; it is missing shell exposure. A targeted repair fixes the route, confirms intended discoverability still works, and adds focused regression tests without turning a routing parity bug into a framework refactor.

## Architecture

The shared UI route registry remains the source of truth for Chat Workflows. The web app should follow the established pattern used by other option routes: define a thin Next.js page file in `apps/tldw-frontend/pages/` that dynamically imports the shared route module with `ssr: false`.

No backend changes are required. No changes are required to `ChatWorkflowsPage` itself unless testing reveals a route-specific assumption in the page wrapper.

## Data Flow

### Direct Navigation

1. Browser requests `/chat-workflows`.
2. Next.js resolves `apps/tldw-frontend/pages/chat-workflows.tsx`.
3. The page dynamically imports `@/routes/option-chat-workflows`.
4. The shared route renders `ChatWorkflowsPage`.
5. Existing page logic handles data loading and offline/unavailable states.

### Discoverability

1. Workspace navigation or launcher actions navigate to `/chat-workflows`.
2. The web shell resolves the route instead of returning 404.
3. Users land on the existing Chat Workflows workspace.

## Failure Handling

- If the backend is unavailable, preserve the existing page-level offline state instead of introducing route-level fallbacks.
- If a discoverability surface points to the wrong path, correct it to `/chat-workflows` rather than adding redirects.
- If a parity test already exists for similar routes, extend the existing convention instead of creating redundant test infrastructure.

## Testing Strategy

### Web Shell Parity

- Add a regression test that verifies the web app contains `apps/tldw-frontend/pages/chat-workflows.tsx`.
- Assert the file follows the same dynamic import pattern used by peer routes.

### Shared UI Route Wiring

- Keep or run the existing shared route-registry test:
  - `apps/packages/ui/src/routes/__tests__/chat-workflows-route.test.tsx`

### Discoverability

- Run or extend the existing Playground launcher coverage:
  - `apps/packages/ui/src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`
- Verify workspace nav still exposes the route through shared route metadata after the web-shell page exists.

## Acceptance Criteria

- Visiting `/chat-workflows` in the web app loads the Chat Workflows page instead of 404.
- Existing launcher/navigation surfaces intended to open Chat Workflows still target `/chat-workflows`.
- Regression tests cover the missing-page failure mode.
- No backend API or permission changes are required for this repair.
