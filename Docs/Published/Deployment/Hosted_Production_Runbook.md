# Hosted Production Runbook

Version: v0.1.0
Audience: operators cutting over the first paid hosted SaaS deployment

This runbook is the canonical production path for the hosted SaaS launch profile. It is intentionally narrower than the staging runbook: production validation should prove the stable topology, not repeat the Stripe billing mutation checks that belong in staging.

Related documents
- Hosted SaaS profile: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Hosted staging runbook: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Hosted Stripe test-mode runbook: `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Hosted staging operations runbook: `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- Production Caddy sample: `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`

## 1) Prepare the production env file

Copy the shape-only example file before launch:

```bash
cp tldw_Server_API/Config_Files/.env.hosted-production.example tldw_Server_API/Config_Files/.env.hosted-production
```

Replace every placeholder secret and provider-specific value before running validation or `docker compose`.

Use `tldw_Server_API/Config_Files/.env.hosted-production` in all commands below. Do not deploy directly from the `.example` file.

## 2) Production topology

Use the standalone hosted production compose file as the default path:

```bash
docker compose \
  --env-file tldw_Server_API/Config_Files/.env.hosted-production \
  -f Dockerfiles/docker-compose.hosted-saas-prod.yml \
  up -d --build
```

If you need the emergency local PostgreSQL fallback, add the overlay explicitly:

```bash
docker compose \
  --env-file tldw_Server_API/Config_Files/.env.hosted-production \
  -f Dockerfiles/docker-compose.hosted-saas-prod.yml \
  -f Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml \
  up -d --build
```

The default production path assumes:

- same-origin public entrypoint on `https://app.example.com`
- `caddy` is the only public service
- `app`, `webui`, and `redis` stay internal to the compose network
- managed PostgreSQL is provided through `DATABASE_URL`
- durable application state lives on host-mounted storage under `/srv/tldw-data`

## 3) Region and network

Use one region for the app node, managed PostgreSQL, and host volume:

- region: a single US region such as `SFO3` or `NYC3`
- VPC: one private VPC for app-to-database traffic
- firewall: only `80`, `443`, and restricted `22` should reach the VPS
- DNS: `app.example.com` should point at the public host or reserved IP

Do not expose the internal `app`, `redis`, or fallback `postgres` services directly.

## 4) Storage layout

Use the following host paths:

- `/srv/tldw-data/app`
- `/srv/tldw-data/user_data`
- `/srv/tldw-data/redis`
- `/srv/tldw-data/postgres` only when using the local-postgres fallback overlay
- `/srv/tldw-data/backups`

Map them to the container paths used by the compose files:

- `/srv/tldw-data/app` -> `/app/Databases`
- `/srv/tldw-data/user_data` -> `/app/Databases/user_databases`
- `/srv/tldw-data/redis` -> `/data`
- `/srv/tldw-data/postgres` -> `/var/lib/postgresql/data`

Backups and restore drills must use those same paths. Do not invent an alternate mount layout during incident response.

## 5) Environment contract

Start from `tldw_Server_API/Config_Files/.env.hosted-production.example`, copy it to `tldw_Server_API/Config_Files/.env.hosted-production`, and replace every placeholder before launch.

Required values:

- `AUTH_MODE=multi_user`
- `tldw_production=true`
- `PUBLIC_WEB_BASE_URL=https://app.example.com`
- `ALLOWED_ORIGINS=https://app.example.com`
- `BILLING_REDIRECT_ALLOWLIST_REQUIRED=true`
- `BILLING_REDIRECT_REQUIRE_HTTPS=true`
- `BILLING_ALLOWED_REDIRECT_HOSTS=app.example.com`
- `DATABASE_URL=postgresql://...` pointing to managed PostgreSQL
- `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET`
- SMTP credentials for verification, reset, and magic-link mail

When using the fallback overlay, set `POSTGRES_PASSWORD` explicitly. The fallback database must never boot with a default password.

## 6) Validation sequence

Run these checks before cutover:

```bash
source .venv/bin/activate
python Helper_Scripts/validate_hosted_saas_profile.py --env-file tldw_Server_API/Config_Files/.env.hosted-production
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production -f Dockerfiles/docker-compose.hosted-saas-prod.yml config
python Helper_Scripts/Deployment/hosted_staging_preflight.py --env-file tldw_Server_API/Config_Files/.env.hosted-production --base-url https://app.example.com --strict
```

The production validation gate should confirm:

- the env contract passes
- the standalone prod compose renders cleanly
- the public host serves `/health`, `/ready`, `/login`, `/signup`, and `/api/v1/billing/plans`

## 7) Optional fallback recovery drill

The local-Postgres overlay is an emergency path, not part of the default production cutover checklist.

Run this only when you are intentionally rehearsing or activating the fallback path:

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production -f Dockerfiles/docker-compose.hosted-saas-prod.yml -f Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml config
```

## 8) Billing and Stripe

Stripe live-mode verification belongs in staging, not in production cutover validation.

For production:

- confirm the billing redirect allowlist still targets the public app host
- confirm checkout, portal, and webhook settings were already proven in staging
- do not add new live-payment mutation checks to the production cutover checklist

If billing state looks stale after cutover, inspect webhook delivery and app logs before changing configuration.

## 9) Backup and rollback

For managed PostgreSQL:

- rely on provider snapshots and point-in-time recovery
- verify a recent successful snapshot before cutover

For durable application data:

- back up `/srv/tldw-data/app`, `/srv/tldw-data/user_data`, and `/srv/tldw-data/redis`
- back up `/srv/tldw-data/postgres` only when using the local fallback overlay

Rollback order:

1. confirm whether the issue is app, proxy, Redis, or database related
2. prefer reverting to the previous deployment before editing data
3. if managed PostgreSQL is healthy, keep the primary prod path and avoid switching to fallback unless necessary
4. if local fallback was used, treat it as temporary recovery and schedule a return to managed PostgreSQL

## 10) What this runbook does not promise

- live Stripe proof during production cutover
- team invites or seat management
- SSO
- a storage backend re-architecture
- multi-node orchestration

Use this runbook together with the staging runbook and the hosted SaaS profile. If a deployment needs to violate the topology above, it is no longer the launch profile.
