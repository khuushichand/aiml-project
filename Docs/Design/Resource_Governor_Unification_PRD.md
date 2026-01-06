# Resource Governor Unification PRD

## Summary
Unify all rate limiting under Resource Governor (RG) and remove legacy limiters
(legacy ingress limiter, AuthNZ DB/Redis limiter, chat token buckets, embeddings
limiter, and Rate_Limit utilities). RG becomes the single source of truth for
request, token, stream, and job limits, and standardizes 429 responses plus
rate-limit headers.

## Goals
- RG is the only limiter used in production for requests, tokens, streams, and jobs.
- Consistent 429 responses and rate-limit headers across all endpoints.
- Policy-driven limits via RG route_map and policy store (file or DB).
- Reduce per-module config knobs by mapping defaults to RG policies.
- Preserve test determinism with RG test bypass and stub settings.

## Non-Goals
- New UI for rate limit management.
- Changes to billing or quota semantics beyond moving enforcement to RG.
- Adding new limit categories unrelated to existing RG capabilities.

## Background / Problem
Rate limiting was implemented in multiple places (legacy ingress limiter, AuthNZ
RateLimiter, chat token buckets, embeddings limiter, and legacy helpers). This
creates duplicated config, inconsistent 429 behavior, and hard-to-test edge
cases. RG already provides a policy-driven, centralized limiter but is not the
only enforcement path.

## Scope
- Replace legacy ingress decorators with RG ingress enforcement.
- Replace chat/embeddings/audio rate limiters with RG token/stream enforcement.
- Remove legacy modules after migration.
- Standardize headers and 429 payloads via RG middleware and endpoint helpers.

### Explicit Deletions (post-migration)
- tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py
- tldw_Server_API/app/core/RateLimiting/Rate_Limit.py
- tldw_Server_API/app/core/AuthNZ/rate_limiter.py
- tldw_Server_API/app/core/Chat/rate_limiter.py
- tldw_Server_API/app/core/Embeddings/rate_limiter.py
- Inline TokenBucketLimiter in Embeddings_Create

## Functional Requirements
1. Ingress requests:
   - RG middleware enforces request limits for all API routes.
   - Route_map covers all relevant endpoints by tag and/or path.
   - 429 responses include Retry-After and X-RateLimit-* headers.

2. Tokens:
   - Chat and embeddings endpoints reserve and commit tokens through RG.
   - Token reservations include per-user and per-conversation scopes where needed.

3. Streams:
   - Audio streaming endpoints reserve and commit stream slots through RG.
   - Standard close codes and 429 behavior stay aligned with RG policies.

4. Jobs / minutes:
   - Workflows and long-running tasks use RG job/minute caps where defined.

5. Error and header contract:
   - Success responses include X-RateLimit-* (requests category) where applicable.
   - Deny responses include Retry-After and standard error payloads.

## Policy Model
- Policies stored in RG policy store (file or DB).
- route_map entries for all API tags/paths (chat, audio, embeddings, media,
  workflows, tools, auth, mcp, etc.).
- Scopes: global, user, api_key, conversation (where applicable).

## Migration / Compatibility
- Maintain RG shadow metrics during migration to validate parity.
- Keep RG_ENABLED as a feature flag for rollout.
- Map legacy per-route limits to policy defaults before removing config knobs.

## Observability
- Emit RG decision metrics with clear policy_id and scope labels.
- Track 429 counts and retry_after histograms by policy_id.

## Testing
- Middleware tests: request caps, headers, retry_after behavior.
- Integration tests: chat, embeddings, audio, workflows receive consistent 429s.
- Token/stream enforcement tests for RG reservations.
- Regression tests for 429 payload shape and header presence.

## Rollout
- Phase 1: Route_map coverage and RG ingress for requests.
- Phase 2: RG tokens and streams; disable legacy limiters.
- Phase 3: Remove legacy modules and config keys; update docs/tests.

## Risks
- Behavior drift for test suites expecting legacy ingress limiter or legacy limiters.
- Policy gaps causing fail-closed 429s; mitigate via route_map audit.

## Open Questions
- Which entity should auth endpoints use (IP vs user vs api_key) when
  no user context exists?
- Do any background workers need RG-based limits outside HTTP ingress?
