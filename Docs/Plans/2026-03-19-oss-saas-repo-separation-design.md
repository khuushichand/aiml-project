# OSS And SaaS Repo Separation Design

**Date:** 2026-03-19
**Scope:** Split hosted/commercial material out of the public `tldw_server` repo into a separate private repo.
**Goal:** Define a durable repository boundary so the open-source project remains coherent and self-host focused while all hosted SaaS documentation, deployment overlays, billing/customer-surface code, and commercial operating material live in a private repo.

## Inputs

- [Docs Site Guide](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Code_Documentation/Docs_Site_Guide.md)
- [MkDocs config](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/mkdocs.yml)
- [Curated docs refresh script](/Users/macbook-dev/Documents/GitHub/tldw_server2/Helper_Scripts/refresh_docs_published.sh)
- [Hosted SaaS Profile](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_SaaS_Profile.md)
- [Hosted Staging Runbook](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_Staging_Runbook.md)
- [Hosted Production Runbook](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_Production_Runbook.md)
- Hosted deployment overlays in [`Dockerfiles/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Dockerfiles)
- Hosted frontend/account/billing surface in [`apps/tldw-frontend/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend)

## Current Problem

The repo currently mixes three different concerns:

1. Open-source product and self-host docs.
2. Hosted SaaS operational documentation and deployment assets.
3. Commercial launch planning and hosted customer-surface code.

That mixture is already leaking into the public docs surface:

- `Docs/mkdocs.yml` publishes from `Docs/Published`.
- `Helper_Scripts/refresh_docs_published.sh` curates public content by copying selected folders into `Docs/Published`.
- Hosted SaaS runbooks currently live under `Docs/Published/Deployment`, which makes them part of the public site contract.
- Public docs and tests now reference hosted SaaS files directly.

If this continues, the public repo will stop being a clean self-host/open-source project and will instead become the operating handbook for the commercial hosted service.

## Recommended Repository Model

Use a two-repo model:

1. `tldw_server`
   - public OSS repo
   - source of truth for the product core
   - self-host and developer documentation only

2. `tldw-hosted`
   - private commercial overlay repo
   - source of truth for hosted customer-surface code, billing integration, hosted deployment overlays, internal ops runbooks, launch plans, and SaaS release gates

The private repo should depend on the public repo, not the reverse.

## Why A Private Overlay Repo Instead Of A Private Fork

A long-lived private fork would be easy at first but would keep encouraging hosted-only work to land in the same tree as OSS core. That makes it harder to decide what belongs public versus private and increases accidental leakage risk.

The better model is:

- public repo stays clean and self-contained
- private repo pins a known revision of the public repo
- hosted/commercial layers are added on top in the private repo

This makes the boundary structural rather than social.

## Boundary Definition

### Keep public in `tldw_server`

These belong in the OSS repo:

- Core FastAPI backend and generic frontend capabilities
- Generic AuthNZ, org, team, user, and tenancy primitives
- Generic multi-user support
- Self-host deployment docs
- Public API docs and developer docs
- Generic operations guidance for self-hosters
- Generic tests that validate product behavior independent of the hosted service

### Move private to `tldw-hosted`

These belong in the private repo:

