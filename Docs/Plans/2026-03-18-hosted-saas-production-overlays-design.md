# Hosted SaaS Production Overlays Design

**Date:** 2026-03-18
**Scope:** Production deployment path for the hosted SaaS launch profile
**Goal:** Define a production-ready compose path for the first paid hosted deployment that defaults to managed PostgreSQL, uses durable host-mounted storage for application state, and preserves a clearly separated local PostgreSQL fallback path.

## Inputs

- [Hosted SaaS Profile](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_SaaS_Profile.md)
- [Hosted Staging Runbook](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Published/Deployment/Hosted_Staging_Runbook.md)
- [Hosted Staging And Stripe Readiness Implementation Plan](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/2026-03-18-hosted-staging-and-stripe-readiness-implementation-plan.md)
- Existing compose files in [`Dockerfiles/`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Dockerfiles)

## Design Review Corrections

The initial "prod overlay with optional local Postgres" idea was usable but too easy to mis-operate. The reviewed design makes these corrections explicit:

1. The primary production path cannot inherit the local `postgres` service from the current base compose files.
   - [`docker-compose.yml`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Dockerfiles/docker-compose.yml) and [`docker-compose.host-storage.yml`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Dockerfiles/docker-compose.host-storage.yml) both assume a local `postgres` service and app dependency.
   - For paid production, managed PostgreSQL must be the default topology, not a suggestion hidden behind `DATABASE_URL`.

2. Local PostgreSQL fallback must be explicit, not implicit.
   - Operators should opt into local fallback by adding a separate file, not by carrying an always-defined local `postgres` service in the normal prod path.
   - This keeps the main operator story simple and reduces accidental exposure or drift.

3. The production compose path should avoid fragile override semantics where possible.
   - The staging overlay works because the current merge behavior is favorable, but production should not rely on subtle list replacement behavior for core safety properties.
   - The reviewed design uses a standalone hosted production compose file plus a narrow fallback overlay.

4. Durable storage boundaries must be exact.
   - The production runbook needs explicit host mount paths for app databases, per-user data, Redis state, and fallback local Postgres state.
   - Backup and restore instructions must align with those exact paths.

5. Production should use a production-labeled reverse-proxy sample.
   - The current hosted Caddy sample is staging-branded.
   - A production sample avoids copy-paste mistakes and makes the public-host contract clearer.

6. Production verification should remain non-mutating.
   - Checkout, portal, and webhook behavioral proof stays in staging.
   - Production gating should rely on validator checks, rendered compose config, route preflight, and smoke-safe reachability checks.

## Recommended Approach

Use a two-file production deployment model:

1. `Dockerfiles/docker-compose.hosted-saas-prod.yml`
   - standalone primary production compose file
   - same-origin public topology
   - `app`, `webui`, `redis`, and `caddy`
   - no local `postgres` service in the default path
   - durable host-mounted storage for app and Redis data
   - managed PostgreSQL required through `DATABASE_URL`

2. `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
   - optional emergency fallback overlay
   - adds an internal-only `postgres` service
   - extends `app.depends_on` to include local `postgres`
   - mounts a dedicated host path for fallback database state
   - is documented as temporary recovery posture, not the paid-production default

This preserves the user-requested fallback behavior while preventing staging assumptions from bleeding into the default production topology.

## Production Topology

### Default production path

- Public entrypoint is `https://app.example.com`.
- `caddy` is the only service bound to `80/443`.
- `webui` and `app` remain internal on the compose network.
- `redis` remains internal to the app node.
- `DATABASE_URL` points to managed PostgreSQL using a provider private hostname or private network endpoint.
- Durable app state is stored on host-mounted storage, not Docker named volumes.

### Fallback local PostgreSQL path

- Activated only by adding `-f Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`.
- `postgres` stays internal-only and is never publicly bound.
- `DATABASE_URL` is switched to the local service only for emergency or temporary recovery use.
- The runbook must state that operators should revert back to managed PostgreSQL once the incident is resolved.

## Required Deliverables

### 1. Production compose files

