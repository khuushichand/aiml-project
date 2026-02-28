# repo2txt Integration Design (Webapp + Extension)

Date: 2026-02-28
Status: Approved for planning
Owner: Codex + project maintainer

## 1. Objective

Integrate `repo2txt` into the shared tldw UI as a new options/web page that is available in both:

- `apps/tldw-frontend` (web app)
- `apps/extension` options experience (via shared UI routes)

for a V1 that supports:

- source providers: GitHub + Local (directory/zip)
- output experience: preview + copy + download

and explicitly does not include sidepanel in-panel rendering for V1.

## 2. Scope Decisions (Confirmed)

1. Integration strategy: Hybrid
2. Entry point: options/web route only
3. Provider scope: GitHub + Local only
4. Output scope: keep repo2txt behavior only (no chat/workspace/knowledge handoff in V1)

## 3. Non-Goals (V1)

- No GitLab or Azure provider support
- No sidepanel full route experience
- No automatic send-to-chat or save-to-knowledge actions
- No deep backend integration beyond existing browser-side fetch/provider behavior

## 4. Approaches Considered

## Approach A (Recommended): Shared-core port into `@tldw/ui`

Port repo2txt core logic and selected components into `apps/packages/ui/src`, then expose through route registry.

Pros:

- Aligns with current monorepo architecture (shared routes consumed by web + extension)
- Avoids iframe/CSP complexity
- Easier long-term maintenance/testing in existing toolchain

Cons:

- More upfront adaptation work than simple wrapping

## Approach B: Embedded micro-app (iframe/static bundle)

Ship repo2txt as a separately built app and embed.

Pros:

- Quick to demonstrate

Cons:

- CSP/permissions complexity in extension
- Styling/session/auth disjointness
- Weaker integration with route/nav/testing conventions

## Approach C: Full source transplant with minimal adaptation

Copy most of repo2txt app directly into shared UI and patch until it compiles.

Pros:

- Potentially fast first pass

Cons:

- High technical debt
- React/build/runtime mismatches likely
- Harder to maintain and evolve

## Recommendation

Proceed with **Approach A**.

## 5. Architecture Design

## 5.1 New shared route

Add a new options route in `apps/packages/ui/src/routes`:

- `option-repo2txt.tsx`

Register route in:

- `apps/packages/ui/src/routes/route-registry.tsx`

with options target support and navigation metadata appropriate for options/web discoverability.

## 5.2 Web wrapper

Expose Next.js wrapper:

- `apps/tldw-frontend/pages/repo2txt.tsx`

using existing dynamic-import wrapper pattern (`ssr: false`) to import shared route.

## 5.3 Navigation surfaces (options/web only)

Add route discoverability to selected options/web surfaces:

- header shortcuts data (launcher)
- mode selector “More” menu (or equivalent quick access surface)
- optional settings/workspace navigation grouping if desired for persistent access

V1 intentionally omits sidepanel route integration.

## 6. Component and Module Design

Create a feature module in shared UI:

- `apps/packages/ui/src/components/Option/Repo2Txt/*`

Port/adapt the following from repo2txt:

- provider selector (GitHub + Local tabs/forms)
- file tree browsing and selection
- advanced filters (extension + gitignore)
- output panel (preview + copy + download)
- error presentation
- formatter and tokenizer worker integration

Excluded modules for V1:

- GitLab provider/UI
- Azure provider/UI
- non-essential branding/promo surfaces

## 6.1 State model

Use a local, route-scoped Zustand store adapted from repo2txt slices:

- provider state
- file tree + selection state
- filter state
- UI state (loading/error/output)

Keep it isolated from broader tldw global stores for V1 to reduce coupling risk.

## 7. Data Flow

1. User opens `/repo2txt` in options/web.
2. User chooses GitHub or Local source.
3. Provider fetches tree (GitHub API or local files/zip).
4. User refines selection/filtering.
5. Selected files fetched progressively.
6. Formatter + tokenizer worker generate output and counts.
7. User previews, copies, or downloads output.

## 8. Error Handling and Risk Controls

## 8.1 Compatibility risks

- Adapt repo2txt assumptions to React 18 and shared UI conventions.
- Keep worker loading compatible across Next web and WXT extension builds.

## 8.2 CSP/permission concerns

- Favor native shared-route integration (no iframe).
- Validate extension host permission behavior for `api.github.com` during implementation.

## 8.3 Performance

- Keep async/progressive file fetch behavior.
- Keep worker-based tokenization for large repositories.
- Avoid introducing heavy dependencies beyond already-present workspace deps where possible.

## 9. Testing Strategy

## 9.1 Unit tests

- GitHub parsing + normalization behavior
- Local provider directory/zip behavior
- selection/filter/gitignore state logic
- formatter/token accounting behavior

## 9.2 Route/render tests

- `option-repo2txt` loads correctly
- loading/error/empty states
- Next wrapper page wiring in `tldw-frontend`

## 9.3 Navigation tests

- Route appears in chosen options/web navigation surfaces
- No sidepanel in-panel exposure in V1

## 9.4 Manual validation

- Web: `/repo2txt` GitHub export and local export
- Extension options: equivalent flow parity
- Copy and download outputs match expected content and counters

## 10. Acceptance Criteria (V1)

1. Options/web page exists and is reachable in both web and extension options contexts.
2. GitHub + Local providers work end-to-end.
3. Output preview, copy, and download work with token/line counts.
4. No regressions in existing shared routing and navigation behavior.

## 11. Follow-on Phases (Post-V1)

Potential V2+ items:

- GitLab/Azure provider reintroduction
- sidepanel launcher shortcuts that open options route directly
- tldw handoffs (send output to chat/workspace, optional knowledge ingestion)
- deeper visual unification with tldw design system if needed

