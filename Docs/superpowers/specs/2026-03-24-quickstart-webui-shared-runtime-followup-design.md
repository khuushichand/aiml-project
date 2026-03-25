# Quickstart WebUI Shared Runtime Follow-Up Design

Date: 2026-03-24
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Close the gaps left by the initial quickstart same-origin WebUI rollout. The default Docker + WebUI quickstart must keep both shared HTTP and shared WebSocket browser traffic on the WebUI origin, fail fast when advanced mode is incomplete, and stop seeding loopback backend URLs into browser runtime config. The Docker single-user guide must also launch the actual WebUI path it describes.

## Problem

The initial quickstart same-origin work moved the web-only API client onto relative `/api/...` requests, but it did not fully update the shared runtime and transport layers used by the WebUI.

Today:

- `apps/tldw-frontend/extension/shims/runtime-bootstrap.ts` still seeds browser config with `http://127.0.0.1:8000` when `NEXT_PUBLIC_API_URL` is empty.
- Shared UI HTTP consumers still depend on `tldwConfig.serverUrl` in several code paths.
- Shared UI stream builders still construct direct backend WebSocket URLs from `serverUrl`.
- Advanced mode still falls back instead of requiring an explicit browser-reachable API URL.
- IPv6 loopback is not consistently treated as non-browser-reachable.
- The Docker single-user guide still tells users to run the API-only compose path while describing the WebUI proxy path.

This leaves quickstart only partially same-origin and still capable of failing from non-localhost browser origins in ways that look like application bugs.

## Goals

- Keep the default Docker + WebUI quickstart same-origin across the shared browser runtime, not just the web-only REST client.
- Stop quickstart WebUI bootstrap from seeding `127.0.0.1:8000` or other stale loopback defaults into browser config.
- Make advanced mode explicit and fail fast when `NEXT_PUBLIC_API_URL` is missing or unreachable from the browser context.
- Treat IPv4 and IPv6 loopback consistently in browser reachability checks.
- Fix the Docker single-user guide so it launches and verifies the real WebUI quickstart path.

## Non-Goals

- Redesign the existing shared UI `hosted` product mode.
- Remove explicit backend host configuration from extension or non-web browser surfaces.
- Rewrite all connection-related UI copy for every surface.
- Replace the earlier quickstart same-origin feature with a new architecture from scratch.

## Constraints

### Platform separation

The shared UI layer serves more than one browser-facing surface:

- the Next.js WebUI, which can rely on same-origin browser traffic in quickstart mode
- extension/browser-app contexts, which still require explicit backend host semantics

The fix must not globally replace explicit-host behavior across all surfaces.

### Hosted mode is not the right abstraction

The existing `apps/packages/ui/src/services/tldw/deployment-mode.ts` helper controls product behavior such as route gating. It must not be reused as the transport contract for the Docker quickstart WebUI path.

### WebSocket support is a gating technical risk

HTTP proxying is already in place for `/api/:path*`. WebSocket-backed features still need explicit validation against the current WebUI edge. The implementation must prove or reject same-origin WS proxy support early instead of assuming it works.

## Current State

### Shared browser config

- `runtime-bootstrap.ts` reads `tldw-api-host` and `NEXT_PUBLIC_API_URL`, then falls back to `http://127.0.0.1:8000`.
- `TldwApiClient.ts`, `useCanonicalConnectionConfig.ts`, and `tldw-server.ts` still contain loopback defaults for browser-side flows.
- Legacy storage keys such as `tldw-api-host`, `tldwConfig.serverUrl`, `tldwServerUrl`, and `serverUrl` can reintroduce stale backend hosts.

### Shared transport

- `request-core.ts` supports a special hosted proxy path, but the WebUI quickstart is not modeled as a first-class shared browser networking mode.
- `persona-stream.ts`, `prompt-studio-stream.ts`, `watchlists-stream.ts`, `useVoiceChatStream.tsx`, and ACP session WebSocket flows still build direct backend WebSocket URLs from `serverUrl`.

### Docs

- `Docs/Getting_Started/Profile_Docker_Single_User.md` launches `Dockerfiles/docker-compose.yml`, which does not start the WebUI overlay path it describes.

## Proposed Design

### 1. Add a browser networking mode helper in shared UI

Introduce a new shared helper in `apps/packages/ui` that models browser transport behavior without changing product/route gating.

Planned modes:

- `quickstart`
  - only for the Docker WebUI browser path
  - browser uses same-origin HTTP and WebSocket endpoints exposed by the WebUI edge
  - browser must not depend on an explicit backend host
- `advanced`
  - browser uses an explicit, browser-reachable backend origin
  - missing API origin is invalid

This helper must be platform-aware:

- WebUI `http`/`https` contexts may use quickstart same-origin behavior
- extension/browser-app contexts keep explicit-host semantics

### 2. Make shared browser config hydration mode-aware

Update browser runtime/bootstrap and shared config hydration so quickstart WebUI does not write loopback defaults into stored connection state.

Expected behavior:

- quickstart WebUI ignores stale loopback defaults from storage when a same-origin path is intended
- advanced mode preserves explicit external hosts
- extension contexts continue to use explicit configured server URLs

Storage precedence must be explicit:

1. explicit advanced/custom host chosen by the user
2. valid existing canonical stored config
3. quickstart WebUI same-origin contract
4. legacy fallback values only where explicit-host platforms still require them

### 3. Centralize shared HTTP and WebSocket URL building

Add shared helpers for browser-side HTTP base resolution and WebSocket base resolution.

