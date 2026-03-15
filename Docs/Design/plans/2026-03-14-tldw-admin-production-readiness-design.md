# tldw-admin Production Readiness Gap Analysis & Roadmap

## Context

tldw-admin needs to be production-ready for **both** SaaS (multi-tenant hosted) and self-hosted multi-user deployments. The backend is mature (25+ admin endpoint modules, full RBAC, Stripe billing, Resource Governor), but the frontend only surfaces ~30% of backend capabilities. This plan identifies all gaps and provides a phased roadmap.

---

## Current State Summary

| Layer | Maturity | Notes |
|-------|----------|-------|
| **Backend Admin APIs** | ~90% | 25+ modules, 100+ endpoints |
| **Frontend Admin UI** | ~30% | 4/9 pages functional, 5 placeholder |
| **AuthNZ** | ~85% | Full RBAC, JWT, MFA (Postgres-only), orgs/teams |
| **Billing** | ~70% | Stripe integration exists, no admin management APIs |
| **Infrastructure** | ~75% | Docker, Prometheus, Redis, workers — missing dashboards/alerts |
| **Multi-tenancy** | ~65% | Per-user DBs, org RBAC — ChromaDB isolation unverified |

---

## Gap Inventory (39 gaps across 10 categories)

### Category 1: Admin UI Gaps (10 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 1.1 | **Orgs/Teams Management page** — placeholder, backend has 18 endpoints | Critical | L | Both |
| 1.2 | **Data Ops page** — placeholder, backend has 24 endpoints (backup, GDPR DSR) | Critical | L | Both |
| 1.3 | **Maintenance page** — placeholder, backend has 25 endpoints (vacuum, cache, jobs) | High | M | Both |
| 1.4 | **Watchlists UI** — placeholder/redirect | Medium | M | Both |
| 1.5 | **Billing Dashboard** — no page exists, backend has checkout/portal/usage | Critical | L | SaaS |
| 1.6 | **RBAC/Permissions Editor** — only basic table, need permission matrix editor | High | L | Both |
| 1.7 | **Usage Analytics Dashboard** — no page, backend has daily/aggregate stats + CSV export | High | M | Both |
| 1.8 | **Monitoring/Alerting Dashboard** — no page, backend has alerts + SSE streaming | High | M | Both |
| 1.9 | **API Key Management panel** — no UI, backend has 9 endpoints | Medium | S | Both |
| 1.10 | **Rate Limiting/Resource Governor UI** — no page, YAML policies exist | Medium | M | Both |

### Category 2: Backend API Gaps (3 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 2.1 | **No admin billing management APIs** — can't override plans, grant credits, view all subs | High | M | SaaS |
| 2.2 | **No tenant provisioning API** — must chain multiple endpoints manually | Medium | M | SaaS |
| 2.3 | **No admin impersonation** — can't debug as a user | Medium | M | Both |

### Category 3: Security & Compliance (5 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 3.1 | **GDPR DSR incomplete** — embeddings erasure unsupported | Critical | M | SaaS (EU) |
| 3.2 | **No consent management** — no Article 7 records | High | M | SaaS |
| 3.3 | **Audit logs not tamper-proof** — SQLite-backed, no hash chains | Medium | M | Both |
| 3.4 | **MFA only on PostgreSQL** — SQLite default has no MFA | High | M | Self-hosted |
| 3.5 | **No automated security scanning** — no Dependabot/SAST in CI | Medium | S | Both |

### Category 4: Operational Readiness (5 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 4.1 | **No Grafana dashboards** — blank instance ships | High | M | Both |
| 4.2 | **No AlertManager rules** — no default critical alerts | High | S | Both |
| 4.3 | **Backup restore untested** — no automated verification | High | M | Both |
| 4.4 | **No distributed migration lock** — multi-node migrations unsafe | High | M | Both |
| 4.5 | **No structured log shipping** — no JSON format, no Loki/ELK integration | Medium | S | Both |

