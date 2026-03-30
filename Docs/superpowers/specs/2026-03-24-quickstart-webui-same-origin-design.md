# Quickstart WebUI Same-Origin Networking Design

Date: 2026-03-24
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Change the default `make quickstart` WebUI path so the browser talks only to the WebUI origin and the WebUI server proxies API traffic to the backend container. This removes browser CORS from the default first-run experience. Keep explicit absolute API URLs available for advanced deployments, and fail fast when deployment mode and API URL configuration are incoherent.

## Problem

The current quickstart flow can produce misleading browser failures when the WebUI is opened from a different host than the absolute API URL baked into the client bundle.

Today:

- `make quickstart` routes to the Docker WebUI path.
- The WebUI build bakes `NEXT_PUBLIC_API_URL` into the browser bundle.
- The default quickstart value is `http://localhost:8000`.
- If a user later opens the WebUI from a LAN IP or custom host, the browser may still attempt to call `localhost` or another unreachable origin.
- Those failures often surface as browser-level CORS or network errors, which look like an application defect even when the real problem is the deployment topology.

This is a poor onboarding contract. Default users should not need to reason about CORS, LAN addressability, or cross-origin API URLs.

## Goals

- Remove browser CORS from the default `make quickstart` path.
- Keep the default quickstart flow working on the same machine with no extra configuration.
- Preserve explicit external API URL support for advanced deployments.
- Fail fast on invalid quickstart or advanced-mode networking combinations.
- Make docs and tests reflect the actual default behavior.

## Non-Goals

- Rework all deployment modes into a single reverse-proxy architecture.
- Remove direct backend access on `localhost:8000` for docs, curl, or advanced operators.
- Replace existing advanced deployment knobs with a new public configuration system.
- Solve every remote-access topology in the default quickstart path.

## Current State

### WebUI

- The frontend API client derives its base URL from `NEXT_PUBLIC_API_URL`.
- The Docker WebUI image bakes `NEXT_PUBLIC_*` values into the client bundle at build time.
- The current quickstart defaults assume `localhost` access.

### API

- The API has CORS middleware enabled by default unless explicitly disabled.
- Non-production runtime already has logic to allow common local and private-LAN origins.
- This helps some local setups, but it does not solve the more important issue: the default quickstart still depends on cross-origin browser traffic.

### Onboarding

- `make quickstart` currently delegates to the Docker WebUI quickstart target.
- Docs describe the quickstart as Docker single-user + WebUI, but the default story still leaves room for hostname mismatch and browser confusion.

## Proposed Design

### 1. Introduce explicit WebUI deployment modes

Add an explicit deployment-mode contract for the WebUI.

Planned modes:

- `quickstart`
  - intended for the default Docker WebUI onboarding path
  - browser uses same-origin API paths
  - WebUI server proxies requests to the internal backend container
- `advanced`
  - intended for reverse proxies, external API hosts, and non-default topologies
  - browser may use an explicit absolute API URL
  - additional validation guards enforce coherent host configuration

The design should not infer behavior from hostnames alone. Deployment mode should be explicit.

### 2. Make quickstart use same-origin browser API requests

In quickstart mode, the browser-facing API base should be relative to the WebUI origin, for example:

- browser requests `/api/v1/...`

This changes the browser contract from:

- WebUI origin `A` calling API origin `B`

to:

- browser calling origin `A`
- WebUI server forwarding to backend origin `B` inside Docker

This is the core change that removes browser CORS from the default path.

### 3. Add a Next.js proxy layer for the default quickstart path

The WebUI server will proxy `/api/:path*` requests to the internal backend service, expected to be reachable inside Docker as:

- `http://app:8000/api/:path*`

Requirements:

- preserve request method, headers, query string, and body
- preserve auth headers used by the current WebUI flows
- preserve streaming behavior for endpoints that use long-lived HTTP responses, including SSE-style flows
- behave transparently for existing browser-side API consumers
- keep backend docs and direct curl access on `localhost:8000` intact

### 4. Make bootstrap and runtime config mode-aware

The current config/bootstrap logic assumes an absolute API host in multiple places. That must become deployment-mode-aware so the quickstart path stays on same-origin proxy mode.

Specific expectations:

- quickstart mode should not overwrite same-origin behavior with stale localhost or saved absolute host values
- advanced mode should continue to allow explicit absolute API hosts
- settings/bootstrap surfaces should distinguish between quickstart default behavior and advanced custom host behavior

### 5. Add fail-fast validation

The system should reject configurations that are known to produce misleading browser failures.

Quickstart mode failure cases:

- same-origin proxy mode selected, but proxy target is missing or invalid
- quickstart build still embeds an absolute browser API host instead of same-origin mode

Advanced mode failure cases:

- browser API URL points at `localhost` or `127.0.0.1`, but the page is being accessed from a non-loopback origin
- other invalid combinations that guarantee the browser cannot reach the configured API origin

Failure behavior:

- fail at startup where possible
- otherwise render a blocking configuration error in the WebUI with specific remediation text
- do not allow the app to degrade into a cascade of request failures that look like CORS defects

