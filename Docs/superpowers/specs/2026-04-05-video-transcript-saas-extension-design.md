# Video Transcript SaaS Extension Design

## Summary

This design defines a lightweight SaaS product for users who want to ingest video URLs, read transcripts, receive eagerly generated summaries, and chat against transcript content without entering the full `tldw` product surface.

The product should ship as a browser extension plus a reduced hosted web experience backed by the existing `tldw-hosted` / `tldw_server` platform. The extension is the discovery and launch surface. The hosted web app is the primary workspace.

V1 should reuse the existing hosted backend, auth, and billing foundations where possible, but the product frontend should live in a separate private project outside the open-source `tldw_server` repository.

V1 should also treat trial management, anonymous identity, lightweight upgrade flow, and repo separation as explicit delivery scope rather than assuming those SaaS pieces already exist in fully productized form.

## Goals

- Offer a browser-store-distributed entry point for transcript-based video analysis.
- Let users ingest a YouTube URL directly from the current page with minimal friction.
- Support a reduced hosted workspace centered on:
  - `Transcript`
  - `Summary`
  - `Chat`
- Generate the default summary eagerly as part of backend workspace readiness rather than as a client-triggered action.
- Reuse the existing `tldw` backend for ingestion, transcript retrieval, summarization, and chat.
- Keep the store-facing extension and hosted app in a separate private project so the product is not directly packaged as part of the open-source monorepo.
- Reuse the existing app through an upstream sync plus private patch-overlay model rather than rebuilding the frontend from scratch.
- Support a limited anonymous trial that demonstrates value before requiring a paid subscription.
- Keep the extension small and opinionated while allowing the hosted app to accept any URL the backend can ingest.

## Non-Goals

- Rebuilding the existing `tldw` backend around a new product-specific media model.
- Shipping a greenfield standalone SaaS frontend unrelated to the existing app surfaces in V1.
- Reproducing the full `tldw` workspace, notebook, or library feature set inside the lightweight mode.
- Building a rich extension-side history manager.
- Exposing all ingestion, RAG, or model configuration knobs in the lightweight experience.
- Restricting the hosted product only to YouTube when the current backend can ingest broader sources.
- Shipping the store-facing product from `apps/extension` or `apps/tldw-frontend` inside the open-source repo.

## Requirements Confirmed With User

- The product should function as a SaaS-oriented frontend distributed via the extension store.
- The backend should be the existing hosted `tldw` project.
- The store-facing product should live in a new project folder outside `tldw_server` so it is not directly associated with the open-source repo.
- The extension UI should stay limited to:
  - quick ingest
  - launcher actions for transcript and chat
  - shallow status and handoff behavior
- V1 should not render full transcript reading or persistent chat directly inside the extension.
- The hosted experience should be the main product surface.
- The extension should detect the current YouTube page and show:
  - `Ingest`
  - `Open transcript`
  - `Quick chat`
- Trial behavior should allow a small demo quota:
  - `3` transcript-backed sessions total
  - each session includes transcript access, summary generation, and limited conversation
- After the quota is exhausted, the user must sign up and pay for a subscription to start new transcript-backed sessions.
- Already unlocked sources remain reopenable for transcript, summary, and follow-up chat after quota exhaustion.
- The main hosted workspace should be a compact video workspace with three tabs:
  - `Transcript`
  - `Summary`
  - `Chat`
- V1 ingestion scope should remain broad in the hosted app:
  - any URL the current backend can ingest
- Anonymous trial should stay narrower than the signed-in product:
  - anonymous trial is YouTube-only
  - broader URL ingest is available after sign-in or in the fuller hosted app flow
- The preferred product direction is:
  - use the existing `tldw` app/auth/billing foundations
  - apply custom branding and labeling for the lightweight mode

## Current State

- The repo already contains a shared browser extension and web UI monorepo under [`/Users/macbook-dev/Documents/GitHub/tldw_server2/apps`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps).
- The extension already uses a background-centered architecture and shared UI package as described in [`/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/extension/AGENTS.md`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/extension/AGENTS.md).
- The shared UI monorepo already supports extension and hosted UI coexistence through [`/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/Shared_UI_Monorepo.md`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/Shared_UI_Monorepo.md).
- The backend already exposes the main primitives needed for the product:
  - media ingestion via `/api/v1/media/process`
  - transcript/audio APIs
  - transcript-grounded retrieval via `/api/v1/rag/search`
  - chat via `/api/v1/chat/completions`
