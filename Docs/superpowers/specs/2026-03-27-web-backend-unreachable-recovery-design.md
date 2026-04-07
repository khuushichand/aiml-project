# Web Backend Unreachable Recovery Design

**Goal:** Replace vague WebUI runtime crashes with a clear full-page recovery experience when the browser cannot reach the configured tldw server.

## Problem

When the WebUI loses access to the backend, some request failures are already surfaced through a recoverable modal in [WebLayout.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/components/layout/WebLayout.tsx). But other failures still escape into a generic runtime crash path that shows users an unhelpful framework-level error.

The observed server-down case is a transport failure for `/api/v1/llm/models/metadata`:

- the request is issued through `bgRequest(...)`
- the direct web fallback calls `fetch(...)`
- the browser throws before any HTTP response exists
- the app eventually shows a vague Next.js/Turbopack runtime error instead of actionable guidance

The user wants a clearer app-wide recovery screen for the WebUI when the server is down.

## Constraints

- The fix should apply across the WebUI, not only to `/chat`.
- It should not change extension-specific error handling unless explicitly opted in.
- It should not misclassify normal product bugs as “server unavailable”.
- It should preserve the distinction between:
  - invalid networking configuration, already handled by [ConfigurationGuard.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/components/networking/ConfigurationGuard.tsx)
  - temporary or current backend reachability failures

## Existing Behavior

### 1. A mounted route boundary already exists for most shared routes

Most shared WebUI routes render through [RouteErrorBoundary.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx), including chat via [option-chat.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-chat.tsx).

This means route-scoped render errors can already be intercepted before they ever reach a top-level fallback.

### 2. The web-only `ErrorBoundary` is currently not mounted

[ErrorBoundary.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/components/ErrorBoundary.tsx) exists, but [pages/_app.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/pages/_app.tsx) does not currently wrap the app with it.

Special-casing that file alone would not fix the current user-visible crash path until it is actually mounted.

### 3. Error boundaries do not catch async promise rejections

Some server-down failures can still surface as unhandled promise rejections rather than render-time exceptions. The WebUI does not currently bridge `unhandledrejection` into the recovery UI, so those cases can still appear as generic runtime crashes even if route or component boundaries improve.

### 4. There is already a backend-unreachable event

The shared request layer emits `tldw:backend-unreachable` through [request-events.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/request-events.ts) and [background-proxy.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/background-proxy.ts) when transport failures occur.

That existing signal should remain useful for the non-fatal modal flow in `WebLayout`, but it should not compete with a fatal full-page recovery state.

## Desired Behavior

When the WebUI cannot reach the configured backend:

- the user should see a full-page recovery screen rather than a vague runtime crash
- the screen should explain that the app cannot reach the configured tldw server
- the user should have direct actions to:
  - try again
  - reload the page
  - open health diagnostics
  - open settings
- when available, lightweight diagnostics should be shown:
  - method and path of the failed request
  - configured server URL

When the error is unrelated to backend reachability:

- the existing generic error fallback should remain unchanged

## Recommended Approach

### 1. Add a narrow shared classifier for backend-unreachable failures

Create a shared helper in the UI package that classifies errors conservatively.

It should identify backend-unreachable failures only when the evidence is strong, such as:

- `status === 0`
- `NetworkError when attempting to fetch resource`
- `Failed to fetch`
- `Network error`
- a recent `__tldwLastRequestError` record showing a transport-style failure

It should explicitly exclude non-reachability cases such as:

- `AbortError`
- `REQUEST_ABORTED`
- `"The operation was aborted."`

The classifier should return structured information instead of a boolean so the recovery UI can display safe diagnostics without parsing multiple times.

### 2. Add a shared full-page recovery component

Create a shared presentational component in the UI package for the recovery screen.

This component should:

- render as a full-page takeover
- accept structured recovery details
- provide handlers for retry, reload, settings, and diagnostics
- reuse the same user-facing language already introduced in the non-fatal backend-unreachable modal inside `WebLayout`

