# MCP Hub Navigation Parity Design

Date: 2026-03-27
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Expose the existing MCP Hub page through the same navigation surfaces users already rely on. The web UI already ships both `/mcp-hub` and `/settings/mcp-hub`, but MCP Hub is missing from the command palette's default navigation list, and the extension route registry does not currently expose the route at all. The fix is to make `/settings/mcp-hub` behave like a real settings-shell route, add MCP Hub to the shared command palette's top-level navigation list without duplicating its existing settings-search entry, and restore route parity in the extension so both surfaces can discover and open the same page.

## Problem

MCP Hub exists, but it is not consistently reachable.

Today:

- The web UI page wrappers already expose [apps/tldw-frontend/pages/mcp-hub.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/pages/mcp-hub.tsx) and [apps/tldw-frontend/pages/settings/mcp-hub.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/pages/settings/mcp-hub.tsx).
- The shared UI route registry already includes both `/mcp-hub` and `/settings/mcp-hub` in [apps/packages/ui/src/routes/route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/route-registry.tsx).
- The settings navigation metadata already includes MCP Hub in [apps/packages/ui/src/components/Layouts/settings-nav-config.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/settings-nav-config.ts).
- The global command palette in [apps/packages/ui/src/components/Common/CommandPalette.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/CommandPalette.tsx) does not offer MCP Hub in its default navigation list.
- The extension route registry in [apps/tldw-frontend/extension/routes/route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/extension/routes/route-registry.tsx) does not register MCP Hub at all.

The result is an uneven product surface:

- web users can hit the page only if they know the URL or find it through settings
- command-palette users cannot discover it
- extension users have no route parity for the same feature

This looks like an omission rather than an intentional access restriction because the shared UI already ships the route component and settings nav token.

## Goals

- Expose MCP Hub in the global navigation modal/command palette default navigation list.
- Keep MCP Hub reachable through the settings-oriented route, not just the standalone route.
- Make `/settings/mcp-hub` behave like an actual settings-shell route.
- Restore extension route parity with the shared web route surface.
- Reuse the existing translation token and shared route component rather than inventing a second navigation pattern.

## Non-Goals

- Redesign the MCP Hub page itself.
- Reorganize the broader settings taxonomy.
- Add new MCP Hub capabilities, tabs, or permissions.
- Change server capability gating beyond what existing route infrastructure already does.

## Constraints

### Shared UI owns page behavior

The MCP Hub screen is already implemented in shared UI code. The safest change is to expose that existing page through missing navigation surfaces rather than duplicating route components or adding web-only/extension-only variants.

### Settings context matters

MCP Hub already has two route shapes:

- `/mcp-hub`
- `/settings/mcp-hub`

For navigation-entry purposes, `/settings/mcp-hub` is the better primary target because it should preserve the existing settings navigation context and matches the existing settings nav metadata.

### Settings routes are resolved through a dedicated deferred registry

The live app does not resolve `/settings/*` through the main route registry alone. `DeferredOptionsRoute` loads `option-settings-route-registry.tsx` for settings paths. Any design that expects settings-shell behavior must update that registry, not just the primary route registry or wrapper pages.

### The command palette already has a settings-search path

MCP Hub already exists in the searchable settings index. A new top-level command is still useful for empty-state discoverability, but the design must avoid or explicitly accept duplicate MCP Hub results when a user types `mcp` or similar queries.

### Extension parity should follow existing route-registry conventions

The extension route registry already carries route definitions plus optional `nav` metadata for discoverability. MCP Hub should be added using the same pattern as existing settings routes instead of adding special-case logic elsewhere.

## Current State

### Web UI

- [apps/tldw-frontend/pages/mcp-hub.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/pages/mcp-hub.tsx) dynamically imports `@/routes/option-mcp-hub`.
- [apps/packages/ui/src/routes/option-mcp-hub.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-mcp-hub.tsx) renders the shared `McpHubPage` inside the standard option layout.
- [apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx) already verifies the shared web route registry includes both route paths.
- The live `/settings/*` runtime path is resolved through `DeferredOptionsRoute`, which loads [apps/packages/ui/src/routes/option-settings-route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-settings-route-registry.tsx) for settings paths.
- In that settings-only registry, `/settings/mcp-hub` currently points directly to `OptionMcpHub` instead of a `SettingsRoute` wrapper, so it does not actually inherit the settings shell today.

### Settings nav

- [apps/packages/ui/src/components/Layouts/settings-nav-config.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/settings-nav-config.ts) already defines `/settings/mcp-hub` with `labelToken: "settings:mcpHubNav"`.
- That means the settings page can render MCP Hub in its own left-side navigation group when a route actually uses the settings shell.

### Missing navigation surfaces

- [apps/packages/ui/src/components/Common/CommandPalette.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/CommandPalette.tsx) has hard-coded default navigation commands for pages like chat, knowledge, media, notes, prompts, flashcards, documentation, settings, and health, but not MCP Hub.
- MCP Hub is already present in the command palette's settings-search path through [apps/packages/ui/src/data/settings-index.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/data/settings-index.ts), so adding a top-level command without dedupe would likely create duplicate results on matching queries.
- [apps/tldw-frontend/extension/routes/route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/extension/routes/route-registry.tsx) currently has no `OptionMcpHub` lazy import and no `/mcp-hub` or `/settings/mcp-hub` route definitions.

## Proposed Design

### 1. Make `/settings/mcp-hub` a true settings-shell route