- The repo already includes billing primitives and subscription status surfaces, but SaaS readiness docs still identify missing trial-management and metering work.
- A recent extension design already established the pattern of using the extension as a focused workflow surface rather than a full product clone in [`/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/superpowers/specs/2026-04-03-browser-extension-web-clipper-design.md`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/superpowers/specs/2026-04-03-browser-extension-web-clipper-design.md).
- The existing monorepo should be treated as implementation reference only, not the delivery location for this product frontend.

## Design Constraints Discovered During Review

### Trial Management Constraint

The repo contains billing primitives, but not fully finished trial-management behavior for a hosted SaaS funnel. V1 therefore must explicitly include:

- anonymous trial identity
- trial session accounting
- upgrade conversion boundary
- basic trial analytics or at least durable trial state

These are not optional follow-up polish items.

### Repo Separation Constraint

The user wants the extension and hosted app to live in a separate project outside `tldw_server`. That means the current open-source monorepo can inform implementation patterns, but it should not be the shipping home for the store-facing product.

Any new product shell, extension package, and upgrade surfaces should therefore be planned as a private sibling project that consumes the hosted backend APIs.

### Overlay Maintenance Constraint

The user wants to reuse the existing app rather than build an unrelated private frontend. That makes an upstream-sync plus patch-overlay model preferable to a greenfield rewrite.

The private product should therefore:

- sync selected frontend surfaces from the existing app
- keep product-specific changes in a clearly bounded private patch layer
- minimize deep invasive divergence where possible
- treat upstream sync cost as part of the architecture, not an afterthought
- record exactly which upstream paths were synced and from which upstream commit

### Launcher State Constraint

The extension action set only works if each action has deterministic behavior across backend states. `Ingest`, `Open transcript`, and `Quick chat` must each define behavior for:

- not yet ingested
- ingest in progress
- transcript ready
- transcript failed
- trial exhausted

Without that matrix, the launcher will produce dead-end or inconsistent flows.

### Anonymous Scope Constraint

Allowing anonymous users to submit any backend-ingestable URL expands abuse surface and weakens the store-facing product story. Anonymous trial should stay narrowly scoped to YouTube in V1, while signed-in users can access broader URL ingest.

### Quota Debit Constraint

The product uses a session-based trial quota rather than per-action quotas. That only works if the debit event is defined precisely. V1 must define when a trial session is consumed and when retries or reopen flows do not consume additional quota.

### Orchestration Contract Constraint

The launcher and lightweight workspace both need one canonical answer to: "What is the state of this source for this identity?" That makes a thin backend orchestration contract effectively required for V1, even if it is implemented as a narrow adapter over existing APIs.

That contract must also be idempotent for repeated submissions of the same normalized source, or the product risks duplicate ingests, inconsistent launcher state, and accidental double-consumption of trial quota.

### Privacy And Retention Constraint

A browser extension that sends video URLs and transcript-derived content to a hosted backend needs an explicit user-facing privacy and retention policy. V1 must define what is stored for anonymous users, how long it is retained, and whether trial data can be attached to a later paid account.

## Approaches Considered

### Approach 1: Lightweight Product Mode Inside Existing `tldw`

Add a dedicated reduced route set and branded mode inside the existing hosted app, while keeping the extension as the launch and trial surface.

Pros:

- Fastest path to market
- Reuses current backend, auth, billing, and app shell
- Keeps transcript/chat objects unified with the rest of the platform
- Minimizes product duplication

Cons:

- Requires careful UX discipline to avoid feeling like a trimmed-down admin screen
- Branding separation is partial rather than absolute

### Approach 2: Private Overlay Repo On Top Of The Existing App

Create a dedicated private product repo that imports or syncs selected frontend surfaces from the existing app, then applies a private patch layer for branding, lightweight routing, extension behavior, and upgrade flow.

Pros:

- Cleanest product story for extension-store users
- Reuses proven frontend patterns and components instead of starting from zero
- Keeps store-facing delivery separate from the open-source repo

Cons:

- Requires an explicit sync strategy and patch-drift discipline
- Still adds maintenance overhead compared with shipping directly from the existing app
- Poor boundaries could turn the private repo into a messy long-lived fork

### Approach 3: Extension-Heavy Product

Keep transcript viewing and most chat interactions in the extension, using the hosted app only for upgrade or advanced flows.

Pros:

- Strong in-browser workflow pitch
- Minimal handoff once launched

Cons:

- Highest UI and state-management complexity
- Hardest place to handle auth, subscriptions, and durable history well
- Weakest fit for long-form transcript reading

## Recommendation

Use **Approach 2**.