This keeps route-level and top-level recovery rendering consistent.

### 3. Mount the web error boundary in `_app.tsx`

Wrap the WebUI app content with [ErrorBoundary.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/components/ErrorBoundary.tsx) in [pages/_app.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/pages/_app.tsx).

The boundary should be mounted after [ConfigurationGuard.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/components/networking/ConfigurationGuard.tsx), so configuration errors continue to use their dedicated screen instead of the backend-down recovery screen.

### 4. Extend the mounted web boundary to handle async crash paths

The mounted web boundary should:

- render the shared backend-unreachable recovery screen when a caught error matches the classifier
- listen for `window.unhandledrejection`
- promote classified backend-unreachable rejections into the same recovery state

This covers both:

- render-time errors caught by React boundaries
- unhandled async failures that would otherwise bubble into generic Next.js runtime overlays

### 5. Extend `RouteErrorBoundary` with opt-in backend recovery

Because [RouteErrorBoundary.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx) is shared by both WebUI and extension routes, backend recovery should be opt-in.

Add a prop such as:

- `enableBackendRecovery?: boolean`

When enabled and the caught error matches the classifier, the route boundary should render the shared full-page backend recovery screen instead of the generic route error card.

When the prop is omitted or false, behavior should remain unchanged.

All WebUI shared route wrappers under `apps/packages/ui/src/routes/` should opt in where appropriate. Extension wrappers under `apps/tldw-frontend/extension/routes/` should remain unchanged.

### 6. Prevent duplicate fatal and non-fatal UI

The non-fatal backend-unreachable modal in [WebLayout.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/components/layout/WebLayout.tsx) should not fight with the new fatal full-page recovery screen.

If the fatal recovery screen is active:

- suppress the modal, or
- ensure it is not mounted/opened

The recommended behavior is suppression so the user sees a single clear recovery surface.

## Files

- Create: `apps/packages/ui/src/services/backend-unreachable.ts`
- Create: `apps/packages/ui/src/services/__tests__/backend-unreachable.test.ts`
- Create: `apps/packages/ui/src/components/Common/BackendUnavailableRecovery.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx`
- Modify: `apps/tldw-frontend/components/ErrorBoundary.tsx`
- Modify: `apps/tldw-frontend/pages/_app.tsx`
- Modify: `apps/tldw-frontend/components/layout/WebLayout.tsx`
- Add tests in `apps/tldw-frontend/__tests__/`

## Testing

Write tests first for:

1. backend-unreachable classifier matches `status === 0` transport failures
2. classifier matches `NetworkError when attempting to fetch resource`
3. classifier excludes abort/cancel failures
4. classifier excludes unrelated runtime errors
5. shared recovery component renders expected copy and actions
6. mounted web error boundary renders the recovery screen for a caught backend-unreachable error
7. mounted web error boundary renders the recovery screen for an `unhandledrejection` backend-unreachable error
8. mounted web error boundary still renders the generic fallback for a normal app bug
9. `RouteErrorBoundary` uses backend recovery only when opted in
10. `RouteErrorBoundary` preserves generic behavior when backend recovery is not enabled
11. `WebLayout` does not show the backend-unreachable modal while the fatal recovery state is active

## Risks

- Overly broad classification would hide real application bugs behind a misleading “server unavailable” screen.
- Route-boundary changes could accidentally affect extension UX if backend recovery is not explicitly opt-in.
- Adding only a mounted error boundary without an `unhandledrejection` bridge would still miss some async crash paths.

## Recommendation

Proceed with a shared recovery stack:

- a narrow backend-unreachable classifier
- one shared full-page recovery component
- a mounted top-level web boundary with async rejection handling
- an opt-in route-boundary backend recovery path for WebUI routes

This provides the clear app-wide recovery experience the user wants while keeping the behavior scoped, testable, and resistant to false positives.
