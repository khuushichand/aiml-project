# SaaS Readiness Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce an evidence-backed readiness review for a first hosted self-serve `tldw` launch, including immediate blockers, short-term roadmap items, and explicit manual-vs-automated launch decisions.

**Architecture:** Start from the approved design in `Docs/Plans/2026-03-18-saas-readiness-review-design.md`, then review the backend, customer WebUI, internal admin UI, and deployment docs in discrete passes. Capture evidence directly into a dedicated report, score each launch-critical track as red/yellow/green, and translate findings into `Immediate`, `Short-term`, and `Later` execution buckets.

**Tech Stack:** FastAPI, Next.js (`apps/tldw-frontend`), Next.js (`admin-ui`), Bun, pytest, ripgrep, Markdown docs.

---

### Task 1: Create The Review Report Skeleton

**Files:**
- Create: `Docs/Plans/2026-03-18-saas-readiness-review-report.md`
- Reference: `Docs/Plans/2026-03-18-saas-readiness-review-design.md`

**Step 1: Write the report skeleton**

```markdown
# tldw SaaS Readiness Review

**Date:** 2026-03-18
**Scope:** Hosted self-serve launch, single-user subscriptions first
**Out of Scope:** Teams-first workflows, B2B-first controls, non-core product modules

## Executive Verdict
- Overall readiness:
- Launch recommendation:

## Assumptions
- `admin-ui` remains internal-only
- customer-facing v1 is a narrow core offer
- pricing starts with flat tiers plus overages or credits

## Rubric
### 1. Customer Product Surface
### 2. Billing And Monetization
### 3. Identity, Tenancy, And Data Isolation
### 4. Operations And Internal Admin Readiness
### 5. Deployment, Compliance, And Supportability

## Immediate
## Short-term
## Later
## Manual At Launch
## Must Automate Before Launch
```

**Step 2: Verify the design doc is present**

Run: `sed -n '1,220p' Docs/Plans/2026-03-18-saas-readiness-review-design.md`  
Expected: approved launch target, assessment framework, review method, and deliverable shape are all visible.

**Step 3: Create the minimal report file**

```markdown
Copy the skeleton above into `Docs/Plans/2026-03-18-saas-readiness-review-report.md` and leave each section ready for evidence-backed findings.
```

**Step 4: Sanity-check the new file**

Run: `sed -n '1,220p' Docs/Plans/2026-03-18-saas-readiness-review-report.md`  
Expected: the report contains the section structure needed for the rest of the review.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-18-saas-readiness-review-report.md
git commit -m "docs: scaffold saas readiness review report"
```

### Task 2: Audit Identity, Signup, Billing, And Entitlements

**Files:**
- Modify: `Docs/Plans/2026-03-18-saas-readiness-review-report.md`
- Reference: `tldw_Server_API/app/api/v1/endpoints/auth.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/billing.py`
- Reference: `tldw_Server_API/tests/Billing/test_billing_endpoints_integration.py`
- Reference: `tldw_Server_API/tests/Billing/test_billing_webhooks_integration.py`
- Reference: `tldw_Server_API/tests/Billing/test_billing_enforcement.py`
- Reference: `tldw_Server_API/tests/Billing/test_billing_usage_endpoint_unit.py`
- Reference: `README.md`

**Step 1: Write the evidence checklist in the report**

```markdown
Under the billing and identity sections, add checklist placeholders for:
- public registration
- login and session model
- plan listing
- checkout
- portal
- invoice access
- entitlement enforcement
- usage accounting
- overage handling
- webhook reconciliation
```

**Step 2: Gather endpoint and test evidence**

Run: `rg -n "register|login|refresh|checkout|portal|invoice|subscription|usage|webhook|plan" tldw_Server_API/app/api/v1/endpoints/auth.py tldw_Server_API/app/api/v1/endpoints/billing.py tldw_Server_API/tests/Billing README.md`  
Expected: exact endpoint names, flow coverage, and test references are visible in one pass.

**Step 3: Run focused backend verification**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Billing/test_billing_endpoints_integration.py tldw_Server_API/tests/Billing/test_billing_webhooks_integration.py tldw_Server_API/tests/Billing/test_billing_enforcement.py tldw_Server_API/tests/Billing/test_billing_usage_endpoint_unit.py -v`  
Expected: passing coverage or specific failing areas that can be cited directly in the report.

**Step 4: Record findings in the report**

