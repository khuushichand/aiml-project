# OSS To Private SaaS Extraction Inventory

This inventory lists the first-pass hosted SaaS materials that should move out of the public `tldw_server` repo and into the private hosted repo.

## Hosted Runbooks And Ops Docs

- `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- `Docs/Published/Deployment/Hosted_Production_Runbook.md`
- `Docs/Operations/Hosted_Staging_Operations_Runbook.md`
- `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`

## Hosted Deployment Assets

- `Dockerfiles/docker-compose.hosted-saas-staging.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.yml`
- `Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml`
- `tldw_Server_API/Config_Files/.env.hosted-staging.example`
- `tldw_Server_API/Config_Files/.env.hosted-production.example`
- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose`
- `Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose`

## Hosted Verification And Support Assets

- hosted smoke and preflight helpers
- hosted compose contract tests
- staging billing verification steps
- internal support and incident procedures tied to hosted operations

## Hosted Frontend And Customer Surface

- hosted signup flows
- hosted login and logout flows
- hosted verify-email and reset-password flows
- hosted account and billing pages
- hosted route allowlisting and session proxy helpers
- Stripe-backed billing helpers and customer-surface UI components

## SaaS Planning Material

- SaaS launch plans in `Docs/Plans`
- commercial readiness and packaging notes
- hosted pricing, limits, and revenue-ops guidance

## Immediate Public Cleanup Targets

These public areas need follow-up once extraction begins because they currently reference hosted material:

- public deployment docs under `Docs/Published/Deployment`
- public operations docs under `Docs/Operations`
- public tests such as `tldw_Server_API/tests/test_hosted_production_compose.py`
- public tests such as `tldw_Server_API/tests/test_hosted_staging_compose.py`
