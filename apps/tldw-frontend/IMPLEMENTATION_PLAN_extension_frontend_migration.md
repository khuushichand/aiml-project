## Stage 1: Discovery and scope mapping
**Goal**: Build a migration map from the extension architecture to the Next.js frontend with clear scope and risks.
**Success Criteria**: Route/feature inventory from `/Users/macbook-dev/Documents/GitHub/custom-extension`; list of extension-only APIs to replace; routing decision recorded (translate to Next.js pages, no embedded React Router); dependency delta recorded; list of existing `tldw-frontend` pages to replace/redirect; migration goes live at `/` with no feature flag.
**Tests**: Not applicable (analysis stage).
**Status**: Complete

## Stage 2: Scaffold the frontend shell and copy base UI
**Goal**: Bring the extension UI into the Next.js app with minimal wiring and no extension-only runtime errors.
**Success Criteria**: Extension UI mounts in a Next page (client-only if needed); core providers (Antd, React Query, i18n, Tailwind) load; build succeeds.
**Tests**: `npm run lint`, `npm run build`.
**Status**: Complete

## Stage 3: De-extensionize platform dependencies
**Goal**: Replace browser-extension APIs with web equivalents and stabilize data/storage flows.
**Success Criteria**: No `browser.*`/`chrome.*` calls in the UI runtime path; storage uses web-safe adapters; API calls use direct fetch/client with auth; key flows (chat, settings, ingest) work in web mode.
**Tests**: Add/adjust unit tests for new adapters; run `npm run test`.
**Status**: Complete

### Changes Made (2026-01-23):
- Created `lib/i18n-web.ts` with statically bundled English translations for SSR/static generation
- Updated `_app.tsx` to use web-specific i18n instead of shared `@tldw/ui/i18n`
- Fixed `AppProviders.tsx` to be SSR-safe with "ltr" default direction
- All 78 pages now build successfully with static generation
- Production server starts and serves all routes correctly

## Stage 4: Route integration, feature parity, and cleanup
**Goal**: Align routes with Next.js, integrate auth/navigation, and retire the old frontend paths.
**Success Criteria**: Primary routes render in Next.js routing; existing Next pages replaced/redirected; docs updated; test suite and build pass.
**Tests**: `npm run test`, `npm run build`, `npm run test:integration` (as applicable).
**Status**: Complete

### Route Coverage (78 pages):
- Settings: 18 routes (`/settings/*`)
- Workspace & Knowledge: Media, flashcards, evaluations, collections, notes, etc.
- Audio: `/speech`, `/stt`, `/tts`
- Playgrounds: chunking, moderation, kanban, prompt-studio
- Admin: 10 routes (`/admin/*`)
- Chat: `/chat`, `/chat/agent`, `/chat/settings`
- Core: `/`, `/login`, `/profile`, `/search`, etc.
