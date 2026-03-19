# SaaS Readiness Review Design

**Date:** 2026-03-18
**Status:** Approved

## Goal

Define a concrete review method for assessing how ready `tldw_server`, `apps/tldw-frontend`, and the internal-only `admin-ui` are for a first self-serve SaaS launch.

The review is not a generic production audit. It is intended to answer a narrower business question:

> What are the immediate and short-term steps required to offer a hosted `tldw` product to paying customers safely, starting with self-serve single-user subscriptions, then expanding to teams, then B2B?

## Launch Target

The target launch shape for this review is:

- Hosted SaaS, not self-host-only guidance
- Self-serve signup first
- Single-user paid subscriptions first
- Flat subscription tiers with usage-based overages, add-ons, or raised limits
- Narrow core customer offering rather than the full current product surface
- `admin-ui` remains internal-only
- Teams and B2B are later phases, not first-launch requirements

## Product Boundary

The first paid launch should be judged against a constrained core offer rather than the entire current platform. The likely initial customer-facing surface is:

- signup and login
- onboarding and first-value path
- media ingest
- chat
- search and RAG
- quota visibility
- upgrade and billing surfaces tied to that core offer

The review should treat advanced or specialist modules as explicitly out of scope for launch unless they are required by the core paid offering.

## Chosen Review Approach

Three assessment approaches were considered:

1. Infrastructure-first readiness review
2. Product-first launch review
3. Launch-path gap analysis

The chosen approach is `launch-path gap analysis`.

Reasoning:

- The core question is not whether the system can run in production in the abstract.
- The core question is whether the existing stack can be turned into a credible first paid SaaS offering.
- The review therefore needs to begin from the actual launch motion and translate findings into immediate blockers, short-term work, and later work.

## Readiness Standard

This review should use a practical first-paid-customers threshold, not an enterprise-complete threshold.

The stack is considered ready enough for first self-serve paid launch only if all of the following are true:

- A new user can discover the product, create an account, select a plan or trial, pay, and reach the core product without operator intervention.
- Billing state controls product entitlements and overage behavior in a predictable way.
- User data isolation and account/session handling are trustworthy enough for hosted customer use.
- The internal team can support normal customer issues through `admin-ui`, logs, metrics, and documented operational procedures.
- Production deployment has credible controls for secrets, backups, monitoring, webhook handling, and incident recovery.

The review may explicitly allow some manual operations at launch:

- refunds and billing exceptions
- manual fraud review
- manual enterprise provisioning
- selected support workflows handled internally through `admin-ui`

The review must not allow the following to remain unresolved:

- broken self-serve signup or payment flow
- missing or weak entitlement enforcement
- unreliable billing webhook reconciliation
- weak user or tenant isolation
- unsupportable production deployment posture

## Assessment Framework

The review should score the current system across five launch-critical tracks.

### 1. Customer Product Surface

Assess whether the public WebUI can be reduced to a coherent, sellable v1 experience:

- signup and login
- onboarding and first value
- ingest
- chat
- search and RAG
- account basics
- quota visibility
- upgrade prompts and plan awareness

The key question is whether the customer-facing experience is understandable and commercially coherent, not whether many features exist.

### 2. Billing And Monetization

Assess whether the current billing layer can support self-serve conversion and ongoing paid usage:

- public plans
- checkout
- subscription lifecycle
- customer portal behavior
- invoices
- entitlements
- usage accounting
- overage, add-on, or raised-limit mechanics
- cancellation, downgrade, and recovery behavior
- webhook reliability and reconciliation

### 3. Identity, Tenancy, And Data Isolation

Assess whether the hosted product can safely operate with real customer accounts:

- registration and login
- session handling
- account recovery
- org and user ownership boundaries
- role and permission handling
- API credential handling
- tenant and data isolation
- forward compatibility with later team support

### 4. Operations And Internal Admin Readiness

Assess whether `admin-ui` is sufficient as an internal control plane for:

- support workflows
- billing exceptions
- user/account interventions
- organization visibility
- monitoring and incident response
- auditability
- revenue-operations basics

### 5. Deployment, Compliance, And Supportability

Assess the minimum viable production and business posture for selling to customers:

- deploy model
- secret management
- TLS and public exposure assumptions
- backups and restore confidence
- monitoring and alerting
- logs and operational diagnostics
- rate limits and abuse controls
- data export and deletion support
- baseline legal/compliance readiness for early SaaS sales

## Review Method

The readiness review should run in four passes.

### Pass 1. Surface Mapping

Map the actual launch path across:

- `apps/tldw-frontend`
- `tldw_Server_API`
- internal `admin-ui`

Focus on the real path for:

- self-serve signup and login
- account creation and account state
- plan selection and checkout
- entitlement-controlled product access
- core user journeys
- internal support and override flows

### Pass 2. Capability Audit

For each launch-critical area, verify whether the repo already provides:

- implemented code paths
- tests that cover the behavior
- deployment or operational documentation
- production controls
- obvious gaps, placeholders, or stubs

### Pass 3. Readiness Scoring

Each area should be scored against these questions:

- Does it exist?
- Does it work end-to-end?
- Is it safe for customer use?
- Is it supportable in production?
- Can it scale to teams later without a major rewrite?

The resulting rating should be:

- `Green`: credible for first paid launch
- `Yellow`: usable with explicit constraints or manual operations
- `Red`: blocking gap

### Pass 4. Launch Sequencing

Translate findings into three execution buckets:

- `Immediate`: must be done before charging customers
- `Short-term`: should be done in the first 30-60 days
- `Later`: needed for teams or B2B, but not required for the first self-serve release

## Evidence Sources

The review should be grounded in the current repo, especially:

- `admin-ui/`
- `apps/tldw-frontend/`
- `tldw_Server_API/app/api/v1/endpoints/auth.py`
- `tldw_Server_API/app/api/v1/endpoints/billing.py`
- backend tests for AuthNZ, billing, orgs, and tenant isolation
- `README.md`
- `Docs/Published/Deployment/First_Time_Production_Setup.md`
- production hardening and deployment guides
- admin and frontend release or audit docs already present in the repo

## Deliverable Shape

The actual readiness review produced from this design should include:

- current readiness verdict
- top blockers
- immediate launch checklist
- short-term roadmap for post-launch hardening and productization
- later roadmap items for teams and B2B
- explicit decisions on what can stay manual at first versus what must be automated before launch

## Success Condition

After running the review, the team should be able to make one of two concrete calls:

1. `We can launch an early self-serve paid offering with these constraints and this immediate checklist.`
2. `We are not ready to charge customers yet, and these are the exact blocking gaps in priority order.`

## Next Step

The next step after this approved design is to create an implementation plan for the actual readiness review work:

- which repo surfaces to inspect first
- what evidence to capture
- how to structure the scoring output
- how to convert findings into immediate and short-term launch actions