### Category 5: Multi-Tenancy & Isolation (4 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 5.1 | **ChromaDB tenant isolation unverified** — vector search could leak | Critical | M | SaaS |
| 5.2 | **Resource Governor coverage incomplete** — not all endpoints gated | High | M | Both |
| 5.3 | **No worker fair-share scheduling** — bulk jobs starve other tenants | High | M | SaaS |
| 5.4 | **No storage quotas** — per-user DBs with no disk limits | High | M | Both |

### Category 6: Onboarding & Setup (4 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 6.1 | **Setup wizard minimal** — only admin creation, no LLM/SMTP/storage config | High | M | Both |
| 6.2 | **No admin operations guide** — no runbook for operators | High | M | Both |
| 6.3 | **No startup preflight validation** — misconfigured deploys don't fail fast | Medium | S | Both |
| 6.4 | **No runtime config UI** — config changes require restart | Medium | L | Both |

### Category 7: Scalability & Performance (4 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 7.1 | **No horizontal scaling docs** — in-memory state breaks multi-node | High | L | SaaS |
| 7.2 | **In-memory state not Redis-backed** — EventBus, caches, lockouts | High | M | Both |
| 7.3 | **No connection pool metrics** — pool exhaustion invisible | Medium | S | Both |
| 7.4 | **No CDN/static asset optimization** — no cache busting or CDN guidance | Medium | S | SaaS |

### Category 8: Developer Experience (3 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 8.1 | **OpenAPI docs auto-generated only** — no examples, no Postman, no SDK | Medium | M | Both |
| 8.2 | **Admin API integration test gaps** — mostly unit-level coverage | Medium | M | Both |
| 8.3 | **No API changelog/versioning strategy** — no deprecation policy | Low | S | Both |

### Category 9: Billing & Metering — SaaS (4 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 9.1 | **Usage metering not reconciled with Stripe** — crash = billing drift | High | M | SaaS |
| 9.2 | **No trial management** — no auto-expire, no conversion tracking | Medium | M | SaaS |
| 9.3 | **No overage handling config** — hard block vs degraded not configurable | Medium | M | SaaS |
| 9.4 | **No billing event audit trail** — no queryable billing history for finance | Medium | M | SaaS |

### Category 10: Self-Hosted Specific (5 gaps)

| ID | Gap | Severity | Effort | Target |
|----|-----|----------|--------|--------|
| 10.1 | **No automated upgrade path** — no safe version upgrade script | Critical | M | Self-hosted |
| 10.2 | **No offline/air-gapped mode** — assumes internet for models/providers | Medium | L | Self-hosted |
| 10.3 | **No minimal deploy profile** — always requires Postgres + Redis | High | S | Self-hosted |
| 10.4 | **No unified backup/restore** — per-user DBs + ChromaDB + media scattered | High | M | Self-hosted |
| 10.5 | **No resource requirements docs** — no hardware guidance | Medium | S | Self-hosted |

---

## Severity Summary

| Severity | Count | Examples |
|----------|-------|---------|
| **Critical** | 7 | Orgs UI, Data Ops UI, ChromaDB isolation, GDPR DSR, upgrade path, billing dashboard |
| **High** | 20 | RBAC UI, MFA on SQLite, monitoring, worker fairness, setup wizard, operations guide |
| **Medium** | 11 | Watchlists, API keys UI, tamper-proof audit, trials, offline mode |
| **Low** | 1 | API changelog |

---

## Recommended Phasing

### Phase 1: Foundation (Weeks 1-4) — Unblock Production
Focus: Critical gaps that block either deployment target.

| ID | Gap | Effort |
|----|-----|--------|
| 5.1 | Verify & enforce ChromaDB tenant isolation | M |
| 3.1 | Complete GDPR DSR (embeddings erasure) | M |
| 4.4 | Add distributed migration lock (Redis/PG advisory) | M |
| 10.1 | Automated upgrade script with pre-flight + rollback | M |
| 10.3 | Minimal deploy profile (SQLite-only, no Redis) | S |
| 4.2 | Default AlertManager rules | S |
| 6.3 | Startup preflight validation | S |

### Phase 2: Admin UI Sprint (Weeks 5-10) — Surface Backend Capabilities
Focus: Build the 5 missing admin pages + enhance existing ones.

