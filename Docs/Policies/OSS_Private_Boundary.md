# OSS And Private SaaS Boundary Policy

This policy defines what belongs in the public `tldw_server` repo versus the private hosted SaaS repo.

## Public

Keep work in the public repo when it improves the open-source or self-host product without exposing the hosted operating model.

Examples:

- Core APIs and backend behavior
- Generic auth, org, team, and tenancy primitives
- Generic multi-user support
- Self-host deployment guides
- Public developer and API docs
- Generic admin and operational capabilities useful to self-hosters
- Generic tests that do not depend on hosted-only artifacts

## Private

Move work to the private hosted repo when it affects how the hosted service is sold, provisioned, billed, gated, operated, supported, or differentiated.

Examples:

- Hosted login, signup, account, and billing flows
- Stripe integration, plans, checkout, portal, invoices, and commercial entitlements
- Hosted route allowlisting and customer-surface gating
- Hosted deployment overlays, env contracts, and reverse-proxy samples
- Hosted staging and production runbooks
- Internal support, incident, and revenue operations guidance
- SaaS launch plans, pricing notes, and commercial release gates

## Public Docs Rule

Hosted commercial documentation does not belong in public `Docs/Published`.

Public docs should remain focused on:

- self-host setup
- OSS developer guidance
- public API and architecture references
- generic operations guidance that does not reveal hosted service internals

## Public CI And Tests Rule

Public CI, tests, docs, and release checks must not depend on private artifacts.

That means:

- no public tests may require hosted-private runbooks or deploy files to exist
- no public docs build may publish hosted-only pages
- no public guidance may point to private hosted material as the canonical path

## Default Decision Rule

When a change is ambiguous:

1. Keep the generic mechanism public if it is broadly useful to self-hosters or contributors.
2. Keep the hosted policy, packaging, operational playbook, and commercial wiring private.
3. If still unclear, default to private first and upstream only the reusable core later.
