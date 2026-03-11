# Chat Page Rate-Limit Lazy Hydration Design

Date: 2026-03-11
Owner: Codex collaboration session
Status: Approved (design)

## Context and Problem

Users report hitting API rate limits during ordinary use of the WebUI `/chat` page and the extension chat surface.

Current request pressure comes from a combination of frontend behaviors:

- eager mount-time fetching for sidebar history, capability checks, MCP discovery, audio health, model catalogs, and preference hydration
- duplicated server-chat metadata and transcript loading across multiple hooks and surfaces
- full history sweeps for server chat lists
- provider-sensitive model refreshes that can run on the send path

Relevant current anchors:

- [`apps/packages/ui/src/components/Layouts/Layout.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/Layout.tsx)
- [`apps/packages/ui/src/components/Common/ChatSidebar.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/ChatSidebar.tsx)
- [`apps/packages/ui/src/hooks/useServerChatHistory.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useServerChatHistory.ts)
- [`apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx)
- [`apps/packages/ui/src/hooks/useMessage.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useMessage.tsx)
- [`apps/packages/ui/src/hooks/chat/useServerChatLoader.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/chat/useServerChatLoader.ts)
- [`apps/tldw-frontend/extension/routes/sidepanel-chat.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/extension/routes/sidepanel-chat.tsx)

## Goals

1. Reduce background and burst traffic to `tldw_server` during normal chat usage.
2. Reduce downstream provider-sensitive traffic caused indirectly by chat UI refresh and validation flows.
3. Preserve fast initial interaction by rendering the chat shell before optional remote data loads.
4. Keep WebUI and extension behavior aligned through shared request-gating policy.
5. Make lazy-loading explicit in the UI so users understand when data has not been fetched yet.

## Non-Goals

1. Rebuilding the chat UI information architecture from scratch.
2. Adding a new backend endpoint purely for this phase unless pagination/search gaps require it.
3. Replacing existing data-fetch services wholesale.
4. Solving unrelated backend-side rate-limit policy tuning in this design.

## User Decisions Captured During Brainstorming

1. Prefer a broader redesign over a minimal low-risk patch.
2. Optimize both `tldw_server` request volume and downstream provider-triggered traffic.
3. Accept later population of optional chat surfaces if that materially reduces request pressure.

## Design Summary

Use a shared chat-surface request coordinator in `apps/packages/ui` that owns fetch policy rather than fetch implementation.

The coordinator is responsible for:

- visibility and interaction gates
- per-resource freshness windows and cooldowns
- single-flight request deduplication
- scoped last-known snapshots for optional UI
- coalesced invalidation rules

Existing feature-specific hooks and services continue to execute the actual requests. The redesign changes when they are allowed to run and how their results are reused.

## Architecture

Render both WebUI `/chat` and the extension chat shell in phases.

### Phase 1: Interactive shell

Render immediately from local state:

- current transcript
- queued drafts
- selected model and prompt state
- connection snapshot
- locally persisted active conversation identity

This phase must not require optional remote fetches.

### Phase 2: Conversation-critical load

Only the active conversation may perform immediate remote work.

Use one canonical server-backed conversation loader for:

- transcript messages
- minimal conversation metadata
- any required local mirror updates

Do not allow multiple hooks or surfaces to independently fetch:

- `getChat`
- `listChatMessages`
- persona profile
- character profile

for the same active conversation at the same time.

### Phase 3: Optional panel hydration

Optional surfaces fetch only after explicit user engagement:

- server history sidebar
- MCP tools/catalogs/modules
- audio and dictation health
- model and image catalogs

Optional surfaces may render cached snapshot data first, then reconcile after the user opens them.

## Request Classes

The coordinator should classify request behavior into four groups.

### Shell-critical

- no network required
- render from local persisted state only

### Conversation-critical

- active conversation transcript load
- minimal metadata needed for the selected chat
- abortable and single-flight

### Panel-optional

- sidebar history
- MCP health, tools, catalogs, modules
- audio health probes
- voices catalog

These must not run until the owning UI surface is explicitly engaged.

### Provider-expensive

- model catalog refresh
- provider-sensitive catalog refresh paths such as OpenRouter metadata refresh

These must never run implicitly on submit by default.

## Server History Design

Server history needs its own split design because the current UI assumes full client-side filtering.

### Overview mode

Use lightweight, paginated history loading for browsing conversations.

Rules:

- do not sweep all pages on initial mount
- fetch only when the server-history panel is actively engaged
- page additional results on scroll or explicit pagination
- do not use full remote history as a passive badge-count source

### Search mode

Search must not rely on page-one-only client filtering.

Rules:

- treat search as its own explicit fetch path
- either call a server-backed filtered result set or fetch a search-specific paginated slice
- do not silently degrade search completeness

## Desktop Sidebar Gating

The desktop WebUI mounts the chat sidebar persistently in layout, so “fetch when sidebar is visible” is insufficient.

History loading should be gated by all of:

- route is chat-capable
- server-history tab or panel is active
- user has expanded, focused, or otherwise intentionally engaged the panel

Acceptable triggers include:

- first open of the server-history panel
- first focus into the server-history search input
- first scroll or click inside the panel

## Conversation Hydration Rules

Canonical conversation loading should be two-phase.

### Phase A

Load:

- transcript messages
- minimal metadata needed to render the conversation shell

This phase should complete without blocking on persona or character enrichment.

### Phase B

Hydrate secondary details after the transcript is visible:

- persona profile
- character profile
- enriched assistant identity UI

This prevents slow profile lookups from delaying transcript render.

## Model Catalog and Provider Refresh Rules

Model catalogs should be cached, scoped, and advisory unless freshly confirmed.

Rules:

- use persisted model snapshots first
- scope cached model data by server URL, auth mode, and user or org identity
- do not force provider refresh on send by default
- if the selected model is stale or uncertain, warn instead of hard-blocking
- hard-block only on a fresh confirmed miss or a real server-side rejection
- expose explicit `Refresh models` and `Pick another model` actions
- protect manual refresh with cooldowns and single-flight semantics

This preserves provider quota while avoiding false-negative send blocks from stale local metadata.

## Optional Surface UX

Lazy-loading must be explicit in the UI.

Recommended states:

- sidebar history: `Load conversations`
- MCP tools: `Not checked yet`
- voice or dictation: `Check availability`
- model freshness issue: `Selected model may be stale or unavailable`

Do not conflate:

- unchecked
- unavailable
- unhealthy
- rate-limited

## Invalidation Rules

Current chat operations should stop triggering broad history refreshes when narrow local patches are sufficient.

Rules:

- patch local chat history metadata after rename, topic edit, or state change
- coalesce follow-up refreshes instead of invalidating full history repeatedly
- sending a message must not trigger repeated full history sweeps during the same turn
- optional panel refreshes run only when their panel is open and the tab is visible

## Error Handling

### Optional panel failures

- keep failures local to the panel
- 429s on optional panels must not escalate into global chat errors
- apply cooldowns before retry

### Conversation-critical failures

- keep abortable single-flight semantics for chat switching
- cancel stale loads when the user changes chats or tabs quickly
- only surface active-load errors to the current selected conversation

### Provider-expensive failures

- record last attempted refresh time
- prevent repeated submit-click bursts from triggering repeated expensive refresh flows
- prefer user-visible recovery actions over silent retry loops

## Persistence and Cache Scope

All lazy snapshots must be scoped to the active environment.

Minimum cache scope:

- server URL
- auth mode
- user identity or org context where applicable

Clear or ignore stale snapshots when those values change.

## Testing Strategy

### Unit tests

- coordinator visibility gates
- cooldown and freshness policy
- single-flight behavior
- snapshot scoping and invalidation

### Integration tests

- `/chat` initial mount does not fetch server history before panel engagement
- `/chat` initial mount does not fetch MCP tools or catalogs before tools UI is opened
- `/chat` initial mount does not start audio probes before voice or dictation UI is opened
- send flow does not implicitly trigger provider refresh
- conversation load renders transcript before persona or character enrichment completes
- server history search still returns complete results under the new search path

### Extension parity tests

- sidepanel follows the same gating policy as WebUI for optional surfaces
- sidepanel conversation switching reuses canonical single-flight load behavior

### Request-budget regression tests

Use resource-class and forbidden-endpoint assertions rather than brittle raw request counts.

Examples:

- initial chat mount must not hit `/api/v1/chats/`
- initial chat mount must not hit `/api/v1/mcp/health`
- initial chat mount must not hit audio health endpoints
- initial send must not trigger provider refresh endpoints implicitly

## Risks and Mitigations

1. Search completeness regression under paginated history
   - Mitigation: separate overview mode from search mode.
2. False send blocks from stale model cache
   - Mitigation: advisory warning by default; hard-block only on fresh negative or server rejection.
3. Coordinator becoming a monolith
   - Mitigation: coordinator owns policy only, not all request implementations.
4. Cross-account or cross-server stale snapshot bleed
   - Mitigation: strict snapshot scoping and invalidation on auth or server changes.
5. Lazy-loading feels like broken UI
   - Mitigation: explicit unchecked/loading states and clear manual actions.

## Rollout Guidance

Implement incrementally:

1. Introduce coordinator and gating primitives.
2. Move server history behind engagement gates and split browse vs search behavior.
3. Move conversation hydration to one canonical path with two-phase enrichment.
4. Remove implicit provider refresh from send flow.
5. Apply the same policy to extension sidepanel parity.

This ordering reduces rate-limit pressure early while keeping the refactor reversible.