| ID | Gap | Effort |
|----|-----|--------|
| 1.1 | Orgs/Teams Management page | L |
| 1.2 | Data Ops page (backups, GDPR DSR) | L |
| 1.6 | RBAC/Permissions Editor (permission matrix) | L |
| 1.3 | Maintenance page | M |
| 1.7 | Usage Analytics Dashboard | M |
| 1.8 | Monitoring/Alerting Dashboard (SSE) | M |
| 1.9 | API Key Management panel | S |

### Phase 3: Operational Hardening (Weeks 11-14) — Production Quality
Focus: Make deployments reliable and observable.

| ID | Gap | Effort |
|----|-----|--------|
| 7.1+7.2 | Horizontal scaling + Redis-backed state | L+M |
| 4.1 | Grafana dashboards (API, workers, DB, billing) | M |
| 4.3 | Automated backup restore testing | M |
| 6.1 | Extended setup wizard | M |
| 6.2 | Admin operations guide / runbook | M |
| 3.4 | MFA for SQLite mode | M |
| 10.4 | Unified backup/restore script | M |

### Phase 4: SaaS Revenue (Weeks 15-18) — Monetization Ready
Focus: Billing and metering for paid SaaS.

| ID | Gap | Effort |
|----|-----|--------|
| 1.5 | Billing Dashboard UI | L |
| 2.1 | Admin billing management APIs | M |
| 9.1 | Usage metering reconciliation with Stripe | M |
| 5.3 | Worker fair-share scheduling | M |
| 5.4 | Storage quota enforcement | M |
| 5.2 | Resource Governor endpoint coverage audit | M |

### Phase 5: Polish (Ongoing) — Quality of Life
Focus: Remaining gaps driven by user feedback.

| ID | Gap | Effort |
|----|-----|--------|
| 1.4, 1.10 | Watchlists UI, Rate Limiting UI | M each |
| 3.2, 3.3 | Consent management, audit tamper-proofing | M each |
| 9.2, 9.3, 9.4 | Trial mgmt, overage config, billing audit trail | M each |
| 2.2, 2.3 | Tenant provisioning API, admin impersonation | M each |
| 6.4 | Runtime config UI with hot-reload | L |
| 10.2 | Offline/air-gapped mode | L |
| 8.1-8.3 | API docs, integration tests, changelog | M+M+S |
| 4.5, 7.3, 7.4, 10.5 | Log shipping, pool metrics, CDN, resource docs | S each |

---

## Key Files & Patterns to Follow

### Frontend (new admin pages should follow these patterns)
- `apps/packages/ui/src/components/Option/Admin/ServerAdminPage.tsx` — reference implementation (905 lines, Ant Design, React Query)
- `apps/tldw-frontend/pages/admin/*.tsx` — page wrappers with SSR disabled + dynamic imports
- `apps/packages/ui/src/components/Option/Admin/admin-error-utils.ts` — error handling utilities

### Backend (admin endpoints)
- `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py` — router aggregation (register new sub-routers here)
- `tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py` — largest gap module (788 lines)
- `tldw_Server_API/app/api/v1/endpoints/admin/admin_rbac.py` — largest admin module (1152 lines)

### Infrastructure
- `Dockerfiles/docker-compose.yml` — base deployment config
- `Dockerfiles/Monitoring/docker-compose.monitoring.yml` — monitoring stack
- `tldw_Server_API/app/core/Resource_Governance/governor.py` — rate limiting engine

---

## Verification

This is a gap analysis and roadmap — not an implementation plan. Verification will happen per-phase:

- **Phase 1**: Run migration on multi-node cluster without corruption; verify ChromaDB namespace isolation with cross-tenant search test; execute GDPR DSR covering embeddings; upgrade from v0.1.0 to new version using upgrade script
- **Phase 2**: All admin pages render and interact with their backend APIs; E2E Playwright tests pass for each new page
- **Phase 3**: Deploy 2+ app replicas, verify no state loss; restore from backup successfully; complete setup wizard end-to-end
- **Phase 4**: Create subscription, track usage, verify Stripe reconciliation; run bulk ingestion for one tenant, verify other tenants unaffected
- **Phase 5**: Per-feature acceptance criteria
