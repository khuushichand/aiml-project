# Hosted SaaS Production Overlays Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a production deployment path for the hosted SaaS launch profile that defaults to managed PostgreSQL, uses host-mounted durable storage, and preserves an explicit local PostgreSQL fallback overlay.

**Architecture:** Implement a standalone hosted production compose file rather than layering production behavior on top of the current local-Postgres-oriented base compose. Add a separate fallback overlay for local PostgreSQL, a production env template, a production Caddy sample, and a published runbook. Verify both the default and fallback topologies with YAML contract tests plus rendered `docker compose config` checks.

**Tech Stack:** Docker Compose, Caddy, FastAPI, Next.js, pytest, Bun, Markdown deployment docs.

---

### Task 1: Add The Production Env Template And Reverse Proxy Sample

**Files:**
- Create: `tldw_Server_API/Config_Files/.env.hosted-production.example`
- Create: `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`
- Test: `tldw_Server_API/tests/test_hosted_production_compose.py`

**Step 1: Write the failing env-template and proxy-sample tests**

Add tests that read the new files as plain text and assert:

```python
def test_hosted_production_env_example_uses_prod_public_origin():
    text = Path("tldw_Server_API/Config_Files/.env.hosted-production.example").read_text(encoding="utf-8")
    _require("PUBLIC_WEB_BASE_URL=https://app.example.com" in text, "expected prod public web base url")
    _require("DATABASE_URL=postgresql://" in text, "expected managed postgres DSN placeholder")
```

```python
def test_hosted_production_caddy_sample_routes_api_and_webui():
    text = Path("Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose").read_text(encoding="utf-8")
    _require("reverse_proxy @api app:8000" in text, "expected api reverse proxy")
    _require("reverse_proxy webui:3000" in text, "expected webui reverse proxy")
```

Use the local `_require(...)/pytest.fail(...)` pattern instead of bare `assert`.

**Step 2: Run the tests and confirm they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
```

Expected: FAIL because the production env template and production Caddy sample do not exist yet.

**Step 3: Add the production env example**

Create `tldw_Server_API/Config_Files/.env.hosted-production.example` with:

- hosted profile invariants
- `PUBLIC_WEB_BASE_URL=https://app.example.com`
- `ALLOWED_ORIGINS=https://app.example.com`
- `NEXT_PUBLIC_API_URL=https://app.example.com`
- `NEXT_PUBLIC_API_BASE_URL=https://app.example.com`
- a managed PostgreSQL DSN placeholder using TLS
- Stripe live-key placeholders
- SMTP placeholders
- bind-mount path variables:
  - `TLDW_APP_DATA_DIR=/srv/tldw-data/app`
  - `TLDW_USER_DATA_DIR=/srv/tldw-data/user_data`
  - `TLDW_REDIS_DATA_DIR=/srv/tldw-data/redis`
  - `TLDW_POSTGRES_DATA_DIR=/srv/tldw-data/postgres`

Keep it shape-only and document that every placeholder must be replaced.

**Step 4: Add the production Caddy sample**

Create `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose` with:

- `app.example.com` as the placeholder host
- an `@api` matcher for `/api/*`, `/openapi.json`, `/docs*`, `/redoc*`, `/health`, and `/ready`
- `reverse_proxy @api app:8000`
- `reverse_proxy webui:3000`
- the same baseline security headers as the staging sample

**Step 5: Re-run the tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
source .venv/bin/activate
python Helper_Scripts/validate_hosted_saas_profile.py --env-file tldw_Server_API/Config_Files/.env.hosted-production.example
```

Expected:

- pytest PASS for the new file-shape tests
- hosted profile validator PASS for the production env example

**Step 6: Commit**

```bash
git add tldw_Server_API/Config_Files/.env.hosted-production.example Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose tldw_Server_API/tests/test_hosted_production_compose.py
git commit -m "feat: add hosted production env contract"
```

### Task 2: Add The Primary Hosted Production Compose File

**Files:**
- Create: `Dockerfiles/docker-compose.hosted-saas-prod.yml`
- Modify: `tldw_Server_API/tests/test_hosted_production_compose.py`

**Step 1: Extend the test file with a failing primary-topology test**

Add coverage for:

```python
def test_hosted_production_compose_defines_internal_app_and_public_proxy():
    data = yaml.safe_load(Path("Dockerfiles/docker-compose.hosted-saas-prod.yml").read_text(encoding="utf-8"))
    services = data["services"]
    _require("postgres" not in services, "primary prod compose should not define local postgres")
    _require(services["caddy"]["ports"] == ["80:80", "443:443"], "expected only proxy public ports")
