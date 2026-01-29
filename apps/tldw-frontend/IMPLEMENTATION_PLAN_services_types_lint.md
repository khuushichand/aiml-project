## Stage 1: Inventory & Low-Risk Types
**Goal**: Remove obvious `any`/unused warnings in types + small services without behavior change.
**Success Criteria**: `extension/types/*` and small service files lint clean; no runtime logic changes.
**Tests**: `bunx eslint extension/types extension/services/<target>`
**Status**: Complete
**Progress**: `extension/types/*`, `background-proxy.ts`, `chunking.ts`, `background-helpers.ts`, `note-keywords.ts`, `prompt-studio.ts`, `api-send.ts`, `resource-client.ts`, `moderation.ts`, `kanban.ts`, `flashcards.ts`, `native-client.ts`, `audio-*`, `mcp.ts`, `TldwMedia.ts` cleaned.

## Stage 2: Medium Service Modules
**Goal**: Clean `any` + unused warnings in mid-sized service modules (auth, models, routing, server-capabilities).
**Success Criteria**: These modules lint clean with stronger typing and safe guards.
**Tests**: `bunx eslint extension/services/<target>`
**Status**: Complete
**Progress**: `tldw-server.ts`, `TldwAuth.ts`, `TldwModels.ts`, `server-capabilities.ts`, `TldwChat.ts`, agent types/loop/utils cleaned.

## Stage 3: Large Client Refactor (TldwApiClient)
**Goal**: Systematically replace `any`/unsafe casts with typed helpers in `TldwApiClient.ts`.
**Success Criteria**: File lint clean; no public API changes; existing callers unaffected.
**Tests**: `bunx eslint extension/services/tldw/TldwApiClient.ts`
**Status**: Complete
**Progress**: All explicit `any` removed; lint clean for `TldwApiClient.ts`.

## Stage 4: Sweep & Validate
**Goal**: Re-run lint for services + types and verify remaining warnings list.
**Success Criteria**: Only unrelated warnings remain; no new warnings introduced.
**Tests**: `bun run lint` (or scoped eslint)
**Status**: Complete
**Progress**: Ran `bun run lint`; remaining warnings are in other areas (components/hooks/stores/etc.).