## Architecture

### Default quickstart data flow

1. User runs `make quickstart`.
2. Docker starts the API container and the WebUI container in `quickstart` mode.
3. Browser opens `http://localhost:8080`.
4. Frontend calls `/api/v1/...` on the same origin.
5. Next.js server proxies the request to `http://app:8000/api/v1/...`.
6. API responds to the WebUI server.
7. WebUI server returns the response to the browser.

Result:

- the browser performs no cross-origin API request
- browser CORS is not part of the normal quickstart path

### Advanced deployment data flow

1. Operator explicitly selects `advanced` mode.
2. WebUI is configured with an absolute API host.
3. Validation checks deployment mode plus API host coherence.
4. If valid, browser calls the configured absolute API origin.
5. If invalid, startup or the WebUI itself blocks with a targeted configuration error.

## Components

### WebUI deployment-mode config

Responsibilities:

- define quickstart versus advanced behavior
- provide a single source of truth for browser-side API base selection
- keep behavior explicit and testable

### Next.js proxy layer

Responsibilities:

- forward same-origin `/api/:path*` requests to the internal backend service
- preserve request semantics needed by the existing frontend
- support the default Docker quickstart path

### Runtime bootstrap and settings integration

Responsibilities:

- avoid restoring incompatible absolute API hosts in quickstart mode
- keep advanced absolute-host workflows intact
- ensure bootstrap info does not silently override the deployment mode contract

### Fail-fast validation surface

Responsibilities:

- reject invalid quickstart builds or runtime wiring
- reject invalid advanced localhost/non-localhost combinations
- show actionable remediation messages

### Onboarding and docs layer

Responsibilities:

- define the same-origin proxy path as the default quickstart contract
- document LAN/custom-host usage as an advanced path
- keep README, getting-started docs, and website quickstart copy aligned

## Error Handling

### Quickstart proxy failure

If the proxy target is missing, invalid, or unavailable:

- startup should fail where practical
- otherwise the WebUI should report backend unavailability directly
- error text should refer to the quickstart networking contract, not generic CORS advice

### Advanced localhost mismatch

If advanced mode uses a loopback API URL but the page is opened from a non-loopback origin:

- the UI should block
- the message should state that the configured API host is only reachable from the host machine
- remediation should direct the operator to use a reachable LAN/public host or return to quickstart mode

### Backend outages

If the proxied backend is down after startup:

- surface backend unavailability
- do not present CORS troubleshooting as the primary guidance for quickstart users

## Documentation Changes

Update at least:

- `README.md`
- `Docs/Getting_Started/README.md`
- `Docs/Getting_Started/Profile_Docker_Single_User.md`
- `Docs/Website/index.html`
- relevant WebUI README or quickstart text where the default networking story is explained

Documentation must state:

- default quickstart is same-origin from the browser perspective
- browser CORS should not be part of normal default quickstart failures
- LAN or custom-host access is an advanced path with explicit configuration

## Testing Strategy

### Unit tests

- deployment-mode config selection
- API base resolution in quickstart versus advanced mode
- fail-fast validation logic

### Integration tests

- proxy route wiring for same-origin `/api/v1/...` traffic
- streaming proxy behavior for same-origin API flows that rely on SSE-style responses
- WebUI startup in quickstart mode against the Docker backend service contract
- advanced-mode mismatch behavior for localhost API URL plus non-localhost page origin

### Contract and documentation tests

- `make quickstart` remains mapped to the WebUI Docker path
- onboarding manifest still declares the correct default entrypoint
- docs describe same-origin quickstart behavior instead of absolute browser API URLs as the default story

## Rollout Plan

### Stage 1

Introduce explicit deployment modes and proxy-aware API base resolution in the WebUI, with unit coverage.

### Stage 2

Add the Next.js proxy and quickstart Docker wiring so `make quickstart` uses the same-origin path by default.

### Stage 3

Add fail-fast validation for invalid advanced-mode localhost combinations and broken quickstart proxy contracts.

### Stage 4

Update onboarding docs and contract tests so the documented default matches shipped behavior.

## Compatibility

- Existing advanced users with explicit external API URLs should continue to work.
- Direct API access on `localhost:8000` remains available.
- The only default-contract change is that quickstart no longer relies on cross-origin browser API access.

## Risks And Mitigations

### Risk: proxy behavior diverges from direct API calls

Mitigation:

- keep proxy semantics transparent
- add integration coverage for auth headers, request bodies, and common API flows

### Risk: saved browser config overrides quickstart mode

Mitigation:

- make deployment mode the higher-precedence contract
- explicitly ignore incompatible saved hosts in quickstart mode

### Risk: docs and code drift apart again

Mitigation:

- add or extend contract tests around onboarding defaults and quickstart text

## Success Criteria

- Fresh `make quickstart` users can open the WebUI without browser CORS/network confusion.
- Default quickstart does not require `ALLOWED_ORIGINS` edits for same-machine access.
- Invalid LAN/custom-host setups fail with direct configuration guidance rather than generic browser request noise.
- The repo’s default onboarding and tests enforce the same-origin quickstart contract.
