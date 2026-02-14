# M5.1 UX Smoke Warning Hard-Gate Allowlist Policy

Status: Active  
Owner: WebUI + QA + Platform  
Date: February 13, 2026  
Related Files:
- `apps/tldw-frontend/e2e/smoke/smoke.setup.ts`
- `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`
- `.github/workflows/frontend-ux-gates.yml`

## 1) Purpose

Define a strict, auditable policy for console/request warning noise in the WebUI smoke suite so CI can hard-fail on unexpected regressions while tolerating known, time-boxed exceptions.

## 2) Hard-Gate Contract

The smoke suite now classifies warning/error diagnostics into:

1. `allowlisted` (known, route-scoped, time-boxed)
2. `unexpected` (hard-fail)

Hard gate is enabled via:

- `TLDW_SMOKE_HARD_GATE=1`

Enforcement behavior in `all-pages.spec.ts`:

- Any `unexpectedConsoleErrors` => test failure
- Any `unexpectedRequestFailures` => test failure
- `allowlisted*` diagnostics are printed with allowlist rule IDs for visibility and trend review

## 3) Rule Requirements

Every allowlist rule must include:

- Stable `id`
- `scope` (`console` or `request`)
- Narrow `pattern`
- Route scope (`routes`) whenever feasible
- `rationale`
- `owner`
- `expiresOn` date

Rule hygiene constraints:

1. Prefer route-scoped rules over global rules.
2. Prefer specific signatures over generic catch-all patterns.
3. Expiry is mandatory; expired rules must be removed or renewed with fresh evidence.
4. Forced-error fixture noise must be isolated to fixture-target routes only.

## 4) Triaged Warning Classes (Baseline)

Baseline run used for triage:

- Command: `TLDW_SMOKE_HARD_GATE=1 bun run e2e:smoke`
- Result: `165 passed`
- Date: February 13, 2026

Allowlisted classes now tracked:

- Rate-limit noise (`429`, chat history bursts)
- React key-prop spread warning on settings/connectors surfaces
- React `defaultProps` and non-boolean attribute warnings in flashcards path
- `rc-collapse` deprecation warning in quick ingest settings
- Known max-update-depth warning in media/content-review surfaces
- Optional `404` resource misses on selected routes (including wayfinding test-only 404 route)
- Optional admin `500` endpoint misses in minimal backend profile
- Llama.cpp `503` unconfigured backend state
- Forced route-boundary fixture console emissions for route-boundary contract tests

## 5) CI Policy

CI gate coverage:

1. Onboarding gate (`e2e:onboarding`) with evidence artifact upload
2. Broad UX smoke gate (`e2e:smoke`) with hard gate enabled

Both gates are required quality signals for M5 UX governance in PR validation.

## 6) Governance and Review Cadence

1. Weekly review of allowlisted warning counts from smoke logs.
2. Remove stale rules as route/components are remediated.
3. Escalate recurring high-volume warning classes to product backlog if they remain beyond expiry.
4. No new allowlist rule without linked evidence (test output and route context).

## 7) Add/Change Checklist for Future Rules

- [ ] Evidence captured from failing smoke run
- [ ] Rule added with route scope and expiry
- [ ] Rationale includes why warning is non-blocking today
- [ ] Owner assigned
- [ ] Follow-up remediation issue linked in PR or roadmap