```

Also verify:

- `app` exposes `8000` internally instead of publishing it
- `redis` exposes `6379` internally instead of publishing it
- `app` volumes use `TLDW_APP_DATA_DIR` and `TLDW_USER_DATA_DIR`
- `redis` volume uses `TLDW_REDIS_DATA_DIR`
- `webui` sets `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: hosted`
- `caddy` mounts `Caddyfile.hosted-saas.prod.compose`

**Step 2: Run the test and confirm it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
```

Expected: FAIL because the primary production compose file does not exist yet.

**Step 3: Create the primary production compose file**

Create `Dockerfiles/docker-compose.hosted-saas-prod.yml` as a standalone compose file with:

- `app`
- `webui`
- `redis`
- `caddy`

Key requirements:

- `app` has no public `ports`, only `expose: ["8000"]`
- `redis` has no public `ports`, only `expose: ["6379"]`
- `caddy` binds `80:80` and `443:443`
- `app` uses bind mounts:
  - `${TLDW_APP_DATA_DIR:-/srv/tldw-data/app}:/app/Databases`
  - `${TLDW_USER_DATA_DIR:-/srv/tldw-data/user_data}:/app/Databases/user_databases`
- `redis` uses:
  - `${TLDW_REDIS_DATA_DIR:-/srv/tldw-data/redis}:/data`
- `DATABASE_URL` is required and not defaulted to local `postgres`
- `app.depends_on` includes only healthy `redis`
- `webui` uses hosted build args and hosted runtime env vars

**Step 4: Re-run the tests and render the composed config**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml config >/tmp/hosted-production-compose.rendered.yml
```

Expected:

- pytest PASS
- `docker compose config` PASS

**Step 5: Commit**

```bash
git add Dockerfiles/docker-compose.hosted-saas-prod.yml tldw_Server_API/tests/test_hosted_production_compose.py
git commit -m "feat: add hosted production compose file"
```

### Task 3: Add The Local PostgreSQL Fallback Overlay

**Files:**
- Create: `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
- Modify: `tldw_Server_API/tests/test_hosted_production_compose.py`

**Step 1: Add the failing fallback-overlay test**

Extend the test file with:

```python
def test_local_postgres_fallback_overlay_adds_internal_postgres_service():
    data = yaml.safe_load(Path("Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml").read_text(encoding="utf-8"))
    services = data["services"]
    postgres = services["postgres"]
    _require(postgres["ports"] == [], "fallback postgres must not publish host ports")
    _require("5432" in postgres["expose"], "fallback postgres should expose 5432 internally")
```

Also verify:

- `app.depends_on` adds healthy `postgres`
- `postgres` uses `${TLDW_POSTGRES_DATA_DIR:-/srv/tldw-data/postgres}:/var/lib/postgresql/data`
- no other services are added or published

**Step 2: Run the tests and confirm they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
```

Expected: FAIL because the fallback overlay file does not exist yet.

**Step 3: Create the fallback overlay**

Create `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml` that:

- adds a `postgres` service with:
  - `image: postgres:18-bookworm`
  - internal `expose: ["5432"]`
  - no host `ports`
  - healthcheck using `pg_isready`
  - bind mount for `TLDW_POSTGRES_DATA_DIR`
- extends `app.depends_on` with healthy `postgres`

Keep `DATABASE_URL` operator-controlled from the env file or CLI. Do not silently rewrite it inside the compose file.

**Step 4: Re-run the tests and render both production modes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml config >/tmp/hosted-production-compose.rendered.yml
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml -f Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml config >/tmp/hosted-production-compose.local-postgres.rendered.yml
```

