# First-Time Production Setup

Version: v0.1.0
Audience: DevOps/SREs and self-hosters deploying tldw_server for the first time

This guide walks you through a secure, production-ready first deployment of tldw_server. It covers Docker Compose (recommended) and a bare-metal alternative, plus the initial setup wizard, TLS, CORS, and basic verification.

Related documents
- Reverse proxy examples (Nginx/Traefik): `Docs/Deployment/Reverse_Proxy_Examples.md`
- Postgres migration: `Docs/Deployment/Postgres_Migration_Guide.md`
- Sidecar workers (systemd/launchd): `Docs/Deployment/Sidecar_Workers.md`
- Metrics and Grafana: `Docs/Deployment/Monitoring/Metrics_Cheatsheet.md`
- Hosted SaaS launch profile: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Hosted SaaS staging runbook: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Environment variables reference: `Env_Vars.md`
- General installation (local/dev): `Docs/Getting_Started/README.md`
- Production hardening checklist: `Docs/User_Guides/Server/Production_Hardening_Checklist.md`

## 1) Prerequisites

- OS: Linux (Ubuntu 22.04 LTS or similar recommended). macOS/Windows supported for small installs.
- CPU/RAM: Minimum 2 vCPU / 4 GB RAM; recommended 4+ vCPU / 8+ GB.
- Storage: 50 GB+ SSD for media, databases, and models.
- FFmpeg installed (Docker image includes it; bare-metal must install via package manager).
- DNS configured for your domain (if exposing over the internet).
- TLS via reverse proxy (Nginx/Traefik/Caddy). See reverse proxy guide.
- Database: SQLite is fine for single-user; Postgres recommended for production multi-user.

Security preflight
- Decide auth mode: `single_user` (API key) or `multi_user` (JWT).
- Generate strong secrets:
  - API key: `python -m tldw_Server_API.app.core.AuthNZ.initialize` (choose "Generate secure keys")
  - JWT secret: `openssl rand -base64 64`
- Restrict CORS to your site(s) with `ALLOWED_ORIGINS`.
- In production, set `tldw_production=true` to mask secrets in logs and harden defaults.

## 2) Quick Decision Matrix

- Want the fastest secure start, one host? Choose Docker Compose (recommended).
- Need package-managed services and systemd? Use bare-metal + Nginx.
- Expect multiple users/teams? Prefer Postgres and reverse proxy TLS from day one.
- Need the hosted self-serve SaaS launch surface? Treat `Docs/Published/Deployment/Hosted_SaaS_Profile.md` as the canonical profile instead of assembling settings ad hoc from the self-host guides.

## 3) Option A - Docker Compose (recommended)

The canonical Compose setup commands are maintained in these profile guides:

- Single-user Docker: `Docs/Getting_Started/Profile_Docker_Single_User.md`
- Multi-user Docker + Postgres: `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`

Production guidance for Compose deployments:

- Keep Postgres volumes backed up and tested for restore.
- Terminate TLS at your reverse proxy and forward to `app:8000`.
- Ensure WebSocket upgrade support for `/api/v1/audio/stream/transcribe` and `/api/v1/mcp/*`.
- Configure `ALLOWED_ORIGINS` explicitly for your public domain(s).
- For the hosted SaaS launch profile, lock `PUBLIC_WEB_BASE_URL` and billing redirect allowlists to the public app origin.
- For the canonical hosted staging deployment, use `Dockerfiles/docker-compose.hosted-saas-staging.yml` via `Docs/Published/Deployment/Hosted_Staging_Runbook.md`.

## 4) Option B - Bare-Metal (systemd + Nginx)

Use the local profile guide for canonical non-Docker setup:

- `Docs/Getting_Started/Profile_Local_Single_User.md`

Then apply production controls in this order:

1. Add process supervision for the API service (systemd/launchd/service manager).
2. Place a reverse proxy in front of the API with TLS termination.
3. Lock down CORS origins and upload limits.
4. Apply backup and restore procedures for your selected database.

Reference implementations:

- Reverse proxy examples: `Docs/Deployment/Reverse_Proxy_Examples.md`
- Sidecar workers: `Docs/Deployment/Sidecar_Workers.md`
- Postgres migration: `Docs/Deployment/Postgres_Migration_Guide.md`

## 5) Configuration essentials

- `AUTH_MODE`: `single_user` or `multi_user`.
- `SINGLE_USER_API_KEY` (single-user) or `JWT_SECRET_KEY` (multi-user).
- `DATABASE_URL`: SQLite for dev; Postgres URL recommended in production multi-user.
- `ALLOWED_ORIGINS`: Comma-separated or JSON array of trusted origins.
- `tldw_production`: `true` in production to mask secrets and enable production guards.
- Provider keys: e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.

Hosted SaaS additions:

- Set `PUBLIC_WEB_BASE_URL` to the public web origin used in auth emails.
- Require billing redirect hardening with `BILLING_REDIRECT_ALLOWLIST_REQUIRED=true`, `BILLING_REDIRECT_REQUIRE_HTTPS=true`, and `BILLING_ALLOWED_REDIRECT_HOSTS=<public-host>`.
- Use `AUTH_MODE=multi_user` plus PostgreSQL. Hosted SaaS should not run on SQLite.
- Prefer same-origin frontend and API deployment so hosted auth can stay on the server side.

See `Env_Vars.md` for the complete list and `Docs/AuthNZ/AUTHNZ_DATABASE_CONFIG.md` for AuthNZ DB details.

## 6) Verify and smoke test

Health/ready
```bash
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8000/ready
```

Auth check (single-user example)
```bash
curl -s -H "X-API-KEY: $SINGLE_USER_API_KEY" http://127.0.0.1:8000/api/v1/llm/providers | jq .
```

Media test (small file)
```bash
curl -s -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/sample.pdf"}' \
  http://127.0.0.1:8000/api/v1/media/add | jq .status
```

## 7) Production checklist (summary)

- Secrets:
  - Strong `SINGLE_USER_API_KEY` (single-user) or `JWT_SECRET_KEY` (multi-user).
  - Don’t print keys on startup in production; keep `SHOW_API_KEY_ON_STARTUP` unset/false.
- Database:
  - Use Postgres for multi-user; back up volumes regularly.
  - If migrating from SQLite, follow `Postgres_Migration_Guide.md`.
- Network:
  - TLS via reverse proxy; enable WebSocket upgrades.
  - Restrict `ALLOWED_ORIGINS`.
- Observability:
  - Enable Prometheus scraping; import Grafana dashboards (see Metrics Cheatsheet).
  - Centralize logs; set `LOG_LEVEL=info`.
- Rate limits:
  - Keep global and module-specific rate limiters enabled and tuned for your users.

For a comprehensive list, see `Docs/Published/User_Guides/Server/Production_Hardening_Checklist.md`.