Requirements:

- HTTP quickstart resolves to same-origin browser paths
- WebSocket quickstart resolves to same-origin browser WebSocket endpoints
- advanced mode uses the explicit configured origin for both HTTP and WebSocket traffic
- loopback detection covers `localhost`, `127.0.0.1`, `::1`, and `[::1]`

This centralization is required so request-core and all stream builders follow the same contract instead of drifting independently.

### 4. Extend the WebUI edge contract to cover WebSockets

The default quickstart promise must include browser-visible WS-backed features, not only REST traffic.

The implementation must first prove whether the current WebUI edge can support same-origin WebSocket upgrade proxying with acceptable risk.

Preferred outcome:

- the WebUI edge exposes same-origin WebSocket endpoints that forward to the backend container

Fallback if the current Next.js edge cannot safely support this:

- add a lightweight reverse-proxy layer in the Docker quickstart path that fronts both Next.js and the backend for HTTP and WS traffic

The implementation should not silently leave WS-backed screens on direct backend URLs.

### 5. Make advanced mode explicitly fail fast

Advanced mode must reject incomplete configuration.

Required invalid cases:

- `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced` with no `NEXT_PUBLIC_API_URL`
- advanced mode API URL on loopback when the page origin is not loopback

Failure behavior:

- fail at build/startup where possible
- otherwise render a blocking configuration error with specific remediation
- do not fall back to the page origin in advanced mode

### 6. Correct the Docker single-user guide

`Docs/Getting_Started/Profile_Docker_Single_User.md` must either:

- direct users to `make quickstart`, or
- explicitly use the compose overlay that starts the WebUI stack

Its verification steps must include the WebUI path on `http://127.0.0.1:8080`, not just the backend docs and quickstart endpoint.

## Architecture

### Quickstart WebUI browser flow

1. User launches the Docker + WebUI quickstart path.
2. Browser networking mode resolves to `quickstart`.
3. Shared browser config hydration keeps same-origin WebUI semantics instead of storing a loopback backend default.
4. Shared HTTP requests resolve to same-origin proxy paths.
5. Shared WebSocket features resolve to same-origin WebSocket endpoints on the WebUI edge.
6. The WebUI edge forwards HTTP and WS traffic to the backend container.

Result:

- the WebUI browser path stays same-origin across shared UI surfaces
- backend loopback defaults do not leak into browser runtime state

### Advanced browser flow

1. Operator selects `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced`.
2. `NEXT_PUBLIC_API_URL` is required and browser-reachable.
3. Shared browser config stores and uses that explicit origin for HTTP and WS.
4. Missing or invalid advanced config fails fast.

## Components

### Shared browser networking helper

Responsibilities:

- define browser transport mode independently of product/route gating
- expose quickstart versus advanced origin resolution
- expose loopback reachability checks, including IPv6 loopback

### Shared config/bootstrap updates

Responsibilities:

- stop WebUI quickstart from seeding loopback backend URLs
- preserve explicit-host behavior where still required
- reconcile legacy storage keys with deterministic precedence

### Shared transport updates

Responsibilities:

- route shared HTTP requests through the correct browser transport base
- route shared WebSocket features through the same contract
- keep extension behavior explicit and unchanged where required

### WebUI edge proxy

Responsibilities:

- expose same-origin HTTP and WS paths for quickstart
- forward traffic to the backend container
- preserve auth and streaming semantics

### Docs and contract tests

Responsibilities:

- keep command paths aligned with the actual quickstart stack
- keep same-origin and advanced-mode guidance accurate

## Error Handling

### Quickstart WebUI stale host config

If browser config still contains a stale loopback or mismatched host while running the WebUI quickstart path:

- bootstrap should normalize or ignore it before shared feature code runs
- browser should not silently continue with a direct loopback backend host

### Advanced incomplete configuration

If advanced mode is selected without a usable `NEXT_PUBLIC_API_URL`:

- startup or build should fail
- browser runtime should not fall back to page origin or any loopback default

### WebSocket proxy infeasibility

If the current WebUI edge cannot support safe WS upgrade proxying:

- implementation must switch to an explicit proxy layer for quickstart
- do not ship a partial quickstart story that still leaves WS-backed features cross-origin

## Testing Strategy

### Unit tests

- browser networking helper quickstart versus advanced behavior
- loopback detection, including `[::1]`
- shared runtime/bootstrap avoiding loopback seeding in quickstart WebUI
- advanced validation rejecting missing `NEXT_PUBLIC_API_URL`

### Shared transport tests

- request-core quickstart behavior without explicit backend host
- request-core advanced-mode failure on missing explicit API origin
- stream builders for persona, prompt studio, watchlists, ACP, and any other touched WS features

### WebUI tests

- WebUI guard/validator coverage for advanced-mode missing API URL
- representative same-origin quickstart browser behavior for shared UI flows

### Docs contract tests

- Docker single-user guide launches the actual WebUI quickstart path
- verify steps mention the WebUI endpoint as part of the profile contract

## Acceptance Criteria

- The Docker + WebUI quickstart path does not write `127.0.0.1:8000` into browser runtime config for the WebUI surface.
- Shared HTTP and shared WebSocket browser traffic in quickstart mode use the WebUI origin, not a direct backend host.
- Advanced mode without `NEXT_PUBLIC_API_URL` fails fast.
- IPv6 loopback is treated the same as IPv4 loopback in browser reachability checks.
- The Docker single-user guide launches and verifies the actual WebUI quickstart path it describes.
