## Stage 1: Discovery and scope mapping
**Goal**: Build a migration map from the extension architecture to the Next.js frontend with clear scope and risks.
**Success Criteria**: Route/feature inventory from `/Users/macbook-dev/Documents/GitHub/custom-extension`; list of extension-only APIs to replace; routing decision recorded (translate to Next.js pages, no embedded React Router); dependency delta recorded; list of existing `tldw-frontend` pages to replace/redirect; migration goes live at `/` with no feature flag.
**Tests**: Not applicable (analysis stage).
**Status**: Complete

## Stage 2: Scaffold the frontend shell and copy base UI
**Goal**: Bring the extension UI into the Next.js app with minimal wiring and no extension-only runtime errors.
**Success Criteria**: Extension UI mounts in a Next page (client-only if needed); core providers (Antd, React Query, i18n, Tailwind) load; build succeeds.
**Tests**: `npm run lint`, `npm run build`.
**Status**: In Progress

## Stage 3: De-extensionize platform dependencies
**Goal**: Replace browser-extension APIs with web equivalents and stabilize data/storage flows.
**Success Criteria**: No `browser.*`/`chrome.*` calls in the UI runtime path; storage uses web-safe adapters; API calls use direct fetch/client with auth; key flows (chat, settings, ingest) work in web mode.
**Tests**: Add/adjust unit tests for new adapters; run `npm run test`.
**Status**: Not Started

## Stage 4: Route integration, feature parity, and cleanup
**Goal**: Align routes with Next.js, integrate auth/navigation, and retire the old frontend paths.
**Success Criteria**: Primary routes render in Next.js routing; existing Next pages replaced/redirected; docs updated; test suite and build pass.
**Tests**: `npm run test`, `npm run build`, `npm run test:integration` (as applicable).
**Status**: Not Started
