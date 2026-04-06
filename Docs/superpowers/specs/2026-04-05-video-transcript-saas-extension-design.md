# Video Transcript SaaS Extension Design

## Summary

This design defines a lightweight SaaS product for users who want to ingest video URLs, read transcripts, generate summaries, and chat against transcript content without entering the full `tldw` product surface.

The product should ship as a browser extension plus a reduced hosted web experience backed by the existing `tldw_server` platform. The extension is the discovery and launch surface. The hosted web app is the primary workspace.

V1 should reuse the existing `tldw` backend, auth, and billing foundations where possible. It should not introduce a separate product backend or a second independent frontend shell unless later demand justifies it.

V1 should also treat trial management, anonymous identity, and lightweight upgrade flow as explicit delivery scope rather than assuming those SaaS pieces already exist in fully productized form.

## Goals

- Offer a browser-store-distributed entry point for transcript-based video analysis.
- Let users ingest a YouTube URL directly from the current page with minimal friction.
- Support a reduced hosted workspace centered on:
  - `Transcript`
  - `Summary`
  - `Chat`
- Reuse the existing `tldw` backend for ingestion, transcript retrieval, summarization, and chat.
- Support a limited anonymous trial that demonstrates value before requiring a paid subscription.
- Keep the extension small and opinionated while allowing the hosted app to accept any URL the backend can ingest.

## Non-Goals

- Rebuilding the existing `tldw` backend around a new product-specific media model.
- Shipping a fully separate standalone SaaS frontend in V1.
- Reproducing the full `tldw` workspace, notebook, or library feature set inside the lightweight mode.
- Building a rich extension-side history manager.
- Exposing all ingestion, RAG, or model configuration knobs in the lightweight experience.
- Restricting the hosted product only to YouTube when the current backend can ingest broader sources.

## Requirements Confirmed With User

- The product should function as a SaaS-oriented frontend distributed via the extension store.
- The backend should be the existing hosted `tldw` project.
- The extension UI should stay limited to:
  - quick ingest
  - simplified chat
  - a reduced transcript-focused media view
- The hosted experience should be the main product surface.
- The extension should detect the current YouTube page and show:
  - `Ingest`
  - `Open transcript`
  - `Quick chat`
- Trial behavior should allow a small demo quota:
  - `3` transcript-backed sessions total
  - each session includes transcript access, summary generation, and limited conversation
- After the quota is exhausted, the user must sign up and pay for a subscription to continue.
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

## Design Constraints Discovered During Review

### Trial Management Constraint

The repo contains billing primitives, but not fully finished trial-management behavior for a hosted SaaS funnel. V1 therefore must explicitly include:

- anonymous trial identity
- trial session accounting
- upgrade conversion boundary
- basic trial analytics or at least durable trial state

These are not optional follow-up polish items.

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

### Approach 2: Separate Branded Frontend On The Same Backend

Create a dedicated hosted frontend for the extension product while still using the same backend APIs and account system.

Pros:

- Cleanest product story for extension-store users
- Full control over onboarding and page structure

Cons:

- Higher frontend maintenance cost
- Duplicates app shell, routing, and product logic early
- Slower V1

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

Use **Approach 1**.

Build the product as a branded lightweight mode inside the existing hosted `tldw` app. The extension stays intentionally narrow: detect supported pages, launch ingestion, surface shallow status, and hand the user into the hosted transcript workspace.

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

### Hosted Lightweight Web Surface

The hosted app is the primary workspace.

This should live inside the existing `tldw` app shell as a dedicated branded mode with a reduced route set and reduced navigation density. The core screen is a compact video workspace with three tabs:

- `Transcript`
- `Summary`
- `Chat`

This mode should hide or de-emphasize unrelated platform areas while reusing the current app infrastructure for auth, sessions, and backend communication.

### Backend Surface

The backend remains the existing `tldw_server` platform.

V1 should compose existing capabilities rather than invent a separate product backend. V1 should add one thin orchestration contract to normalize:

- submit URL for ingest
- query existing ingest status
- resolve the transcript-backed media record
- route chat and summary calls against that record
- return one canonical source-state answer for the launcher and hosted workspace
- derive and persist a canonical normalized-source identity for reuse across extension and hosted lightweight mode
- make repeated submit requests for the same normalized source idempotent

## User Flow

The primary user flow is:

1. User opens a supported YouTube page.
2. Extension detects the current video and offers `Ingest`, `Open transcript`, and `Quick chat`.
3. If the item is not yet ready for the current user or anonymous trial session, the extension triggers ingest.
4. The extension shows shallow progress feedback.
5. Once transcript-ready, the user is routed into the hosted lightweight workspace.
6. The user reads the transcript, requests a summary, or asks questions grounded in the transcript.
7. If the anonymous quota is exhausted, the user is pushed into account creation and paid subscription flow.

The hosted experience may also accept direct pasted URLs for sources beyond YouTube, but extension auto-detection in V1 should stay focused on YouTube pages.

Anonymous trial should remain YouTube-only. Broader source support belongs to signed-in users and the fuller hosted path.

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
  - route to upgrade
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
  - route to upgrade
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
4. Hosted app polls or subscribes for ready state.
5. Transcript, summary, and chat all bind to the same underlying transcript-backed media record.

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
- generating another summary for that same source
- asking additional follow-up questions within that same transcript-backed session

If ingest never reaches transcript-ready, the session should not be permanently consumed.

The normalization logic used for quota debit must be the same logic used by the orchestration contract for source reuse and idempotency.

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
- transcript, summary, and chat behavior on transcript-backed media
- server-side trial enforcement across anonymous and signed-in states
- upgrade routing and subscription gating when quota is exhausted
- retention behavior and account-conversion behavior for anonymous trial state

## Open Implementation Questions

These do not block the design, but they must be answered in planning:

- Should lightweight mode live under a dedicated route namespace, a feature flag, or both?
- Should anonymous trial data be claimable into a newly created account, or should it expire without migration?
- What anti-abuse strategy is acceptable for anonymous YouTube-only trials in the hosted SaaS environment?
- Should lightweight mode use an existing checkout surface with branding changes, or a narrower dedicated upgrade wrapper over current billing primitives?

## Decision

Ship V1 as a branded lightweight mode of the existing `tldw` hosted product, launched from a focused extension workflow and backed by the current ingestion, transcript, summary, chat, auth, and billing foundations, with explicit V1 delivery scope for trial management, launcher state handling, orchestration, and privacy/retention behavior.