- Hosted login/signup/account/billing flows in the web frontend
- Hosted route allowlisting and customer-surface gating
- Stripe integration, plan logic, checkout flows, portal flows, invoice/customer flows
- Hosted deployment overlays:
  - `Dockerfiles/docker-compose.hosted-saas-staging.yml`
  - `Dockerfiles/docker-compose.hosted-saas-prod.yml`
  - `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
- Hosted env templates and hosted Caddy samples
- Hosted staging/prod smoke and preflight flows
- Internal runbooks and support/ops documentation
- SaaS launch plans, pricing/packaging notes, and internal readiness documents

### Refactor mixed areas before or during extraction

These are not safe to leave as-is:

- Public docs that reference hosted SaaS runbooks as canonical
- Public tests that assert hosted/private docs or overlays exist
- Public README/docs that position hosted deployment as the main path
- Hosted-mode code that is intertwined with OSS defaults rather than isolated behind a private overlay or integration seam

## Repo Interaction Model

The private repo should import the public repo as a pinned dependency, not maintain a drifting private fork.

Recommended practical model:

- create private repo `tldw-hosted`
- include the public repo as `upstream/tldw_server` or similar
- keep hosted-only code, docs, overlays, CI/CD, and operational assets in the private repo root
- update the pinned public revision deliberately as part of hosted release work

This model makes it clear which changes are upstream-worthy and which are commercial-only.

## Migration Plan

The split should happen in phases.

### Phase 1: Freeze the boundary

Immediately stop adding new hosted-only material to:

- `Docs/Published`
- `Docs/Operations`
- `Docs/Plans`
- public deployment overlays and hosted env templates

Add a simple boundary rule: no public docs, tests, or CI may require private hosted artifacts.

### Phase 2: Extract private documentation first

Move the highest-risk material out first:

- hosted runbooks
- hosted env contracts
- hosted ops guides
- hosted launch plans/designs/reviews
- pricing/packaging notes

Then scrub public docs so they no longer reference those files.

### Phase 3: Extract hosted deployment/config/test layers

Move:

- hosted compose overlays
- hosted reverse-proxy samples
- hosted preflight/smoke scripts
- hosted-only verification tests

Replace public references with self-host-safe guidance or remove them entirely.

### Phase 4: Extract hosted customer-surface code

Move the hosted web layer out of the public repo:

- hosted auth/customer funnel
- hosted billing surface
- hosted route gating
- any hosted-only API proxy/session assumptions

This is the hardest phase because it touches actual app behavior, not just docs.

### Phase 5: Stabilize the public repo

After extraction, the public repo must still:

- build successfully
- pass tests without private artifacts
- build and deploy the public docs site
- read as a coherent OSS/self-host project

## Governance Rules

Use this rule for future work:

- `Public` if it improves the OSS/self-host product without exposing the hosted operating model.
- `Private` if it affects how the hosted service is sold, provisioned, billed, gated, operated, supported, or differentiated.

Concrete guidance:

- Public: core APIs, auth primitives, generic org/team abstractions, self-host deployment patterns, generic admin capabilities.
- Private: Stripe integration, pricing logic, hosted signup funnel, customer account/billing pages, hosted deployment overlays, internal runbooks, support procedures, launch plans, and release gates.

When in doubt, default to private first and upstream only the generic mechanism later.

## Implementation Guardrails

To keep the split durable:

1. Public docs must not describe hosted SaaS as the canonical deployment path.
2. Public docs build must not publish hosted-only pages.
3. Public tests and CI must not assert the existence of hosted/private files.
4. Hosted/private files should move to their own repo rather than being hidden in the public repo.
5. The private repo should carry the hosted/commercial release logic, not the OSS repo.

## Initial Files Likely To Move Private

This is the current first-pass extraction set:

- [Hosted_SaaS_Profile.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_SaaS_Profile.md)
- [Hosted_Staging_Runbook.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_Staging_Runbook.md)
- [Hosted_Production_Runbook.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_Production_Runbook.md)
- [Hosted_Staging_Operations_Runbook.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Operations/Hosted_Staging_Operations_Runbook.md)
- [Hosted_Stripe_Test_Mode_Runbook.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md)
- hosted SaaS plan docs under [`Docs/Plans/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans)
- hosted compose/env/Caddy assets in [`Dockerfiles/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Dockerfiles), [`Helper_Scripts/Samples/Caddy/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Helper_Scripts/Samples/Caddy), and [`tldw_Server_API/Config_Files/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files)
- hosted customer-surface and billing code in [`apps/tldw-frontend/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend)

## Success Condition

The separation is successful when:

- the public repo can be published and maintained without exposing hosted commercial operations
- the private repo contains everything needed to run and evolve the hosted service
- self-host users can still understand and deploy the OSS product without hosted-only references
- future hosted work defaults to the private repo by structure, not by convention alone
