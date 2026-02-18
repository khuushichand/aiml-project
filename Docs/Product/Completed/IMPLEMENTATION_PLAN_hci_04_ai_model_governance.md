# Implementation Plan: HCI Review - AI & Model Governance

## Scope

Pages: `app/providers/`, `app/resource-governor/`, `app/voice-commands/`
Finding IDs: `4.1` through `4.7`

## Finding Coverage

- `4.1` (Critical): No per-model usage or cost breakdown on providers page
- `4.2` (Important): No model deprecation or sunset warnings
- `4.3` (Important): Resource Governor has no policy simulation/preview
- `4.4` (Important): No rate limit hit monitoring
- `4.5` (Important): Resource Governor scope resolution unclear
- `4.6` (Nice-to-Have): Voice commands lack test/dry-run capability
- `4.7` (Nice-to-Have): No token usage trending or forecast on providers page

## Key Files

- `admin-ui/app/providers/page.tsx` -- 3-tab layout: Providers list, User BYOK, Org BYOK
- `admin-ui/app/resource-governor/page.tsx` -- Policy CRUD with scope/resource type/rate limits
- `admin-ui/app/voice-commands/page.tsx` -- Voice command list with analytics
- `admin-ui/app/voice-commands/[id]/page.tsx` -- Voice command detail + usage stats
- `admin-ui/lib/api-client.ts` -- Provider overrides, policy CRUD, voice command CRUD

## Stage 1: Per-Model Usage and Cost on Providers Page

**Goal**: Show admins which models are actually being used, how much they cost, and at what error rates.
**Success Criteria**:
- Providers table adds columns: Requests (7d), Tokens (7d), Cost (7d $), Error Rate (%).
- Data sourced from `/admin/llm-usage/summary?group_by=provider` endpoint.
- Each provider row expandable to show per-model breakdown within that provider.
- Per-model rows show: model name, request count, input/output tokens, cost, avg latency.
- "View full usage" link on each provider navigates to `/usage` page pre-filtered to that provider.
- Graceful fallback if usage data unavailable (show "—" not broken layout).
**Tests**:
- Unit test for provider row expansion with per-model data.
- Unit test for cost/token formatting (K, M suffixes for large numbers).
- Unit test for fallback when usage endpoint fails.
**Status**: Complete

## Stage 2: Resource Governor Policy Simulation + Scope Resolution

**Goal**: Let admins understand policy impact before applying and see which policy applies to any given request.
**Success Criteria**:
- "Simulate" button on policy form: shows "Would affect X users / Y requests in last 24h" before saving.
- Simulation data sourced from a dry-run endpoint or client-side estimation from usage data.
- New "Policy Resolution" tool: enter a user ID + resource type → shows which policy applies and why (priority, scope match).
- Policy resolution explains the evaluation chain: "Global policy 'Default LLM' (priority 1) → User policy 'Power User' (priority 10) → **Winner: Power User**".
- Policy table adds "Affected Users" column showing count of users matched by each policy's scope.
**Tests**:
- Unit test for simulation result display.
- Unit test for policy resolution chain rendering.
- Unit test for affected users count display.
**Status**: Complete

## Stage 3: Model Deprecation Warnings + Rate Limit Monitoring

**Goal**: Proactively warn admins about deprecated models and show rate limit enforcement data.
**Success Criteria**:
- Providers page flags deprecated models with orange "Deprecated" badge.
- Deprecated model list maintained as a client-side config (e.g., `gpt-3.5-turbo`, `claude-2`, etc.) updated periodically.
- Clicking deprecated badge shows: "This model is deprecated. X requests used it in the last 7 days. Consider migrating to [alternative]."
- Resource Governor page adds "Rate Limit Events" section showing: user/role, policy, rejection count (24h), last rejection timestamp.
- Data sourced from `/metrics/text` Prometheus counters or a dedicated rate-limit events endpoint.
**Tests**:
- Unit test for deprecated model badge rendering and info popover.
- Unit test for rate limit events table rendering.
- Snapshot test for deprecated model list configuration.
**Status**: Complete

## Stage 4: Voice Command Testing + Usage Trending

**Goal**: Complete the remaining Nice-to-Have findings.
**Success Criteria**:
- Voice command detail page has "Test Command" button: enter sample text → shows whether it would match this command's trigger phrases, with confidence score.
- Test uses client-side fuzzy matching against trigger phrases (no backend required).
- Providers page header includes mini sparkline charts showing 7-day token usage trend per provider.
- Sparklines sourced from `/admin/llm-usage/summary?group_by=provider&group_by=day`.
**Tests**:
- Unit test for voice command phrase matching logic.
- Unit test for sparkline chart rendering with trend data.
**Status**: Complete

## Dependencies

- Stage 1 relies on existing `/admin/llm-usage/summary` with `group_by` support.
- Stage 2 simulation may require a new backend endpoint `POST /resource-governor/policy/simulate` or can be approximated client-side from usage data.
- Stage 3 deprecated model list is client-side; no backend dependency. Rate limit events use `/admin/rate-limit-events` when available with `/metrics/text` parsing as fallback.
- Stage 4 voice command testing is entirely client-side (phrase matching).