```markdown
For each identity or billing sub-area, add:
- current state
- evidence path
- readiness color
- blocker or caveat
```

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-18-saas-readiness-review-report.md
git commit -m "docs: capture billing and identity readiness findings"
```

### Task 3: Audit The Customer-Facing Launch Path In `apps/tldw-frontend`

**Files:**
- Modify: `Docs/Plans/2026-03-18-saas-readiness-review-report.md`
- Reference: `apps/tldw-frontend/README.md`
- Reference: `apps/FRONTEND_AUDIT.md`
- Reference: `apps/tldw-frontend/pages/login.tsx`
- Reference: `apps/tldw-frontend/pages/profile.tsx`
- Reference: `apps/tldw-frontend/pages/admin/billing.tsx`
- Reference: `apps/tldw-frontend/e2e/login.spec.ts`
- Reference: `apps/tldw-frontend/e2e/workflows/tier-1-critical/settings-core.spec.ts`
- Reference: `apps/tldw-frontend/e2e/workflows/chat.spec.ts`
- Reference: `apps/tldw-frontend/e2e/workflows/search.spec.ts`
- Reference: `apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts`

**Step 1: Write the customer-journey checklist in the report**

```markdown
Add placeholders for:
- landing and positioning
- signup and login
- onboarding and first-value path
- media ingest
- chat
- search and RAG
- quota and account visibility
- plan and upgrade surfaces
```

**Step 2: Inventory the relevant frontend routes and docs**

Run: `rg -n "signup|register|login|billing|subscription|plan|quota|upgrade|profile|search|chat|media" apps/tldw-frontend/pages apps/tldw-frontend/README.md apps/FRONTEND_AUDIT.md`  
Expected: the core launch-path surfaces and current audit notes are identified.

**Step 3: Run focused frontend verification**

Run: `cd apps/tldw-frontend && bun run build && bun run test`  
Expected: the public WebUI builds and its unit suite passes, or failures identify unstable customer-facing areas.

**Step 4: Record customer-product findings**

```markdown
For each customer-facing sub-area, record:
- whether the flow exists
- whether it feels coherent for a paid core offer
- the strongest evidence file or command
- the readiness color
- the immediate action if it is yellow or red
```

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-18-saas-readiness-review-report.md
git commit -m "docs: capture customer launch path readiness findings"
```

### Task 4: Audit Internal Admin, Deployment, And Supportability

**Files:**
- Modify: `Docs/Plans/2026-03-18-saas-readiness-review-report.md`
- Reference: `admin-ui/README.md`
- Reference: `admin-ui/Release_Checklist.md`
- Reference: `admin-ui/lib/billing.ts`
- Reference: `Docs/Published/Deployment/First_Time_Production_Setup.md`
- Reference: `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`
- Reference: `Docs/Published/User_Guides/Server/Production_Hardening_Checklist.md`
- Reference: `README.md`

**Step 1: Write the operations checklist in the report**

```markdown
Add placeholders for:
- internal support controls
- billing exception handling
- org and user intervention tools
- monitoring and incidents
- deployment baseline
- secrets and backups
- logs and alerting
- abuse and rate limiting
- data deletion and export posture
```

**Step 2: Gather admin and deployment evidence**

Run: `rg -n "billing|org|user|incident|monitoring|audit|backup|retention|production|hardening|deploy|postgres|cors|tls|websocket|rate" admin-ui/README.md admin-ui/Release_Checklist.md Docs/Published/Deployment/First_Time_Production_Setup.md Docs/Published/User_Guides/Server/Production_Hardening_Checklist.md README.md`  
Expected: the current operational story and hardening assumptions are visible in a single evidence pass.

**Step 3: Run focused admin-ui verification**

Run: `cd admin-ui && bun run build && bun run test`  
Expected: the internal admin console builds and its local test suite passes, or failures reveal support/ops instability.

**Step 4: Record operations and deployment findings**

```markdown
Capture:
- which support tasks are already possible in `admin-ui`
- which tasks still require direct backend or DB intervention
- whether the deployment docs are enough for an early hosted SaaS baseline
- the readiness color and the highest-priority gap for each section
```

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-18-saas-readiness-review-report.md
git commit -m "docs: capture admin and deployment readiness findings"
```

### Task 5: Score The Launch Readiness And Derive The Roadmap

**Files:**
- Modify: `Docs/Plans/2026-03-18-saas-readiness-review-report.md`
- Reference: `Docs/Plans/2026-03-18-saas-readiness-review-design.md`

**Step 1: Write the scoring checklist**

```markdown
For each top-level track, add a final scoring block:
- Exists
- Works end-to-end
- Safe for customer use
- Supportable in production
- Team-ready without major rewrite
```

**Step 2: Synthesize the ratings and roadmap**

Run: `sed -n '1,260p' Docs/Plans/2026-03-18-saas-readiness-review-report.md`  
Expected: all sections contain evidence-backed notes that can now be collapsed into `Immediate`, `Short-term`, `Later`, `Manual At Launch`, and `Must Automate Before Launch`.

**Step 3: Write the final verdict**

```markdown
Complete:
- Executive Verdict
- Launch recommendation
- Top blockers
- Immediate
- Short-term
- Later
- Manual At Launch
- Must Automate Before Launch
```

**Step 4: Final verification**

Run: `rg -n "TODO|TBD|placeholder" Docs/Plans/2026-03-18-saas-readiness-review-report.md`  
Expected: no unresolved placeholders remain in the final review report.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-18-saas-readiness-review-report.md
git commit -m "docs: finalize saas readiness review"
```