Build the product as a separate private overlay repo that reuses selected existing app surfaces through sync plus a bounded private patch layer, while still relying on the hosted backend APIs, auth, and billing foundations. The extension stays intentionally narrow: detect supported pages, launch ingestion, surface shallow status, and hand the user into the hosted transcript workspace.

## Product Architecture

V1 should have two intentionally different surfaces.

### Extension Surface

The extension is the entry point, launcher, and upgrade funnel.

Its responsibilities are:

- detect supported YouTube pages
- extract current tab URL and basic metadata when available
- show the three primary actions:
  - `Ingest`
  - `Open transcript`
  - `Quick chat`
- initiate ingest against the hosted backend
- show lightweight readiness or progress status
- hand off to the hosted lightweight workspace

It should not own full transcript reading, durable chat history, or broad media-library functionality.
`Open transcript` and `Quick chat` are entry actions that preserve user intent and deep-link into the hosted workspace; they are not separate in-extension transcript or chat surfaces in V1.

### Hosted Lightweight Web Surface

The hosted app is the primary workspace.

This should live in a separate private hosted app repo, not inside the open-source `tldw` app shell. The core screen is a compact video workspace with three tabs:

- `Transcript`
- `Summary`
- `Chat`

This product should keep a narrow information architecture and avoid exposing the full open-source app surface. It should reuse selected upstream UI patterns and components where they reduce implementation cost, but product-specific behavior should stay in the private patch layer.

### Backend Surface

The backend remains the existing `tldw_server` platform.

V1 should compose existing capabilities rather than invent a separate open-source backend feature set. V1 should add one thin orchestration contract in the backend and consume it from the private overlay product to normalize:

- submit URL for ingest
- query existing ingest status
- resolve the transcript-backed media record
- generate and cache the default transcript summary once transcript readiness is reached
- route chat and summary calls against that record
- return one canonical workspace answer for the launcher and hosted workspace
- derive and persist a canonical normalized-source identity for reuse across extension and hosted lightweight mode
- make repeated submit requests for the same normalized source idempotent

The launcher-facing source response must include identity-aware access state, not just normalized source identity. It must tell the extension enough to distinguish:

- new session allowed
- reopen already unlocked source
- upgrade required

## Workspace Contract And Summary Lifecycle

The backend should grow from a source-state contract into a small workspace contract.

The recommended contract shape is:

- keep `POST /api/v1/media/video-lite/source` for normalization, entitlement checks, and ingest kickoff
- require that `POST /api/v1/media/video-lite/source` returns identity-aware launcher access data such as entitlement plus reopen-vs-upgrade state
- add a backend-backed workspace/status response that includes:
  - `source_key`
  - `source_url`
  - `state`
  - `transcript`
  - `summary`
  - `summary_state`
  - optional `chat_preview` only if the hosted page wants presentational empty-state copy; it is not a separate chat API surface
  - `entitlement`

Because V1 now prefers eager summary generation, summary lifecycle belongs to the backend rather than the hosted page. New source flows should normally move through:

- media `processing`
- media `ready` plus summary `processing`
- media `ready` plus summary `ready`

`summary_state` should be explicit. The useful V1 states are:

- `not_requested`
  - legacy or incomplete records only
- `processing`
- `ready`
- `failed`

The hosted page should open once transcript-ready, even if `summary_state` is still `processing`. `Transcript` should render transcript or transcript-processing state, `Summary` should render summary or summary-processing state, and `Chat` should remain grounded on transcript-ready content.

V1 should not expose a client-triggered summary creation, regeneration, or retry control in the lightweight product. The hosted page should render backend workspace state only. Any summary retry behavior remains a backend concern.

Summary generation should not happen inline on workspace reads. Transcript readiness should enqueue at most one background summary job per normalized source or transcript hash, protected by a dedupe key or equivalent lock. `GET /video-lite/workspace/...` should stay read-only and report `summary_state` without spawning duplicate summarization work during polling.

## User Flow

The primary user flow is:

1. User opens a supported YouTube page.
2. Extension detects the current video and offers `Ingest`, `Open transcript`, and `Quick chat`.
3. If the item is not yet ready for the current user or anonymous trial session, the extension triggers ingest.
4. The extension shows shallow progress feedback.
5. Once transcript-ready, the user is routed into the hosted lightweight workspace.
6. The backend generates the default summary as part of the same workspace lifecycle.
7. The user reads the transcript, reviews the ready or in-progress summary, and asks questions grounded in the transcript.
8. If the anonymous quota is exhausted, the user is pushed into account creation and paid subscription flow.

