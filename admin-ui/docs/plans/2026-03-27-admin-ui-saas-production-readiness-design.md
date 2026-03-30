# Admin-UI Production Readiness Design for SaaS Deployment

**Date:** 2026-03-27
**Scope:** Full production readiness audit of `admin-ui/` Next.js 15 application
**Target:** Docker-containerized SaaS deployment, 1-2 month timeline
**Backend:** Multi-tenant backend already ready

---

## Problem Statement

The admin-ui works locally but lacks the infrastructure, security hardening, and observability required for SaaS deployment. The existing REVIEW.md (71 HCI/UX findings) covers product gaps but misses all deployment, security header, containerization, and monitoring concerns.

## Design Decision: Unified Infrastructure + UX Roadmap

Front-load infrastructure/security work (entirely frontend-only, ~25 hours) before interleaving highest-priority UX fixes from REVIEW.md.

---

## Phase 0: Launch Blockers -- Containerization & Security (Week 1)

### 0.1: `next.config.js` -- Standalone Output + Security Headers
- Add `output: 'standalone'`, `poweredByHeader: false`
- Security headers via `async headers()`: CSP, X-Frame-Options: DENY, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy

### 0.2: Dockerfile
- New `Dockerfiles/Dockerfile.admin-ui` following `Dockerfile.webui` pattern
- Port 3001, non-root user, health check

### 0.3: Docker Compose Overlay
- New `Dockerfiles/docker-compose.admin-ui.yml`

### 0.4: Health Check Endpoint
- New `admin-ui/app/api/health/route.ts`

### 0.5: Environment Validation
- New `admin-ui/lib/env.ts` with Zod schema, fail-fast on missing vars

### 0.6: Auth Cache Invalidation on Logout
- Export `invalidateAuthCacheEntry` from middleware, call in logout route

### 0.7: Auth Endpoint Rate Limiting
- New `admin-ui/lib/rate-limiter.ts`, apply to login/MFA/apikey routes

---

## Phase 1: Observability (Week 2)

### 1.1: Sentry Error Tracking
### 1.2: Structured JSON Logging (replace 94 console.* calls)
### 1.3: Request Correlation IDs (X-Request-ID header)

---

## Phase 2: Safety & Critical UX (Weeks 3-4)

### 2.1: Plan Deletion Subscriber Check (REVIEW.md 7.1)
### 2.2: PrivilegedActionDialog Rollout (REVIEW.md 9.6, 5 pages)
### 2.3: Dashboard Auto-Refresh (REVIEW.md 1.13)
### 2.4: ACP Session Token Budgets (REVIEW.md 4.6, requires backend)
### 2.5: Quick Wins Batch (3.2, 3.3, 5.14, 9.5, 9.8)

---

## Phase 3: AI Governance & Ops Maturity (Weeks 5-6)

### 3.1: ACP Agent Runtime Metrics (REVIEW.md 4.4, requires backend)
### 3.2: ACP Session Auto-Refresh + Cost (REVIEW.md 4.7, 4.8)
### 3.3: AI Operations Summary Dashboard (REVIEW.md 4.15)
### 3.4: Monitoring Auto-Refresh (REVIEW.md 5.1)
### 3.5: Incident SLA Tracking (REVIEW.md 5.7, requires backend)
### 3.6: Audit-to-Logs Cross-Reference (REVIEW.md 5.11, requires backend)
### 3.7: Bundle Size Monitoring

---

## Phase 4: Cost, Compliance & Multi-Tenancy (Weeks 7-8)

### 4.1: Budget Forecasting (REVIEW.md 6.3)
### 4.2: Per-User/Per-Org Cost Attribution (REVIEW.md 6.5, requires backend)
### 4.3: Compliance Posture Dashboard (REVIEW.md 6.11, requires backend)
### 4.4: Tenant Context Visibility
### 4.5: Subscription At-Risk Identification (REVIEW.md 7.4)

---

## Post-Launch: Polish & Accessibility (Weeks 9+)

- Chart accessibility (11.1), ExportMenu keyboard a11y (11.2)
- Visual regression testing, Lighthouse CI
- Org detail tabs (2.5), registration code relocation (2.10)
- Revenue analytics (7.9), CDN config, proxy retry

---

## Intentionally Deferred

| Item | Reason |
|------|--------|
| CSRF double-submit cookie | SameSite:Lax + server proxy sufficient |
| Subresource integrity | No third-party scripts loaded |
| Graceful shutdown | Next.js standalone handles SIGTERM |
| Session management UI | Requires backend session enumeration |
