# Hosted Staging Runbook

Version: v0.1.0
Audience: operators standing up the first hosted SaaS staging environment

This runbook is the canonical path for staging the hosted SaaS launch profile. It assumes the same-origin public topology defined in `Hosted_SaaS_Profile.md`: public frontend and API behind one reverse proxy, multi-user AuthNZ on PostgreSQL, and Stripe test mode for billing verification.

Production cutover guidance now lives in `Docs/Published/Deployment/Hosted_Production_Runbook.md`. Keep billing mutation proof in staging and treat production validation as a non-mutating topology check.

## 1) Prepare the staging env file

Copy the example file and replace every placeholder secret before launching:

```bash
cp tldw_Server_API/Config_Files/.env.hosted-staging.example tldw_Server_API/Config_Files/.env.hosted-staging
```

At minimum, replace:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `SESSION_ENCRYPTION_KEY`
- `PUBLIC_WEB_BASE_URL`
- `ALLOWED_ORIGINS`
- `STRIPE_API_KEY`
- `STRIPE_WEBHOOK_SECRET`
- SMTP credentials and `EMAIL_FROM`

Keep these hosted profile invariants intact:

- `AUTH_MODE=multi_user`
- `tldw_production=true`
- `BILLING_REDIRECT_ALLOWLIST_REQUIRED=true`
- `BILLING_REDIRECT_REQUIRE_HTTPS=true`
- `BILLING_ALLOWED_REDIRECT_HOSTS=<public-host>`
- `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted`

## 2) Validate the env contract

Run the hosted profile validator against the filled staging env file before starting containers:

```bash
source .venv/bin/activate
python Helper_Scripts/validate_hosted_saas_profile.py --env-file tldw_Server_API/Config_Files/.env.hosted-staging
```

If this fails, fix the env contract first. Do not launch around the validator.

## 3) Launch the same-origin staging stack

Use the base compose file plus the hosted staging overlay:

```bash
docker compose \
  --env-file tldw_Server_API/Config_Files/.env.hosted-staging \
  -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.hosted-saas-staging.yml \
  up -d --build
```

The overlay:

- keeps `app`, `postgres`, and `redis` internal to the compose network
- serves the Next.js frontend through `webui`
- publishes only the `caddy` reverse proxy on `80/443`
- mounts `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose` as the public routing contract

## 4) Render and inspect the resolved config

Use `docker compose config` as the authoritative merged view:

```bash
docker compose \
  --env-file tldw_Server_API/Config_Files/.env.hosted-staging \
  -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.hosted-saas-staging.yml \
  config
```

Confirm:

- `app` has hosted env vars for `PUBLIC_WEB_BASE_URL` and billing redirect hardening
- `webui` build args include `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted`
- `caddy` mounts the hosted SaaS Caddyfile sample
- `postgres` is not bound to a public host port

## 5) Verify same-origin routing

Once the stack is up and DNS/TLS are configured, confirm the public routes:

```bash
curl -I https://app.example.com/
curl -I https://app.example.com/login
curl -I https://app.example.com/signup
curl -I https://app.example.com/health
curl -I https://app.example.com/ready
curl -I https://app.example.com/api/v1/billing/plans
```

Expected:

- `/`, `/login`, and `/signup` return through the frontend origin
- `/health`, `/ready`, and `/api/v1/billing/plans` route to the API behind the same public host

## 6) Run the hosted staging preflight

Use the preflight script after the stack is reachable over the public staging URL:

```bash
source .venv/bin/activate
python Helper_Scripts/Deployment/hosted_staging_preflight.py \
  --env-file tldw_Server_API/Config_Files/.env.hosted-staging \
  --base-url https://staging.example.com \
  --strict
```

If the API is fronted on a separate staging origin during an intermediate rollout, add:

```bash
python Helper_Scripts/Deployment/hosted_staging_preflight.py \
  --env-file tldw_Server_API/Config_Files/.env.hosted-staging \
  --base-url https://staging.example.com \
  --api-base-url https://api.staging.example.com \
  --strict
```

The preflight validates:

- the hosted env contract from the env file
- `/health`
- `/ready`
- `/login`
- `/signup`
- `/api/v1/billing/plans`

## 7) Hand-off to Stripe and smoke verification

After the stack is healthy:

1. configure Stripe test mode secrets and webhook destination for the public staging URL
2. run the hosted staging preflight and smoke checks
3. verify signup, login, `/account`, `/billing`, checkout, portal return, and cancel/downgrade flows

Use the staging Stripe proof as the source of truth before you cut over production. The production runbook does not repeat those live billing checks.

Treat this runbook as the baseline for hosted staging. If you need a different topology, update the hosted profile first rather than mutating staging ad hoc.

Frontend smoke command:

```bash
cd apps/tldw-frontend
TLDW_STAGING_BASE_URL=https://staging.example.com bun run e2e:hosted:staging
```

Optional authenticated smoke:

```bash
cd apps/tldw-frontend
TLDW_STAGING_BASE_URL=https://staging.example.com \
TLDW_STAGING_USER_EMAIL=user@example.com \
TLDW_STAGING_USER_PASSWORD='replace-me' \
bun run e2e:hosted:staging
```