Add:

- `Dockerfiles/docker-compose.hosted-saas-prod.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`

The primary file must:

- define `app`, `webui`, `redis`, and `caddy`
- require hosted SaaS envs that match the hosted profile
- publish only `80/443`
- use host bind mounts for:
  - `/app/Databases`
  - `/app/Databases/user_databases`
  - `/data` for Redis

The fallback file must:

- add `postgres`
- keep `postgres` internal-only
- add host bind mount for `/var/lib/postgresql/data`
- extend `app.depends_on` for local fallback mode

### 2. Production env template

Add `tldw_Server_API/Config_Files/.env.hosted-production.example`.

It should:

- satisfy the hosted profile contract
- default `PUBLIC_WEB_BASE_URL` and frontend URLs to `https://app.example.com`
- use a managed PostgreSQL DSN placeholder with TLS enabled
- include host-storage env vars such as:
  - `TLDW_APP_DATA_DIR`
  - `TLDW_USER_DATA_DIR`
  - `TLDW_REDIS_DATA_DIR`
  - `TLDW_POSTGRES_DATA_DIR` for fallback mode
- clearly separate test-mode examples from live-production values for Stripe and SMTP

### 3. Production reverse-proxy sample

Add `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`.

It should:

- route `/api/*`, `/health`, and `/ready` to `app`
- route all other public traffic to `webui`
- use a production placeholder hostname
- keep the current baseline hardening headers

### 4. Production runbook

Add `Docs/Published/Deployment/Hosted_Production_Runbook.md`.

It should document:

- region, VPC, firewall, and DNS assumptions
- exact host mount layout under `/srv/tldw-data`
- how to use the primary prod compose file
- how to opt into fallback local Postgres
- pre-cutover validation commands
- non-goals and rollback posture

### 5. Tests and verification

Add a narrow test surface:

- YAML contract tests for the primary prod file
- YAML contract tests for the fallback overlay
- env template alignment tests or validator coverage
- rendered compose verification for:
  - primary prod file
  - primary prod file plus fallback overlay

## Storage Contract

Standardize the host layout as:

- `/srv/tldw-data/app`
- `/srv/tldw-data/user_data`
- `/srv/tldw-data/redis`
- `/srv/tldw-data/postgres` only for fallback mode
- `/srv/tldw-data/backups`

These paths must map cleanly to the existing runtime expectations and the current backup/restore runbooks.

## Verification Strategy

### Default production path

Before the environment is considered production-ready:

```bash
source .venv/bin/activate
python Helper_Scripts/validate_hosted_saas_profile.py --env-file tldw_Server_API/Config_Files/.env.hosted-production.example
python Helper_Scripts/Deployment/hosted_staging_preflight.py --env-file tldw_Server_API/Config_Files/.env.hosted-production.example --base-url https://app.example.com --strict
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml config
```

### Fallback local PostgreSQL path

For the fallback composition:

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml -f Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml config
```

### Explicit non-goals

- live checkout mutation tests in production
- automated billing state changes against live Stripe during deploy validation
- a storage backend re-architecture
- multi-node production orchestration

## Risks And Mitigations

1. Operators may still confuse staging and production compose paths.
   - Mitigation: use separate prod filenames, a prod-specific Caddy sample, and explicit published runbooks.

2. Host-mounted storage may drift from backup scope.
   - Mitigation: document exact mount paths and reuse them in backup guidance.

3. Fallback local Postgres may become semi-permanent.
   - Mitigation: document fallback as emergency-only, keep it in a separate file, and require explicit rollback to managed PostgreSQL in the runbook.

4. Production checks could become too invasive.
   - Mitigation: keep prod verification non-mutating and reserve billing-flow proof for staging.

## Success Condition

After implementation, the repo should contain one clear production deployment path for hosted SaaS:

- managed PostgreSQL by default
- durable host-mounted storage for application state
- only the reverse proxy publicly exposed
- a documented and testable emergency local PostgreSQL fallback path
- production docs and env templates that match the actual compose topology
