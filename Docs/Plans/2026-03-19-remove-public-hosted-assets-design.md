# Remove Public Hosted Assets Design

## Goal

Remove the remaining hosted-only operational, deployment, and validation assets from the public `tldw_server` repo so the OSS repo no longer ships hosted SaaS runbooks, compose overlays, hosted env contracts, hosted reverse-proxy samples, or hosted-only validation/tests.

## Recommended Approach

Use a hard-removal extraction:

1. Delete the remaining hosted ops docs from the public repo.
2. Delete hosted deployment/config assets from the public repo.
3. Delete or relocate hosted helper scripts and hosted compose tests that only exist to support the hosted deployment path.
4. Expand boundary enforcement to cover public deploy/config/runtime surfaces, not just docs/frontend surfaces.
5. Re-run boundary tests, checker, and strict MkDocs to confirm the OSS repo remains coherent.

This is the most consistent boundary. It avoids leaving hosted operational code and configs in the public tree after the hosted docs and customer surface have already been extracted.

## Scope

The extraction should include these categories:

### Hosted ops docs

- `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`

### Hosted deploy/config assets

- `Dockerfiles/docker-compose.hosted-saas-staging.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
- `tldw_Server_API/Config_Files/.env.hosted-staging.example`
- `tldw_Server_API/Config_Files/.env.hosted-production.example`
- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose`
- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`

### Hosted helper scripts and tests

- `Helper_Scripts/validate_hosted_saas_profile.py`
- `Helper_Scripts/Deployment/hosted_staging_preflight.py`
- `tldw_Server_API/tests/test_hosted_production_compose.py`
- `tldw_Server_API/tests/test_hosted_staging_compose.py`
- hosted helper/unit tests tied only to those assets, such as:
  - `tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_email_service_public_urls.py` if it remains hosted-only after review

## Important Refinement

The previous boundary checker was too narrow for this step. It scanned public docs and frontend entrypoints, but not the deploy/config paths where hosted files currently live.

For this extraction, enforcement must cover public runtime/config surfaces such as:

- `Docs/Published`
- `Docs/Operations`
- `Dockerfiles`
- `tldw_Server_API/Config_Files`
- `Helper_Scripts/Samples/Caddy`
- selected `Helper_Scripts/Deployment`
- selected public test paths

The checker must still **not** scan:

- `Docs/Plans`
- policy/governance docs
- other planning artifacts that legitimately describe the separation work

## Concrete Changes

### 1. Delete hosted ops docs from public

Remove the two hosted operations docs from `Docs/Operations`.

### 2. Delete hosted deploy/config assets from public

Remove the hosted compose overlays, hosted env examples, and hosted Caddy samples from the public tree.

### 3. Remove hosted helper scripts and hosted compose tests

Hosted validation helpers and their tests no longer belong in the OSS repo if the hosted deployment assets are gone. They should be deleted from public or moved to the private hosted repo if still needed there.

### 4. Tighten enforcement

Update `Helper_Scripts/docs/check_public_private_boundary.py` and `tldw_Server_API/tests/test_public_private_boundary.py` so the OSS repo explicitly forbids:

- hosted ops docs in public operations docs
- hosted compose/env/Caddy files in public config/deploy paths
- hosted-only helper scripts and hosted compose tests in public runtime/test paths

### 5. Verify OSS repo coherence

Run:

- public/private boundary checker
- boundary pytest
- strict MkDocs build
- Bandit on touched Python scope

## Risks And Mitigations

### Risk: checker still misses hosted assets in non-doc paths

Mitigation:

- explicitly expand checker scan targets to deploy/config/helper/test paths
- add direct absence assertions in boundary pytest

### Risk: false positives from planning docs

Mitigation:

- keep checker scoped away from `Docs/Plans` and policy docs

### Risk: breaking self-host documentation or OSS flows

Mitigation:

- verify with strict MkDocs
- keep only self-host/generic deployment assets in public

### Risk: leaving hosted validation scripts orphaned in OSS

Mitigation:

- include them in this extraction rather than deferring

## Validation

Run:

- `source .venv/bin/activate && python Helper_Scripts/docs/check_public_private_boundary.py`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v`
- `source .venv/bin/activate && mkdocs build --strict -f Docs/mkdocs.yml`
- `source .venv/bin/activate && python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py -f json -o /tmp/bandit_remove_public_hosted_assets.json`

Success means:

- hosted ops/docs/config/helper/test assets are absent from the public repo
- checker passes over the expanded public surface
- strict MkDocs still passes
- touched Python scope has no new Bandit findings

## Non-Goals

- adding public stubs or redirects for hosted assets
- changing private hosted repo contents in this task
- broad public docs/nav redesign