Expected:

- pytest PASS
- both rendered compose commands PASS

**Step 5: Commit**

```bash
git add Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml tldw_Server_API/tests/test_hosted_production_compose.py
git commit -m "feat: add local postgres fallback overlay"
```

### Task 4: Publish The Hosted Production Runbook And Update Docs

**Files:**
- Create: `Docs/Published/Deployment/Hosted_Production_Runbook.md`
- Modify: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Modify: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Modify: `Docs/Published/Deployment/First_Time_Production_Setup.md`
- Modify: `Docs/Operations/Hosted_Staging_Operations_Runbook.md`

**Step 1: Add the failing doc-alignment test**

Extend `tldw_Server_API/tests/test_hosted_production_compose.py` with a simple file-shape test that checks the production runbook exists and references:

- `docker-compose.hosted-saas-prod.yml`
- `docker-compose.hosted-saas-prod.local-postgres.yml`
- `.env.hosted-production.example`
- `Caddyfile.hosted-saas.prod.compose`

Use `_require(...)` checks only.

**Step 2: Run the tests and confirm they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
```

Expected: FAIL because the runbook and doc references do not exist yet.

**Step 3: Add the production runbook**

Create `Docs/Published/Deployment/Hosted_Production_Runbook.md` and document:

- recommended region/VPC/firewall assumptions
- DNS layout for `app.example.com`
- exact host mount layout under `/srv/tldw-data`
- default managed PostgreSQL deployment commands
- fallback local PostgreSQL commands
- required validation sequence:
  - hosted profile validator
  - `docker compose config`
  - hosted preflight against the public base URL
- backup and rollback notes

**Step 4: Update the existing hosted docs**

Update the hosted docs so they:

- point production operators to the new prod runbook
- keep staging and production clearly separated
- clarify that live Stripe proof belongs in staging, not prod cutover validation
- reference the exact production compose and env-template filenames

**Step 5: Re-run the tests and perform lightweight doc verification**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
python Helper_Scripts/check_site_anchors.py Docs/site
```

Expected:

- pytest PASS
- note any pre-existing unrelated site-anchor failures separately; do not silently ignore them

**Step 6: Commit**

```bash
git add Docs/Published/Deployment/Hosted_Production_Runbook.md Docs/Published/Deployment/Hosted_SaaS_Profile.md Docs/Published/Deployment/Hosted_Staging_Runbook.md Docs/Published/Deployment/First_Time_Production_Setup.md Docs/Operations/Hosted_Staging_Operations_Runbook.md tldw_Server_API/tests/test_hosted_production_compose.py
git commit -m "docs: add hosted production deployment runbook"
```

### Task 5: Final Verification And Plan Closeout

**Files:**
- Verify only: the files touched in Tasks 1-4

**Step 1: Run the full production-overlay verification set**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_hosted_production_compose.py -v
python Helper_Scripts/validate_hosted_saas_profile.py --env-file tldw_Server_API/Config_Files/.env.hosted-production.example
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml config >/tmp/hosted-production-compose.rendered.yml
docker compose --env-file tldw_Server_API/Config_Files/.env.hosted-production.example -f Dockerfiles/docker-compose.hosted-saas-prod.yml -f Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml config >/tmp/hosted-production-compose.local-postgres.rendered.yml
```

Expected: all commands PASS.

**Step 2: Run Bandit on the touched Python scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/tests/test_hosted_production_compose.py -f json -o /tmp/bandit_hosted_production_overlays.json
```

Expected: `results: []`

If Bandit flags test `assert` usage, replace it with `_require(...)/pytest.fail(...)` and re-run.

**Step 3: Check git status and verify only intended files changed**

Run:

```bash
git status --short
```

Expected: only the production overlay files, docs, and any unrelated pre-existing user changes.

**Step 4: Commit the final verification cleanup if needed**

```bash
git add <touched-files>
git commit -m "test: verify hosted production overlays"
```

Only commit if verification cleanup changed files.