The hosted experience may also accept direct pasted URLs for sources beyond YouTube, but extension auto-detection in V1 should stay focused on YouTube pages.

Anonymous trial should remain YouTube-only. Broader source support belongs to signed-in users and the fuller hosted path.

Signed-in users should have an explicit hosted intake surface for pasted non-YouTube URLs. That flow should not depend on the extension launcher.

## Launcher Action Matrix

The extension should use the following deterministic behavior.

### `Ingest`

- `Not ingested`
  - start ingest and show progress
- `Ingestion in progress`
  - reopen status and continue polling
- `Transcript ready`
  - deep-link to hosted lightweight workspace
- `Transcript failed`
  - offer retry and fallback to hosted app
- `Trial exhausted`
  - route to sign-up and upgrade
- `Signed in, unsubscribed`
  - route directly to upgrade without a redundant sign-up step

### `Open transcript`

- `Not ingested`
  - start ingest first, then route to transcript when ready
- `Ingestion in progress`
  - open hosted status or waiting screen
- `Transcript ready`
  - deep-link to hosted `Transcript` tab
- `Transcript failed`
  - show plain-language failure and retry path
- `Trial exhausted`
  - route to upgrade unless this exact normalized source was already unlocked for the current identity
- `Signed in, unsubscribed`
  - route directly to upgrade and preserve transcript destination intent

### `Quick chat`

- `Not ingested`
  - start ingest first; do not open an empty chat shell
- `Ingestion in progress`
  - open hosted waiting state with `Chat` as intended destination
- `Transcript ready`
  - deep-link to hosted `Chat` tab
- `Transcript failed`
  - show transcript-preparation failure, not a generic chat error
- `Trial exhausted`
  - route to upgrade unless this exact normalized source was already unlocked for the current identity
- `Signed in, unsubscribed`
  - route directly to upgrade and preserve chat destination intent

## Core Components

The design should keep the system split into five clear units.

### 1. Extension Launcher

Owns supported-page detection, page metadata extraction, shallow status display, and launch/handoff behavior.

### 2. Lightweight SaaS Web Mode

Owns the reduced branded workspace and the three-tab video screen. This is the main user experience.

### 3. Backend Orchestration Layer

Owns ingest initiation, record reuse, status lookup, and transcript/media resolution. This should be thin and built from existing APIs where possible.

### 4. Trial And Quota Gate

Owns anonymous quota accounting, upgrade enforcement, and conversion boundaries. This must be enforced server-side.

### 5. Product-Mode Routing And Branding

Owns route gating, reduced navigation, labels, onboarding copy, and upgrade messaging for the lightweight mode without creating a second product brain.

## Data Flow

The main data flow should be:

1. Extension or hosted lightweight mode submits a URL.
2. Backend creates or reuses the media-processing record.
3. Ingestion and transcription run to readiness.
4. Once transcript-ready, the backend generates or reuses the default summary for that record.
5. Hosted app polls or subscribes for workspace state.
6. Transcript, summary, and chat all bind to the same underlying transcript-backed media record.

The main design rule is to avoid inventing a separate “extension-only video” entity. Extension, hosted lightweight mode, and existing product surfaces should all reference the same underlying backend objects.

## Trial, Auth, And Subscription Model

V1 should use a guided demo model, not an open-ended free tier.

### Trial Behavior

Anonymous users receive `3` transcript-backed sessions total. Each session includes:

- transcript access
- summary generation
- limited follow-up conversation

This is intentionally framed as a single session counter rather than separate per-action quotas.

### Quota Consumption Rule

One trial session is consumed only when a unique normalized source reaches transcript-ready state for the current anonymous identity.

The following should not consume additional quota:

- retrying a failed ingest for the same normalized source
- reopening the same ready transcript
- reopening the existing eager summary for that same source
- asking additional follow-up questions within that same transcript-backed session

If ingest never reaches transcript-ready, the session should not be permanently consumed.

The normalization logic used for quota debit must be the same logic used by the orchestration contract for source reuse and idempotency.

If anonymous trial quota is exhausted, the user may still reopen an already unlocked normalized source for transcript, summary, and follow-up chat. Exhaustion only blocks creation of new transcript-backed sessions.

### State Model

Recommended user states:

- `Anonymous, trial available`
  - can ingest and use the lightweight workspace up to the remaining quota
- `Anonymous, trial exhausted`
  - cannot start new transcript-backed sessions
  - sees upgrade prompts
- `Signed in, unsubscribed`
  - can access account context and purchase flow
  - cannot continue protected actions unless an explicit grace path is added later