Correct the shared settings runtime so `/settings/mcp-hub` behaves like other settings pages.

Requirements:

- Update the settings-path registry in [apps/packages/ui/src/routes/option-settings-route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-settings-route-registry.tsx), not just the main route registry.
- Ensure the `/settings/mcp-hub` route renders within `SettingsRoute` and `SettingsLayout`.
- Keep `/mcp-hub` available as the standalone route entry point unless later product cleanup decides to remove it explicitly.

Rationale:

- The existing design intent already treats `/settings/mcp-hub` as a settings destination.
- Without this correction, navigating there from the command palette still drops users into the generic option layout rather than the settings shell the route name implies.

### 2. Add MCP Hub to the shared command palette

Add a new navigation command in [apps/packages/ui/src/components/Common/CommandPalette.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/CommandPalette.tsx).

Requirements:

- Use the normal navigation command shape.
- Navigate to `/settings/mcp-hub`.
- Include MCP-appropriate keywords so search terms like `mcp`, `hub`, `policies`, or `servers` can find it.
- Keep the command available only in the non-sidepanel global palette, matching other page-navigation commands.
- Avoid duplicate MCP Hub results when the query also matches the existing settings-search entry. Preferred behavior is to keep the dedicated navigation command for empty-state discoverability and suppress the redundant settings-search result for the same route.

Rationale:

- This is the navigation modal the user asked about.
- Sending users to `/settings/mcp-hub` should preserve the settings shell and left-nav context once the route wiring is corrected.
- It avoids ambiguity about whether `/mcp-hub` is a standalone app page or a settings subsection.

### 3. Add MCP Hub routes to the extension registry

Update [apps/tldw-frontend/extension/routes/route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/extension/routes/route-registry.tsx) to register MCP Hub with the extension shell.

Requirements:

- Add a lazy import for `./option-mcp-hub`.
- Register `/settings/mcp-hub` with `nav` metadata using the existing translation token `settings:mcpHubNav`.
- Register `/mcp-hub` as a plain options route that renders the same shared page.

Rationale:

- The shared UI already treats both paths as first-class routes in web.
- Extension parity should match that route surface unless there is an explicit product reason not to, and no such reason appears in current code.
- Using the existing nav token keeps naming aligned across web and extension.

### 4. Preserve existing settings navigation source of truth

Do not move or redefine MCP Hub settings navigation metadata.

Requirements:

- Keep [apps/packages/ui/src/components/Layouts/settings-nav-config.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/settings-nav-config.ts) as the source of truth for settings-nav labeling and order.
- Only align missing consumers with that source.

Rationale:

- The metadata already exists and appears intentional.
- Reusing it minimizes drift between settings navigation and extension route registration.

## Architecture

### Navigation flow after the change

1. A web user opens the global command palette.
2. The palette includes an `MCP Hub` navigation command.
3. Selecting that command navigates to `/settings/mcp-hub`.
4. The standard settings layout renders, with MCP Hub selected in the settings navigation.
5. If the user types a query that would also hit the settings-search index, the palette shows one MCP Hub destination rather than duplicate results for the same route.

### Extension flow after the change

1. The extension options shell loads routes from its route registry.
2. MCP Hub appears as a registered settings destination through `/settings/mcp-hub`.
3. The standalone `/mcp-hub` path also resolves for parity with the web route surface.

## Testing

Add or update tests that prove the exposed navigation surface instead of relying on manual spot checks.

### Command palette coverage

Add a focused unit test for [apps/packages/ui/src/components/Common/CommandPalette.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/CommandPalette.tsx) that verifies:

- MCP Hub appears in the default navigation results when the palette is opened in global scope.
- Selecting it navigates to `/settings/mcp-hub`.
- Query-driven MCP Hub search does not produce duplicate entries for the same route.

### Settings runtime coverage

Add focused route coverage for the settings-path runtime, not just the main route registry.

Required checks:

- [apps/packages/ui/src/routes/option-settings-route-registry.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-settings-route-registry.tsx) registers `/settings/mcp-hub`.
- `/settings/mcp-hub` resolves through the settings-shell path rather than a standalone `OptionLayout` path.
- Existing route-registry source tests are updated only as needed to reflect the corrected settings-shell behavior.

### Extension route parity coverage

Add a focused source-level parity test under [apps/tldw-frontend/__tests__/extension](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/__tests__/extension) that verifies:

- the extension registry contains `/settings/mcp-hub`
- the extension registry contains `/mcp-hub`
- the settings route uses `labelToken: "settings:mcpHubNav"`

## Risks

### Route discoverability drift

If the command palette label text diverges from the settings nav token wording, users may see inconsistent naming across surfaces. This risk is small and can be minimized by using the same MCP Hub wording the page and settings nav already use.

### Duplicate command palette entries

Because MCP Hub already exists in the settings search index, adding a dedicated navigation command without dedupe could produce redundant search results. The implementation should treat this as a correctness issue rather than a cosmetic follow-up.

### Extension bundle creep

Adding a new lazy route import slightly expands the extension route registry surface. This should be negligible because the page component already exists in shared UI and the extension registry already uses lazy loading for the same class of routes.

## Decision

Proceed with a parity fix:

- correct `/settings/mcp-hub` so it is a true settings-shell route
- add MCP Hub to the shared command palette without duplicate search results
- add `/settings/mcp-hub` and `/mcp-hub` to the extension route registry
- cover both with focused tests
