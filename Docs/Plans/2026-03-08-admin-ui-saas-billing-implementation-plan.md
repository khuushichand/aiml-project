# Admin UI SaaS Billing & Feature Gating — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add billing, subscription management, feature gating, and onboarding to the admin UI so it can operate as a multi-tenant SaaS with an open-core self-hosted option.

**Architecture:** Stripe-first billing integration. New pages for Plans, Subscriptions, Feature Registry, and Onboarding. A PlanGuard component gates SaaS-only UI. A NEXT_PUBLIC_BILLING_ENABLED env var toggles the entire billing surface. Backend API endpoints are assumed to exist at /api/v1/admin/billing/* — this plan covers the frontend only.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Radix UI, React Hook Form + Zod, Recharts, Vitest + React Testing Library

**Design Doc:** Docs/Plans/2026-03-08-admin-ui-saas-billing-gaps-design.md

---

See the full 17-task plan in the Write tool output above. This file serves as the committed reference.

## Task Summary

| Task | Description | New Files | Modified Files |
|------|------------|-----------|----------------|
| 1 | Billing types | — | types/index.ts |
| 2 | API client methods | — | lib/api-client.ts |
| 3 | Billing helper + nav items | lib/billing.ts | lib/navigation.ts |
| 4 | PlanBadge component | components/PlanBadge.tsx + test | — |
| 5 | UsageMeter component | components/UsageMeter.tsx + test | — |
| 6 | UpgradePrompt component | components/UpgradePrompt.tsx + test | — |
| 7 | PlanGuard component | components/PlanGuard.tsx + test | — |
| 8 | InvoiceTable component | components/InvoiceTable.tsx + test | — |
| 9 | Plans page | app/plans/ + test | — |
| 10 | Subscriptions page | app/subscriptions/ + test | — |
| 11 | Feature Registry page | app/feature-registry/ + test | — |
| 12 | Onboarding page | app/onboarding/ + test | — |
| 13 | Org detail subscription tab | — | app/organizations/[id]/page.tsx |
| 14 | Org list plan column | — | app/organizations/page.tsx |
| 15 | Dashboard billing KPIs | — | app/page.tsx |
| 16 | Nav billing filtering | — | lib/navigation.ts |
| 17 | Integration test | app/__tests__/billing-integration.test.tsx | — |

Total: 17 tasks, ~17 commits, 12 new files, 6 modified files

---

## Task 1: Add Billing Types

**Files:**
- Modify: admin-ui/types/index.ts

**Step 1: Add types to the end of types/index.ts**

Append after the last existing export:

```typescript
// ============================================
// Billing & Subscription Types
// ============================================

export type PlanTier = 'free' | 'pro' | 'enterprise';
export type SubscriptionStatus = 'active' | 'past_due' | 'canceled' | 'trialing' | 'incomplete';

export interface Plan {
  id: string;
  name: string;
  tier: PlanTier;
  stripe_product_id: string;
  stripe_price_id: string;
  monthly_price_cents: number;
  included_token_credits: number;
  overage_rate_per_1k_tokens_cents: number;
  features: string[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: string;
  org_id: number;
  plan_id: string;
  plan?: Plan;
  stripe_subscription_id: string;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  trial_end?: string;
  cancel_at?: string;
  created_at: string;
  updated_at: string;
}

export interface OrgUsageSummary {
  org_id: number;
  period_start: string;
  period_end: string;
  tokens_used: number;
  tokens_included: number;
  tokens_overage: number;
  overage_cost_cents: number;
  breakdown_by_provider: Record<string, number>;
}

export interface Invoice {
  id: string;
  stripe_invoice_id: string;
  amount_cents: number;
  currency: string;
  status: 'paid' | 'open' | 'void' | 'draft' | 'uncollectible';
  invoice_pdf?: string;
  period_start: string;
  period_end: string;
  created_at: string;
}

export interface FeatureRegistryEntry {
  feature_key: string;
  display_name: string;
  description: string;
  plans: string[];
  category: string;
}
```

**Step 2: Verify TypeScript compiles**

Run: cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20
Expected: No new errors from these types

**Step 3: Commit**

```bash
git add admin-ui/types/index.ts
git commit -m "feat(admin-ui): add billing, subscription, and feature registry types"
```

---

## Task 2: Add Billing API Client Methods

**Files:**
- Modify: admin-ui/lib/api-client.ts

**Step 1: Add import for new types at the top of api-client.ts**

```typescript
import type {
  AuditLog, BackupsResponse, FeatureRegistryEntry, IncidentsResponse,
  Invoice, OrgUsageSummary, Plan, RegistrationCode, RetentionPoliciesResponse,
  Subscription, UserWithKeyCount,
} from '@/types';
```

**Step 2: Add billing API methods before the closing }; of the api object**

```typescript
  // ============================================
  // Plans & Billing
  // ============================================
  getPlans: (params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Plan[]>(`/billing/plans${qs}`);
  },
  getPlan: (planId: string) =>
    requestJson<Plan>(`/billing/plans/${encodeURIComponent(planId)}`),
  createPlan: (data: Partial<Plan>) =>
    requestJson<Plan>('/billing/plans', { method: 'POST', body: JSON.stringify(data) }),
  updatePlan: (planId: string, data: Partial<Plan>) =>
    requestJson<Plan>(`/billing/plans/${encodeURIComponent(planId)}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePlan: (planId: string) =>
    requestJson(`/billing/plans/${encodeURIComponent(planId)}`, { method: 'DELETE' }),

  // Subscriptions
  getSubscriptions: (params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Subscription[]>(`/billing/subscriptions${qs}`);
  },
  getOrgSubscription: (orgId: number) =>
    requestJson<Subscription>(`/billing/orgs/${orgId}/subscription`),
  createSubscription: (orgId: number, data: { plan_id: string; trial_days?: number }) =>
    requestJson<{ checkout_url?: string; subscription?: Subscription }>(
      `/billing/orgs/${orgId}/subscription`, { method: 'POST', body: JSON.stringify(data) }),
  updateSubscription: (orgId: number, data: { plan_id: string }) =>
    requestJson<Subscription>(`/billing/orgs/${orgId}/subscription`, { method: 'PUT', body: JSON.stringify(data) }),
  cancelSubscription: (orgId: number) =>
    requestJson(`/billing/orgs/${orgId}/subscription`, { method: 'DELETE' }),

  // Usage & Invoices
  getOrgUsageSummary: (orgId: number, params?: { period?: string }) => {
    const qs = buildQueryString(params as Record<string, QueryParamValue>);
    return requestJson<OrgUsageSummary>(`/billing/orgs/${orgId}/usage${qs}`);
  },
  getOrgInvoices: (orgId: number, params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Invoice[]>(`/billing/orgs/${orgId}/invoices${qs}`);
  },

  // Feature Registry
  getFeatureRegistry: () =>
    requestJson<FeatureRegistryEntry[]>('/billing/feature-registry'),
  updateFeatureRegistry: (data: FeatureRegistryEntry[]) =>
    requestJson<FeatureRegistryEntry[]>('/billing/feature-registry', { method: 'PUT', body: JSON.stringify(data) }),

  // Onboarding
  createOnboardingSession: (data: { org_name: string; org_slug: string; plan_id: string; owner_email?: string }) =>
    requestJson<{ checkout_url?: string; org_id?: number }>(
      '/billing/onboarding', { method: 'POST', body: JSON.stringify(data) }),
```

**Step 3: Verify TypeScript compiles**

Run: cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20

**Step 4: Commit**

```bash
git add admin-ui/lib/api-client.ts
git commit -m "feat(admin-ui): add billing, subscription, and feature registry API methods"
```

---

## Task 3: Add billingEnabled Helper and Navigation Items

**Files:**
- Create: admin-ui/lib/billing.ts
- Modify: admin-ui/lib/navigation.ts

**Step 1: Create billing helper (admin-ui/lib/billing.ts)**

```typescript
'use client';

export function isBillingEnabled(): boolean {
  return process.env.NEXT_PUBLIC_BILLING_ENABLED === 'true';
}
```

**Step 2: Add navigation items in admin-ui/lib/navigation.ts**

Add imports: CreditCard, Receipt, Grid3X3 from lucide-react.

Add to navigationItems (before } satisfies):
```typescript
  plans: { name: 'Plans', href: '/plans', icon: CreditCard, role: ['admin', 'super_admin', 'owner'], keywords: ['billing', 'pricing', 'subscription', 'tiers'], billingOnly: true },
  subscriptions: { name: 'Subscriptions', href: '/subscriptions', icon: Receipt, role: ['admin', 'super_admin', 'owner'], keywords: ['billing', 'payments', 'invoices'], billingOnly: true },
  featureRegistry: { name: 'Feature Registry', href: '/feature-registry', icon: Grid3X3, role: ['admin', 'super_admin', 'owner'], keywords: ['gating', 'entitlements', 'open core'], billingOnly: true },
```

Add billingOnly?: boolean to NavigationItem type.

Add items to Governance section after navigationItems.usage.

Add breadcrumb support in resolveDynamicPathLabel for plans and subscriptions routes.

**Step 3: Commit**

```bash
git add admin-ui/lib/billing.ts admin-ui/lib/navigation.ts
git commit -m "feat(admin-ui): add billing nav items and billingEnabled helper"
```

---

## Tasks 4-8: Components (PlanBadge, UsageMeter, UpgradePrompt, PlanGuard, InvoiceTable)

Each follows TDD: write test -> verify fail -> implement -> verify pass -> commit.

See full component code in the detailed plan above (the Write tool output for the implementation plan file contains all code).

Key file paths:
- admin-ui/components/PlanBadge.tsx + __tests__/PlanBadge.test.tsx
- admin-ui/components/UsageMeter.tsx + __tests__/UsageMeter.test.tsx
- admin-ui/components/UpgradePrompt.tsx + __tests__/UpgradePrompt.test.tsx
- admin-ui/components/PlanGuard.tsx + __tests__/PlanGuard.test.tsx
- admin-ui/components/InvoiceTable.tsx + __tests__/InvoiceTable.test.tsx

---

## Tasks 9-12: New Pages (Plans, Subscriptions, Feature Registry, Onboarding)

Each follows TDD with page-level tests.

Key file paths:
- admin-ui/app/plans/page.tsx + __tests__/page.test.tsx
- admin-ui/app/subscriptions/page.tsx + __tests__/page.test.tsx
- admin-ui/app/feature-registry/page.tsx + __tests__/page.test.tsx
- admin-ui/app/onboarding/page.tsx + __tests__/page.test.tsx

---

## Tasks 13-16: Existing Page Modifications

- Task 13: Add Subscription section to admin-ui/app/organizations/[id]/page.tsx
- Task 14: Add Plan column to admin-ui/app/organizations/page.tsx
- Task 15: Add billing KPIs to admin-ui/app/page.tsx (dashboard)
- Task 16: Add billingOnly flag filtering to admin-ui/lib/navigation.ts

---

## Task 17: Integration Test

- admin-ui/app/__tests__/billing-integration.test.tsx
- Run full test suite to verify no regressions