- `Signed in, subscribed`
  - full product behavior

### Enforcement Rules

- Quota enforcement must be server-side.
- Anonymous identity should be stable enough to preserve trial continuity, but should not become a fragile pseudo-account system.
- Upgrade prompts should trigger:
  - before the last free session
  - when quota is exhausted
  - when the user attempts durable or cross-device use
- Anonymous trial should be limited to YouTube sources.
- Signed-in users may access broader source ingest according to product entitlement.

The core conversion message should be value-based:

> You have analyzed 3 videos. Subscribe to continue transcript chat and summaries.

### Upgrade And Billing Boundary

V1 should assume billing primitives exist, but should not assume the end-user upgrade flow is already shaped for this lightweight product. The implementation plan should therefore include:

- a branded upgrade entry point from lightweight mode
- a branded checkout or subscription handoff
- a branded post-purchase return path into the lightweight workspace

The upgrade flow should preserve user intent. At minimum it should carry forward:

- the normalized source or resolved media identity
- the intended destination tab such as `Transcript` or `Chat`
- enough context to resume the in-progress lightweight flow after purchase

## Error Handling And Limits

V1 should define explicit failure and boundary states.

### Supported Input Boundary

- Extension auto-detects YouTube pages only.
- Hosted lightweight mode can accept any URL the backend can ingest for signed-in users.
- Anonymous lightweight trial should remain YouTube-only.
- Unsupported sources should fail clearly with retry and fallback paths.

### Failure States

- `Unsupported URL`
- `Ingestion in progress`
- `Transcript unavailable`
- `Summary in progress`
- `Summary unavailable`
- `Trial exhausted`
- `Auth required`
- `Chat unavailable`

Each state should have plain-language copy and a clear next action.

## Privacy And Retention

V1 should define explicit storage and retention behavior for hosted ingestion.

### Anonymous Trial Data

- Store only the minimum source metadata, transcript artifact references, and derived workspace state needed to support the active trial flow.
- Retain anonymous trial data for a short, explicit retention window rather than indefinitely.
- Disclose clearly that transcript processing and chat occur on the hosted `tldw` service.

### Account Conversion

The implementation plan must choose one of two clear behaviors:

- anonymous trial data can be claimed into the newly created account
- anonymous trial data expires and is not migrated

V1 should not leave this ambiguous.

### User-Facing Disclosure

The extension and hosted lightweight mode should both disclose:

- that source URLs and transcript-derived content are sent to the hosted backend
- whether anonymous trial content is retained temporarily or attached to an account
- where users go to manage or delete their data once signed in

### V1 Scope Discipline

The lightweight mode should not become a full clone of `tldw`. V1 should exclude:

- general media-library redesign
- full notebook/workspace behavior
- extension-side advanced history management
- full configuration surfaces for ingest or model tuning
- multi-document or broad knowledge-base chat

## Testing Strategy

Implementation should verify the following flows:

- YouTube page detection and launcher actions in the extension
- ingest handoff from extension to hosted lightweight mode
- ingest status transitions and ready-state rendering
- launcher action behavior across all source states
- eager summary generation once transcript-ready
- summary reuse for reopened normalized sources
- transcript, summary, and chat behavior on transcript-backed media
- server-side trial enforcement across anonymous and signed-in states
- upgrade routing and subscription gating when quota is exhausted
- retention behavior and account-conversion behavior for anonymous trial state

## Open Implementation Questions

These do not block the design, but they must be answered in planning:

- What should the new private overlay project be named and where should it live as a sibling to `tldw_server`?
- Which frontend paths should be synced from the existing app versus replaced by private-only implementations?
- Will the overlay use a fork, vendored sync, or scripted copy-plus-patch workflow?
- What exact anonymous retention window should V1 use?
- Should anonymous trial data be claimable into a newly created account, or should it expire without migration?
- What anti-abuse strategy is acceptable for anonymous YouTube-only trials in the hosted SaaS environment?
- Does "limited follow-up conversation" rely on existing backend chat limits, or does V1 need an explicit per-session chat cap?
- Should the private hosted frontend use an existing checkout surface with branding changes, or a narrower dedicated upgrade wrapper over current billing primitives?

## Decision

Ship V1 as a separate private overlay product repo with its own hosted frontend and extension, backed by the existing `tldw` hosted ingestion, transcript, summary, chat, auth, and billing foundations, with explicit V1 delivery scope for trial management, launcher state handling, orchestration, privacy/retention behavior, repo separation, and upstream sync/patch-overlay maintenance.
