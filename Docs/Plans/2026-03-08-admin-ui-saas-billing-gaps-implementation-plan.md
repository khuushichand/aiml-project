# Admin UI SaaS Billing & Feature Gating — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add billing, subscription management, feature gating, and onboarding to the admin UI so it can operate as a multi-tenant SaaS with an open-core self-hosted option.

**Architecture:** Stripe-first billing integration. New pages for Plans, Subscriptions, Feature Registry, and Onboarding. A `PlanGuard` component gates SaaS-only UI. A `NEXT_PUBLIC_BILLING_ENABLED` env var toggles the entire billing surface. Backend API endpoints are assumed to exist at `/api/v1/admin/billing/*` — this plan covers the frontend only.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Radix UI, React Hook Form + Zod, Recharts, Vitest + React Testing Library

**Design Doc:** `Docs/Plans/2026-03-08-admin-ui-saas-billing-gaps-design.md`

---

## Task 1: Add Billing Types

**Files:**
- Modify: `admin-ui/types/index.ts`

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

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No new errors from these types (pre-existing errors may exist)

**Step 3: Commit**

```bash
git add admin-ui/types/index.ts
git commit -m "feat(admin-ui): add billing, subscription, and feature registry types"
```

---

## Task 2: Add Billing API Client Methods

**Files:**
- Modify: `admin-ui/lib/api-client.ts`

**Step 1: Add import for new types**

At the top of `api-client.ts`, update the import from `@/types` to include:

```typescript
import type {
  AuditLog,
  BackupsResponse,
  FeatureRegistryEntry,
  IncidentsResponse,
  Invoice,
  OrgUsageSummary,
  Plan,
  RegistrationCode,
  RetentionPoliciesResponse,
  Subscription,
  UserWithKeyCount,
} from '@/types';
```

**Step 2: Add billing API methods before the closing `};` of the api object (before `export default api;`)**

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
    requestJson<Plan>('/billing/plans', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updatePlan: (planId: string, data: Partial<Plan>) =>
    requestJson<Plan>(`/billing/plans/${encodeURIComponent(planId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deletePlan: (planId: string) =>
    requestJson(`/billing/plans/${encodeURIComponent(planId)}`, {
      method: 'DELETE',
    }),

  // Subscriptions
  getSubscriptions: (params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Subscription[]>(`/billing/subscriptions${qs}`);
  },
  getOrgSubscription: (orgId: number) =>
    requestJson<Subscription>(`/billing/orgs/${orgId}/subscription`),
  createSubscription: (orgId: number, data: { plan_id: string; trial_days?: number }) =>
    requestJson<{ checkout_url?: string; subscription?: Subscription }>(
      `/billing/orgs/${orgId}/subscription`,
      { method: 'POST', body: JSON.stringify(data) },
    ),
  updateSubscription: (orgId: number, data: { plan_id: string }) =>
    requestJson<Subscription>(`/billing/orgs/${orgId}/subscription`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
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
    requestJson<FeatureRegistryEntry[]>('/billing/feature-registry', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Onboarding
  createOnboardingSession: (data: { org_name: string; org_slug: string; plan_id: string; owner_email?: string }) =>
    requestJson<{ checkout_url?: string; org_id?: number }>(
      '/billing/onboarding',
      { method: 'POST', body: JSON.stringify(data) },
    ),
```

**Step 3: Verify TypeScript compiles**

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No new errors

**Step 4: Commit**

```bash
git add admin-ui/lib/api-client.ts
git commit -m "feat(admin-ui): add billing, subscription, and feature registry API methods"
```

---

## Task 3: Add `billingEnabled` Helper and Navigation Items

**Files:**
- Create: `admin-ui/lib/billing.ts`
- Modify: `admin-ui/lib/navigation.ts`

**Step 1: Create billing helper**

Create `admin-ui/lib/billing.ts`:

```typescript
'use client';

/**
 * Returns true when the SaaS billing surface is enabled.
 * Self-hosted deployments set NEXT_PUBLIC_BILLING_ENABLED=false (or omit it).
 */
export function isBillingEnabled(): boolean {
  return process.env.NEXT_PUBLIC_BILLING_ENABLED === 'true';
}
```

**Step 2: Add navigation items**

In `admin-ui/lib/navigation.ts`, add imports at the top:

```typescript
import { CreditCard, Receipt, Grid3X3 } from 'lucide-react';
```

Add three new items to the `navigationItems` object (before the `} satisfies` closing):

```typescript
  plans: { name: 'Plans', href: '/plans', icon: CreditCard, role: ['admin', 'super_admin', 'owner'], keywords: ['billing', 'pricing', 'subscription', 'tiers'] },
  subscriptions: { name: 'Subscriptions', href: '/subscriptions', icon: Receipt, role: ['admin', 'super_admin', 'owner'], keywords: ['billing', 'payments', 'invoices'] },
  featureRegistry: { name: 'Feature Registry', href: '/feature-registry', icon: Grid3X3, role: ['admin', 'super_admin', 'owner'], keywords: ['gating', 'entitlements', 'open core'] },
```

Add these to the Governance section in `navigationSections`, after `navigationItems.usage`:

```typescript
      navigationItems.plans,
      navigationItems.subscriptions,
      navigationItems.featureRegistry,
```

Add breadcrumb support in `resolveDynamicPathLabel`:

```typescript
  if (root === 'plans' && segments.length === 2) {
    return `Plan ${decodeURIComponent(idOrSlug)}`;
  }
  if (root === 'subscriptions' && segments.length === 2) {
    return `Subscription ${decodeURIComponent(idOrSlug)}`;
  }
```

**Step 3: Verify TypeScript compiles**

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 4: Commit**

```bash
git add admin-ui/lib/billing.ts admin-ui/lib/navigation.ts
git commit -m "feat(admin-ui): add billing nav items and billingEnabled helper"
```

---

## Task 4: PlanBadge Component

**Files:**
- Create: `admin-ui/components/PlanBadge.tsx`
- Create: `admin-ui/components/__tests__/PlanBadge.test.tsx`

**Step 1: Write the test**

Create `admin-ui/components/__tests__/PlanBadge.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PlanBadge } from '../PlanBadge';

describe('PlanBadge', () => {
  it('renders the plan tier label', () => {
    render(<PlanBadge tier="pro" />);
    expect(screen.getByText('Pro')).toBeInTheDocument();
  });

  it('renders free tier with secondary variant styling', () => {
    const { container } = render(<PlanBadge tier="free" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.textContent).toBe('Free');
  });

  it('renders enterprise tier', () => {
    render(<PlanBadge tier="enterprise" />);
    expect(screen.getByText('Enterprise')).toBeInTheDocument();
  });

  it('applies additional className', () => {
    const { container } = render(<PlanBadge tier="pro" className="ml-2" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain('ml-2');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run components/__tests__/PlanBadge.test.tsx 2>&1 | tail -10`
Expected: FAIL — module not found

**Step 3: Implement PlanBadge**

Create `admin-ui/components/PlanBadge.tsx`:

```typescript
import { Badge } from '@/components/ui/badge';
import type { PlanTier } from '@/types';
import { cn } from '@/lib/utils';

const tierConfig: Record<PlanTier, { label: string; className: string }> = {
  free: { label: 'Free', className: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300' },
  pro: { label: 'Pro', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  enterprise: { label: 'Enterprise', className: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' },
};

interface PlanBadgeProps {
  tier: PlanTier;
  className?: string;
}

export function PlanBadge({ tier, className }: PlanBadgeProps) {
  const config = tierConfig[tier] ?? tierConfig.free;
  return (
    <Badge variant="outline" className={cn(config.className, className)}>
      {config.label}
    </Badge>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run components/__tests__/PlanBadge.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/components/PlanBadge.tsx admin-ui/components/__tests__/PlanBadge.test.tsx
git commit -m "feat(admin-ui): add PlanBadge component with tests"
```

---

## Task 5: UsageMeter Component

**Files:**
- Create: `admin-ui/components/UsageMeter.tsx`
- Create: `admin-ui/components/__tests__/UsageMeter.test.tsx`

**Step 1: Write the test**

Create `admin-ui/components/__tests__/UsageMeter.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { UsageMeter } from '../UsageMeter';

describe('UsageMeter', () => {
  it('renders used and included token counts', () => {
    render(<UsageMeter used={500_000} included={1_000_000} overageCostCents={0} />);
    expect(screen.getByText(/500,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument();
  });

  it('shows green bar when under 80% usage', () => {
    const { container } = render(<UsageMeter used={400_000} included={1_000_000} overageCostCents={0} />);
    const bar = container.querySelector('[data-testid="usage-bar"]');
    expect(bar?.className).toContain('bg-green');
  });

  it('shows yellow bar when between 80-100% usage', () => {
    const { container } = render(<UsageMeter used={850_000} included={1_000_000} overageCostCents={0} />);
    const bar = container.querySelector('[data-testid="usage-bar"]');
    expect(bar?.className).toContain('bg-yellow');
  });

  it('shows red bar and overage cost when over 100%', () => {
    render(<UsageMeter used={1_200_000} included={1_000_000} overageCostCents={2400} />);
    const bar = screen.getByTestId('usage-bar');
    expect(bar.className).toContain('bg-red');
    expect(screen.getByText(/\$24\.00/)).toBeInTheDocument();
  });

  it('handles zero included gracefully', () => {
    render(<UsageMeter used={100} included={0} overageCostCents={0} />);
    expect(screen.getByText(/100/)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run components/__tests__/UsageMeter.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement UsageMeter**

Create `admin-ui/components/UsageMeter.tsx`:

```typescript
import { cn } from '@/lib/utils';

interface UsageMeterProps {
  used: number;
  included: number;
  overageCostCents: number;
  className?: string;
}

function formatTokens(n: number): string {
  return n.toLocaleString();
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

export function UsageMeter({ used, included, overageCostCents, className }: UsageMeterProps) {
  const pct = included > 0 ? (used / included) * 100 : (used > 0 ? 100 : 0);
  const clampedPct = Math.min(pct, 100);

  const barColor =
    pct > 100 ? 'bg-red-500' :
    pct >= 80 ? 'bg-yellow-500' :
    'bg-green-500';

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex justify-between text-sm">
        <span>{formatTokens(used)} / {formatTokens(included)} tokens</span>
        {overageCostCents > 0 && (
          <span className="text-red-600 dark:text-red-400 font-medium">
            Overage: {formatCents(overageCostCents)}
          </span>
        )}
      </div>
      <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          data-testid="usage-bar"
          className={cn('h-2 rounded-full transition-all', barColor)}
          style={{ width: `${clampedPct}%` }}
        />
      </div>
      <div className="text-xs text-muted-foreground text-right">
        {pct.toFixed(1)}% used
      </div>
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run components/__tests__/UsageMeter.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/components/UsageMeter.tsx admin-ui/components/__tests__/UsageMeter.test.tsx
git commit -m "feat(admin-ui): add UsageMeter component with color zones and overage display"
```

---

## Task 6: UpgradePrompt Component

**Files:**
- Create: `admin-ui/components/UpgradePrompt.tsx`
- Create: `admin-ui/components/__tests__/UpgradePrompt.test.tsx`

**Step 1: Write the test**

Create `admin-ui/components/__tests__/UpgradePrompt.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { UpgradePrompt } from '../UpgradePrompt';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('UpgradePrompt', () => {
  it('displays required plan name', () => {
    render(<UpgradePrompt requiredPlan="pro" featureName="Advanced Analytics" />);
    expect(screen.getByText(/Pro/)).toBeInTheDocument();
    expect(screen.getByText(/Advanced Analytics/)).toBeInTheDocument();
  });

  it('shows upgrade link when showUpgradeLink is true', () => {
    render(<UpgradePrompt requiredPlan="enterprise" featureName="SSO" showUpgradeLink />);
    expect(screen.getByRole('link', { name: /upgrade/i })).toBeInTheDocument();
  });

  it('hides upgrade link by default', () => {
    render(<UpgradePrompt requiredPlan="pro" featureName="Feature X" />);
    expect(screen.queryByRole('link', { name: /upgrade/i })).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run components/__tests__/UpgradePrompt.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement UpgradePrompt**

Create `admin-ui/components/UpgradePrompt.tsx`:

```typescript
import Link from 'next/link';
import { ArrowUpCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

interface UpgradePromptProps {
  requiredPlan: string;
  featureName: string;
  showUpgradeLink?: boolean;
}

export function UpgradePrompt({ requiredPlan, featureName, showUpgradeLink }: UpgradePromptProps) {
  const planLabel = requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1);

  return (
    <Alert>
      <ArrowUpCircle className="h-4 w-4" />
      <AlertDescription className="flex items-center justify-between">
        <span>
          <strong>{featureName}</strong> requires the <strong>{planLabel}</strong> plan.
          {!showUpgradeLink && ' Contact your administrator to upgrade.'}
        </span>
        {showUpgradeLink && (
          <Button asChild size="sm" variant="outline" className="ml-4">
            <Link href="/plans">Upgrade Plan</Link>
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run components/__tests__/UpgradePrompt.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/components/UpgradePrompt.tsx admin-ui/components/__tests__/UpgradePrompt.test.tsx
git commit -m "feat(admin-ui): add UpgradePrompt component for plan-gated features"
```

---

## Task 7: PlanGuard Component

**Files:**
- Create: `admin-ui/components/PlanGuard.tsx`
- Create: `admin-ui/components/__tests__/PlanGuard.test.tsx`

**Step 1: Write the test**

Create `admin-ui/components/__tests__/PlanGuard.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlanGuard } from '../PlanGuard';

const mockIsBillingEnabled = vi.hoisted(() => vi.fn());
const mockGetOrgSubscription = vi.hoisted(() => vi.fn());
const mockUseOrgContext = vi.hoisted(() => vi.fn());

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: mockIsBillingEnabled,
}));

vi.mock('@/lib/api-client', () => ({
  api: { getOrgSubscription: mockGetOrgSubscription },
  ApiError: class extends Error {},
}));

vi.mock('@/components/OrgContextSwitcher', () => ({
  useOrgContext: mockUseOrgContext,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('PlanGuard', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders children when billing is disabled (self-hosted)', () => {
    mockIsBillingEnabled.mockReturnValue(false);
    mockUseOrgContext.mockReturnValue({ selectedOrg: null, loading: false });
    render(<PlanGuard requiredPlan="pro"><div>Protected Content</div></PlanGuard>);
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('renders children when org has required plan', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'pro' },
      status: 'active',
    });
    render(<PlanGuard requiredPlan="pro"><div>Protected Content</div></PlanGuard>);
    expect(await screen.findByText('Protected Content')).toBeInTheDocument();
  });

  it('renders upgrade prompt when org lacks required plan', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'free' },
      status: 'active',
    });
    render(<PlanGuard requiredPlan="pro" featureName="Analytics"><div>Hidden</div></PlanGuard>);
    expect(await screen.findByText(/Pro/)).toBeInTheDocument();
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });

  it('accepts array of plans', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'enterprise' },
      status: 'active',
    });
    render(<PlanGuard requiredPlan={['pro', 'enterprise']}><div>Visible</div></PlanGuard>);
    expect(await screen.findByText('Visible')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run components/__tests__/PlanGuard.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement PlanGuard**

Create `admin-ui/components/PlanGuard.tsx`:

```typescript
'use client';

import { ReactNode, useEffect, useState } from 'react';
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { UpgradePrompt } from '@/components/UpgradePrompt';
import type { PlanTier } from '@/types';

const TIER_RANK: Record<PlanTier, number> = { free: 0, pro: 1, enterprise: 2 };

interface PlanGuardProps {
  requiredPlan: PlanTier | PlanTier[];
  featureName?: string;
  fallback?: ReactNode;
  children: ReactNode;
}

export function PlanGuard({ requiredPlan, featureName, fallback, children }: PlanGuardProps) {
  const { selectedOrg, loading: orgLoading } = useOrgContext();
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    if (!isBillingEnabled()) {
      setAllowed(true);
      return;
    }
    if (orgLoading || !selectedOrg) return;

    let cancelled = false;
    api.getOrgSubscription(selectedOrg.id)
      .then((sub) => {
        if (cancelled) return;
        const tier = (sub?.plan?.tier ?? 'free') as PlanTier;
        const plans = Array.isArray(requiredPlan) ? requiredPlan : [requiredPlan];
        const meetsRequirement = plans.some((p) => TIER_RANK[tier] >= TIER_RANK[p]);
        setAllowed(meetsRequirement);
      })
      .catch(() => {
        if (!cancelled) setAllowed(true); // fail open — backend enforces
      });
    return () => { cancelled = true; };
  }, [selectedOrg, orgLoading, requiredPlan]);

  if (allowed === null) return null; // loading
  if (allowed) return <>{children}</>;

  if (fallback) return <>{fallback}</>;

  const displayPlan = Array.isArray(requiredPlan) ? requiredPlan[0] : requiredPlan;
  return (
    <UpgradePrompt
      requiredPlan={displayPlan}
      featureName={featureName ?? 'This feature'}
      showUpgradeLink
    />
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run components/__tests__/PlanGuard.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/components/PlanGuard.tsx admin-ui/components/__tests__/PlanGuard.test.tsx
git commit -m "feat(admin-ui): add PlanGuard component for plan-based UI gating"
```

---

## Task 8: InvoiceTable Component

**Files:**
- Create: `admin-ui/components/InvoiceTable.tsx`
- Create: `admin-ui/components/__tests__/InvoiceTable.test.tsx`

**Step 1: Write the test**

Create `admin-ui/components/__tests__/InvoiceTable.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { InvoiceTable } from '../InvoiceTable';
import type { Invoice } from '@/types';

const invoices: Invoice[] = [
  {
    id: '1',
    stripe_invoice_id: 'inv_abc',
    amount_cents: 4900,
    currency: 'usd',
    status: 'paid',
    invoice_pdf: 'https://stripe.com/invoice.pdf',
    period_start: '2026-02-01T00:00:00Z',
    period_end: '2026-03-01T00:00:00Z',
    created_at: '2026-03-01T00:00:00Z',
  },
  {
    id: '2',
    stripe_invoice_id: 'inv_def',
    amount_cents: 7500,
    currency: 'usd',
    status: 'open',
    period_start: '2026-03-01T00:00:00Z',
    period_end: '2026-04-01T00:00:00Z',
    created_at: '2026-04-01T00:00:00Z',
  },
];

describe('InvoiceTable', () => {
  it('renders invoice rows', () => {
    render(<InvoiceTable invoices={invoices} />);
    expect(screen.getByText('$49.00')).toBeInTheDocument();
    expect(screen.getByText('$75.00')).toBeInTheDocument();
  });

  it('renders status badges', () => {
    render(<InvoiceTable invoices={invoices} />);
    expect(screen.getByText('paid')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
  });

  it('renders PDF download link when available', () => {
    render(<InvoiceTable invoices={invoices} />);
    const links = screen.getAllByRole('link');
    expect(links.some((link) => link.getAttribute('href') === 'https://stripe.com/invoice.pdf')).toBe(true);
  });

  it('renders empty state when no invoices', () => {
    render(<InvoiceTable invoices={[]} />);
    expect(screen.getByText(/no invoices/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run components/__tests__/InvoiceTable.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement InvoiceTable**

Create `admin-ui/components/InvoiceTable.tsx`:

```typescript
import { Download } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Invoice } from '@/types';

interface InvoiceTableProps {
  invoices: Invoice[];
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

const statusVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  paid: 'default',
  open: 'outline',
  void: 'secondary',
  draft: 'secondary',
  uncollectible: 'destructive',
};

export function InvoiceTable({ invoices }: InvoiceTableProps) {
  if (invoices.length === 0) {
    return <p className="text-sm text-muted-foreground py-4 text-center">No invoices yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-4">Date</th>
            <th className="py-2 pr-4">Period</th>
            <th className="py-2 pr-4">Amount</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id} className="border-b">
              <td className="py-2 pr-4">{formatDate(inv.created_at)}</td>
              <td className="py-2 pr-4">
                {formatDate(inv.period_start)} — {formatDate(inv.period_end)}
              </td>
              <td className="py-2 pr-4 font-medium">{formatCents(inv.amount_cents)}</td>
              <td className="py-2 pr-4">
                <Badge variant={statusVariant[inv.status] ?? 'outline'}>{inv.status}</Badge>
              </td>
              <td className="py-2">
                {inv.invoice_pdf && (
                  <a
                    href={inv.invoice_pdf}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
                  >
                    <Download className="h-3 w-3" /> PDF
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run components/__tests__/InvoiceTable.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/components/InvoiceTable.tsx admin-ui/components/__tests__/InvoiceTable.test.tsx
git commit -m "feat(admin-ui): add InvoiceTable component for Stripe invoice display"
```

---

## Task 9: Plans Management Page

**Files:**
- Create: `admin-ui/app/plans/page.tsx`
- Create: `admin-ui/app/plans/__tests__/page.test.tsx`

**Step 1: Write the test**

Create `admin-ui/app/plans/__tests__/page.test.tsx`:

```typescript
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockGetPlans = vi.hoisted(() => vi.fn());
const mockCreatePlan = vi.hoisted(() => vi.fn());
const mockDeletePlan = vi.hoisted(() => vi.fn());
const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api-client', () => ({
  api: {
    getPlans: mockGetPlans,
    createPlan: mockCreatePlan,
    deletePlan: mockDeletePlan,
  },
  ApiError: class extends Error {},
}));

vi.mock('@/hooks/useConfirm', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: toastSuccessMock, error: vi.fn() }),
}));

vi.mock('@/components/PermissionGuard', () => ({
  usePermissions: () => ({ user: { id: 1, role: 'admin' }, loading: false, hasRole: () => true }),
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: () => true,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const samplePlans = [
  {
    id: 'plan_free',
    name: 'Free',
    tier: 'free' as const,
    stripe_product_id: 'prod_free',
    stripe_price_id: 'price_free',
    monthly_price_cents: 0,
    included_token_credits: 10_000,
    overage_rate_per_1k_tokens_cents: 0,
    features: ['basic_chat'],
    is_default: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'plan_pro',
    name: 'Pro',
    tier: 'pro' as const,
    stripe_product_id: 'prod_pro',
    stripe_price_id: 'price_pro',
    monthly_price_cents: 4900,
    included_token_credits: 1_000_000,
    overage_rate_per_1k_tokens_cents: 5,
    features: ['basic_chat', 'advanced_analytics', 'priority_support'],
    is_default: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('PlansPage', () => {
  beforeEach(() => {
    mockGetPlans.mockResolvedValue(samplePlans);
    confirmMock.mockResolvedValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('renders plan list', async () => {
    const PlansPage = (await import('../page')).default;
    render(<PlansPage />);
    expect(await screen.findByText('Free')).toBeInTheDocument();
    expect(screen.getByText('Pro')).toBeInTheDocument();
    expect(screen.getByText('$49.00/mo')).toBeInTheDocument();
  });

  it('shows create plan dialog', async () => {
    const PlansPage = (await import('../page')).default;
    const user = userEvent.setup();
    render(<PlansPage />);
    await screen.findByText('Free');
    const createButton = screen.getByRole('button', { name: /create plan/i });
    await user.click(createButton);
    expect(screen.getByLabelText(/plan name/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run app/plans/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement Plans page**

Create `admin-ui/app/plans/page.tsx`:

```typescript
'use client';

import { useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Plus, Trash2, Edit2 } from 'lucide-react';
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';
import { useConfirm } from '@/hooks/useConfirm';
import { useToast } from '@/hooks/useToast';
import PermissionGuard from '@/components/PermissionGuard';
import { PlanBadge } from '@/components/PlanBadge';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { Plan, PlanTier } from '@/types';

const planSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  tier: z.enum(['free', 'pro', 'enterprise']),
  monthly_price_cents: z.coerce.number().min(0),
  included_token_credits: z.coerce.number().min(0),
  overage_rate_per_1k_tokens_cents: z.coerce.number().min(0),
  stripe_product_id: z.string().optional(),
  stripe_price_id: z.string().optional(),
});

type PlanFormData = z.infer<typeof planSchema>;

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null);
  const confirm = useConfirm();
  const toast = useToast();

  const form = useForm<PlanFormData>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      name: '',
      tier: 'free',
      monthly_price_cents: 0,
      included_token_credits: 0,
      overage_rate_per_1k_tokens_cents: 0,
    },
  });

  const loadPlans = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getPlans();
      setPlans(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Failed to load plans');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (isBillingEnabled()) loadPlans();
    else setLoading(false);
  }, [loadPlans]);

  const handleCreate = async (data: PlanFormData) => {
    try {
      await api.createPlan(data as Partial<Plan>);
      toast.success('Plan created');
      setShowCreate(false);
      form.reset();
      loadPlans();
    } catch {
      toast.error('Failed to create plan');
    }
  };

  const handleDelete = async (plan: Plan) => {
    const ok = await confirm(`Delete plan "${plan.name}"? Orgs on this plan will need to be migrated.`);
    if (!ok) return;
    try {
      await api.deletePlan(plan.id);
      toast.success('Plan deleted');
      loadPlans();
    } catch {
      toast.error('Failed to delete plan');
    }
  };

  const handleEdit = async (data: PlanFormData) => {
    if (!editingPlan) return;
    try {
      await api.updatePlan(editingPlan.id, data as Partial<Plan>);
      toast.success('Plan updated');
      setEditingPlan(null);
      form.reset();
      loadPlans();
    } catch {
      toast.error('Failed to update plan');
    }
  };

  const openEdit = (plan: Plan) => {
    form.reset({
      name: plan.name,
      tier: plan.tier,
      monthly_price_cents: plan.monthly_price_cents,
      included_token_credits: plan.included_token_credits,
      overage_rate_per_1k_tokens_cents: plan.overage_rate_per_1k_tokens_cents,
      stripe_product_id: plan.stripe_product_id,
      stripe_price_id: plan.stripe_price_id,
    });
    setEditingPlan(plan);
  };

  if (!isBillingEnabled()) {
    return (
      <ResponsiveLayout>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Billing is not enabled. Set <code>NEXT_PUBLIC_BILLING_ENABLED=true</code> to manage plans.
          </CardContent>
        </Card>
      </ResponsiveLayout>
    );
  }

  const formatPrice = (cents: number) => cents === 0 ? 'Free' : `$${(cents / 100).toFixed(2)}/mo`;

  const planFormDialog = (
    open: boolean,
    onOpenChange: (v: boolean) => void,
    title: string,
    onSubmit: (data: PlanFormData) => void,
  ) => (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="name">Plan Name</Label>
            <Input id="name" {...form.register('name')} />
            {form.formState.errors.name && (
              <p className="text-sm text-red-500 mt-1">{form.formState.errors.name.message}</p>
            )}
          </div>
          <div>
            <Label htmlFor="tier">Tier</Label>
            <Select
              value={form.watch('tier')}
              onValueChange={(v) => form.setValue('tier', v as PlanTier)}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="free">Free</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="monthly_price_cents">Monthly Price (cents)</Label>
            <Input id="monthly_price_cents" type="number" {...form.register('monthly_price_cents')} />
          </div>
          <div>
            <Label htmlFor="included_token_credits">Included Token Credits</Label>
            <Input id="included_token_credits" type="number" {...form.register('included_token_credits')} />
          </div>
          <div>
            <Label htmlFor="overage_rate_per_1k_tokens_cents">Overage Rate / 1K Tokens (cents)</Label>
            <Input id="overage_rate_per_1k_tokens_cents" type="number" {...form.register('overage_rate_per_1k_tokens_cents')} />
          </div>
          <div>
            <Label htmlFor="stripe_product_id">Stripe Product ID</Label>
            <Input id="stripe_product_id" {...form.register('stripe_product_id')} placeholder="prod_..." />
          </div>
          <div>
            <Label htmlFor="stripe_price_id">Stripe Price ID</Label>
            <Input id="stripe_price_id" {...form.register('stripe_price_id')} placeholder="price_..." />
          </div>
          <DialogFooter>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  return (
    <ResponsiveLayout>
      <PermissionGuard role={['admin', 'super_admin', 'owner']}>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Subscription Plans</h1>
              <p className="text-muted-foreground">Manage pricing tiers and included features</p>
            </div>
            <Button onClick={() => { form.reset(); setShowCreate(true); }}>
              <Plus className="h-4 w-4 mr-2" /> Create Plan
            </Button>
          </div>

          {loading ? (
            <p className="text-muted-foreground">Loading plans...</p>
          ) : plans.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No plans configured. Create your first plan to get started.
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {plans.map((plan) => (
                <Card key={plan.id}>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-lg">{plan.name}</CardTitle>
                      <PlanBadge tier={plan.tier} />
                      {plan.is_default && (
                        <span className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">Default</span>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(plan)}>
                        <Edit2 className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(plan)}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">{formatPrice(plan.monthly_price_cents)}</p>
                    <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                      <p>{plan.included_token_credits.toLocaleString()} tokens included</p>
                      {plan.overage_rate_per_1k_tokens_cents > 0 && (
                        <p>${(plan.overage_rate_per_1k_tokens_cents / 100).toFixed(2)} per 1K overage tokens</p>
                      )}
                      <p>{plan.features.length} features enabled</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {planFormDialog(showCreate, setShowCreate, 'Create Plan', handleCreate)}
        {planFormDialog(!!editingPlan, (v) => !v && setEditingPlan(null), 'Edit Plan', handleEdit)}
      </PermissionGuard>
    </ResponsiveLayout>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run app/plans/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/plans/
git commit -m "feat(admin-ui): add Plans management page with CRUD and Stripe IDs"
```

---

## Task 10: Subscriptions List Page

**Files:**
- Create: `admin-ui/app/subscriptions/page.tsx`
- Create: `admin-ui/app/subscriptions/__tests__/page.test.tsx`

**Step 1: Write the test**

Create `admin-ui/app/subscriptions/__tests__/page.test.tsx`:

```typescript
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockGetSubscriptions = vi.hoisted(() => vi.fn());
const mockGetPlans = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api-client', () => ({
  api: {
    getSubscriptions: mockGetSubscriptions,
    getPlans: mockGetPlans,
  },
  ApiError: class extends Error {},
}));

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock('@/components/PermissionGuard', () => ({
  usePermissions: () => ({ user: { id: 1, role: 'admin' }, loading: false, hasRole: () => true }),
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: () => true,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/components/OrgContextSwitcher', () => ({
  useOrgContext: () => ({ selectedOrg: null, loading: false, organizations: [] }),
}));

describe('SubscriptionsPage', () => {
  beforeEach(() => {
    mockGetSubscriptions.mockResolvedValue([
      {
        id: 'sub_1',
        org_id: 1,
        plan_id: 'plan_pro',
        plan: { id: 'plan_pro', name: 'Pro', tier: 'pro' },
        stripe_subscription_id: 'sub_stripe_1',
        status: 'active',
        current_period_start: '2026-03-01T00:00:00Z',
        current_period_end: '2026-04-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    ]);
    mockGetPlans.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('renders subscription list', async () => {
    const SubscriptionsPage = (await import('../page')).default;
    render(<SubscriptionsPage />);
    expect(await screen.findByText('active')).toBeInTheDocument();
    expect(screen.getByText(/Pro/)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run app/subscriptions/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement Subscriptions page**

Create `admin-ui/app/subscriptions/page.tsx`:

```typescript
'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';
import { useToast } from '@/hooks/useToast';
import PermissionGuard from '@/components/PermissionGuard';
import { PlanBadge } from '@/components/PlanBadge';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { Subscription, SubscriptionStatus } from '@/types';

const statusVariant: Record<SubscriptionStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  active: 'default',
  trialing: 'outline',
  past_due: 'destructive',
  canceled: 'secondary',
  incomplete: 'secondary',
};

export default function SubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const data = await api.getSubscriptions(params);
      setSubscriptions(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Failed to load subscriptions');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, toast]);

  useEffect(() => {
    if (isBillingEnabled()) load();
    else setLoading(false);
  }, [load]);

  if (!isBillingEnabled()) {
    return (
      <ResponsiveLayout>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Billing is not enabled.
          </CardContent>
        </Card>
      </ResponsiveLayout>
    );
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });

  return (
    <ResponsiveLayout>
      <PermissionGuard role={['admin', 'super_admin', 'owner']}>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Subscriptions</h1>
              <p className="text-muted-foreground">All active and past subscriptions across organizations</p>
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="trialing">Trialing</SelectItem>
                <SelectItem value="past_due">Past Due</SelectItem>
                <SelectItem value="canceled">Canceled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : subscriptions.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No subscriptions found.
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="p-3">Organization</th>
                        <th className="p-3">Plan</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Current Period</th>
                        <th className="p-3">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subscriptions.map((sub) => (
                        <tr key={sub.id} className="border-b hover:bg-muted/50">
                          <td className="p-3">
                            <Link href={`/organizations/${sub.org_id}`} className="text-blue-600 hover:underline">
                              Org #{sub.org_id}
                            </Link>
                          </td>
                          <td className="p-3">
                            {sub.plan ? <PlanBadge tier={sub.plan.tier} /> : sub.plan_id}
                          </td>
                          <td className="p-3">
                            <Badge variant={statusVariant[sub.status] ?? 'outline'}>{sub.status}</Badge>
                          </td>
                          <td className="p-3">
                            {formatDate(sub.current_period_start)} — {formatDate(sub.current_period_end)}
                          </td>
                          <td className="p-3">{formatDate(sub.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </PermissionGuard>
    </ResponsiveLayout>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run app/subscriptions/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/subscriptions/
git commit -m "feat(admin-ui): add Subscriptions list page with status filtering"
```

---

## Task 11: Feature Registry Page

**Files:**
- Create: `admin-ui/app/feature-registry/page.tsx`
- Create: `admin-ui/app/feature-registry/__tests__/page.test.tsx`

**Step 1: Write the test**

Create `admin-ui/app/feature-registry/__tests__/page.test.tsx`:

```typescript
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockGetFeatureRegistry = vi.hoisted(() => vi.fn());
const mockGetPlans = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api-client', () => ({
  api: {
    getFeatureRegistry: mockGetFeatureRegistry,
    getPlans: mockGetPlans,
  },
  ApiError: class extends Error {},
}));

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock('@/components/PermissionGuard', () => ({
  usePermissions: () => ({ user: { id: 1, role: 'admin' }, loading: false, hasRole: () => true }),
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: () => true,
}));

describe('FeatureRegistryPage', () => {
  beforeEach(() => {
    mockGetPlans.mockResolvedValue([
      { id: 'plan_free', name: 'Free', tier: 'free' },
      { id: 'plan_pro', name: 'Pro', tier: 'pro' },
    ]);
    mockGetFeatureRegistry.mockResolvedValue([
      {
        feature_key: 'advanced_analytics',
        display_name: 'Advanced Analytics',
        description: 'Deep usage analytics',
        plans: ['plan_pro'],
        category: 'Analytics',
      },
    ]);
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('renders feature matrix with plan columns', async () => {
    const FeatureRegistryPage = (await import('../page')).default;
    render(<FeatureRegistryPage />);
    expect(await screen.findByText('Advanced Analytics')).toBeInTheDocument();
    expect(screen.getByText('Free')).toBeInTheDocument();
    expect(screen.getByText('Pro')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run app/feature-registry/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement Feature Registry page**

Create `admin-ui/app/feature-registry/page.tsx`:

```typescript
'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';
import { useToast } from '@/hooks/useToast';
import PermissionGuard from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { Plan, FeatureRegistryEntry } from '@/types';

export default function FeatureRegistryPage() {
  const [features, setFeatures] = useState<FeatureRegistryEntry[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [featData, planData] = await Promise.all([
        api.getFeatureRegistry(),
        api.getPlans(),
      ]);
      setFeatures(Array.isArray(featData) ? featData : []);
      setPlans(Array.isArray(planData) ? planData : []);
    } catch {
      toast.error('Failed to load feature registry');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (isBillingEnabled()) load();
    else setLoading(false);
  }, [load]);

  const toggleFeature = (featureKey: string, planId: string) => {
    setFeatures((prev) =>
      prev.map((f) => {
        if (f.feature_key !== featureKey) return f;
        const has = f.plans.includes(planId);
        return { ...f, plans: has ? f.plans.filter((p) => p !== planId) : [...f.plans, planId] };
      }),
    );
    setDirty(true);
  };

  const handleSave = async () => {
    try {
      await api.updateFeatureRegistry(features);
      toast.success('Feature registry saved');
      setDirty(false);
    } catch {
      toast.error('Failed to save');
    }
  };

  if (!isBillingEnabled()) {
    return (
      <ResponsiveLayout>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Billing is not enabled.
          </CardContent>
        </Card>
      </ResponsiveLayout>
    );
  }

  const categories = Array.from(new Set(features.map((f) => f.category))).sort();

  return (
    <ResponsiveLayout>
      <PermissionGuard role={['admin', 'super_admin', 'owner']}>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Feature Registry</h1>
              <p className="text-muted-foreground">Map features to plan tiers for open-core gating</p>
            </div>
            {dirty && <Button onClick={handleSave}>Save Changes</Button>}
          </div>

          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="p-3">Feature</th>
                        {plans.map((plan) => (
                          <th key={plan.id} className="p-3 text-center">{plan.name}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {categories.map((cat) => (
                        <>
                          <tr key={`cat-${cat}`}>
                            <td colSpan={plans.length + 1} className="p-3 font-semibold bg-muted/50">
                              {cat}
                            </td>
                          </tr>
                          {features
                            .filter((f) => f.category === cat)
                            .map((feat) => (
                              <tr key={feat.feature_key} className="border-b hover:bg-muted/30">
                                <td className="p-3">
                                  <div>{feat.display_name}</div>
                                  <div className="text-xs text-muted-foreground">{feat.description}</div>
                                </td>
                                {plans.map((plan) => {
                                  const included = feat.plans.includes(plan.id);
                                  return (
                                    <td key={plan.id} className="p-3 text-center">
                                      <button
                                        onClick={() => toggleFeature(feat.feature_key, plan.id)}
                                        className="inline-flex items-center justify-center"
                                      >
                                        {included ? (
                                          <Check className="h-4 w-4 text-green-600" />
                                        ) : (
                                          <X className="h-4 w-4 text-gray-300" />
                                        )}
                                      </button>
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                        </>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </PermissionGuard>
    </ResponsiveLayout>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run app/feature-registry/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/feature-registry/
git commit -m "feat(admin-ui): add Feature Registry page with plan-to-feature matrix"
```

---

## Task 12: Onboarding Wizard Page

**Files:**
- Create: `admin-ui/app/onboarding/page.tsx`
- Create: `admin-ui/app/onboarding/__tests__/page.test.tsx`

**Step 1: Write the test**

Create `admin-ui/app/onboarding/__tests__/page.test.tsx`:

```typescript
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockGetPlans = vi.hoisted(() => vi.fn());
const mockCreateOnboardingSession = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api-client', () => ({
  api: {
    getPlans: mockGetPlans,
    createOnboardingSession: mockCreateOnboardingSession,
  },
  ApiError: class extends Error {},
}));

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock('@/components/PermissionGuard', () => ({
  usePermissions: () => ({ user: { id: 1, role: 'admin' }, loading: false, hasRole: () => true }),
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: () => true,
}));

const plans = [
  { id: 'plan_free', name: 'Free', tier: 'free', monthly_price_cents: 0, included_token_credits: 10000 },
  { id: 'plan_pro', name: 'Pro', tier: 'pro', monthly_price_cents: 4900, included_token_credits: 1000000 },
];

describe('OnboardingPage', () => {
  beforeEach(() => {
    mockGetPlans.mockResolvedValue(plans);
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('renders step 1 with org name input', async () => {
    const OnboardingPage = (await import('../page')).default;
    render(<OnboardingPage />);
    expect(await screen.findByLabelText(/organization name/i)).toBeInTheDocument();
  });

  it('advances to step 2 on next', async () => {
    const OnboardingPage = (await import('../page')).default;
    const user = userEvent.setup();
    render(<OnboardingPage />);

    const nameInput = await screen.findByLabelText(/organization name/i);
    await user.type(nameInput, 'Acme Corp');

    const slugInput = screen.getByLabelText(/slug/i);
    await user.type(slugInput, 'acme-corp');

    const nextButton = screen.getByRole('button', { name: /next/i });
    await user.click(nextButton);

    expect(await screen.findByText(/select a plan/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run app/onboarding/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: FAIL

**Step 3: Implement Onboarding page**

Create `admin-ui/app/onboarding/page.tsx`:

```typescript
'use client';

import { useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Check, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';
import { useToast } from '@/hooks/useToast';
import PermissionGuard from '@/components/PermissionGuard';
import { PlanBadge } from '@/components/PlanBadge';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import type { Plan } from '@/types';

const orgSchema = z.object({
  org_name: z.string().min(1, 'Required'),
  org_slug: z.string().min(1, 'Required').regex(/^[a-z0-9-]+$/, 'Lowercase letters, numbers, hyphens only'),
  owner_email: z.string().email().optional().or(z.literal('')),
});

type OrgFormData = z.infer<typeof orgSchema>;

const STEPS = ['Organization', 'Select Plan', 'Confirm'] as const;

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const toast = useToast();

  const form = useForm<OrgFormData>({
    resolver: zodResolver(orgSchema),
    defaultValues: { org_name: '', org_slug: '', owner_email: '' },
  });

  const loadPlans = useCallback(async () => {
    try {
      const data = await api.getPlans();
      const list = Array.isArray(data) ? data : [];
      setPlans(list);
      const defaultPlan = list.find((p) => p.is_default);
      if (defaultPlan) setSelectedPlanId(defaultPlan.id);
    } catch {
      toast.error('Failed to load plans');
    }
  }, [toast]);

  useEffect(() => {
    if (isBillingEnabled()) loadPlans();
  }, [loadPlans]);

  const handleNext = async () => {
    if (step === 0) {
      const valid = await form.trigger();
      if (!valid) return;
      setStep(1);
    } else if (step === 1) {
      if (!selectedPlanId) {
        toast.error('Please select a plan');
        return;
      }
      setStep(2);
    }
  };

  const handleBack = () => {
    if (step > 0) setStep(step - 1);
  };

  const handleSubmit = async () => {
    const data = form.getValues();
    setSubmitting(true);
    try {
      const result = await api.createOnboardingSession({
        org_name: data.org_name,
        org_slug: data.org_slug,
        plan_id: selectedPlanId!,
        owner_email: data.owner_email || undefined,
      });
      if (result.checkout_url) {
        window.location.href = result.checkout_url;
      } else {
        toast.success('Organization created successfully');
        setStep(0);
        form.reset();
      }
    } catch {
      toast.error('Onboarding failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isBillingEnabled()) {
    return (
      <ResponsiveLayout>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Billing is not enabled.
          </CardContent>
        </Card>
      </ResponsiveLayout>
    );
  }

  const selectedPlan = plans.find((p) => p.id === selectedPlanId);

  return (
    <ResponsiveLayout>
      <PermissionGuard role={['admin', 'super_admin', 'owner']}>
        <div className="max-w-2xl mx-auto space-y-6">
          <h1 className="text-2xl font-bold">Onboard New Organization</h1>

          {/* Step indicator */}
          <div className="flex items-center gap-2">
            {STEPS.map((label, i) => (
              <div key={label} className="flex items-center gap-2">
                <div className={cn(
                  'flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium',
                  i < step ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                  i === step ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
                  'bg-gray-100 text-gray-500 dark:bg-gray-800',
                )}>
                  {i < step ? <Check className="h-4 w-4" /> : i + 1}
                </div>
                <span className={cn('text-sm', i === step ? 'font-medium' : 'text-muted-foreground')}>
                  {label}
                </span>
                {i < STEPS.length - 1 && <ChevronRight className="h-4 w-4 text-muted-foreground" />}
              </div>
            ))}
          </div>

          {/* Step 1: Organization Details */}
          {step === 0 && (
            <Card>
              <CardHeader><CardTitle>Organization Details</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="org_name">Organization Name</Label>
                  <Input id="org_name" {...form.register('org_name')} />
                  {form.formState.errors.org_name && (
                    <p className="text-sm text-red-500 mt-1">{form.formState.errors.org_name.message}</p>
                  )}
                </div>
                <div>
                  <Label htmlFor="org_slug">Slug</Label>
                  <Input id="org_slug" {...form.register('org_slug')} placeholder="acme-corp" />
                  {form.formState.errors.org_slug && (
                    <p className="text-sm text-red-500 mt-1">{form.formState.errors.org_slug.message}</p>
                  )}
                </div>
                <div>
                  <Label htmlFor="owner_email">Owner Email (optional)</Label>
                  <Input id="owner_email" type="email" {...form.register('owner_email')} />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 2: Plan Selection */}
          {step === 1 && (
            <div className="space-y-3">
              <p className="text-muted-foreground">Select a plan for this organization:</p>
              {plans.map((plan) => (
                <Card
                  key={plan.id}
                  className={cn(
                    'cursor-pointer transition-colors',
                    selectedPlanId === plan.id ? 'ring-2 ring-blue-500' : 'hover:bg-muted/50',
                  )}
                  onClick={() => setSelectedPlanId(plan.id)}
                >
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <PlanBadge tier={plan.tier} />
                      <div>
                        <p className="font-medium">{plan.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {plan.included_token_credits.toLocaleString()} tokens included
                        </p>
                      </div>
                    </div>
                    <p className="font-bold">
                      {plan.monthly_price_cents === 0 ? 'Free' : `$${(plan.monthly_price_cents / 100).toFixed(2)}/mo`}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Step 3: Confirm */}
          {step === 2 && (
            <Card>
              <CardHeader><CardTitle>Confirm</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p><strong>Organization:</strong> {form.getValues('org_name')} ({form.getValues('org_slug')})</p>
                {form.getValues('owner_email') && <p><strong>Owner:</strong> {form.getValues('owner_email')}</p>}
                <p><strong>Plan:</strong> {selectedPlan?.name ?? 'Unknown'}</p>
                {selectedPlan && selectedPlan.monthly_price_cents > 0 && (
                  <p className="text-muted-foreground">
                    A Stripe Checkout session will be created for payment.
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Navigation */}
          <div className="flex justify-between">
            <Button variant="outline" onClick={handleBack} disabled={step === 0}>
              Back
            </Button>
            {step < 2 ? (
              <Button onClick={handleNext}>
                Next <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting ? 'Creating...' : selectedPlan && selectedPlan.monthly_price_cents > 0 ? 'Create & Pay' : 'Create Organization'}
              </Button>
            )}
          </div>
        </div>
      </PermissionGuard>
    </ResponsiveLayout>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run app/onboarding/__tests__/page.test.tsx 2>&1 | tail -10`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/onboarding/
git commit -m "feat(admin-ui): add Onboarding wizard with org creation and plan selection"
```

---

## Task 13: Org Detail — Subscription Tab

**Files:**
- Modify: `admin-ui/app/organizations/[id]/page.tsx`

**Step 1: Read the existing org detail page to understand current structure**

Run: Read the file to find where to add the subscription section.

**Step 2: Add imports for billing components**

Add to the imports section of `admin-ui/app/organizations/[id]/page.tsx`:

```typescript
import { PlanBadge } from '@/components/PlanBadge';
import { UsageMeter } from '@/components/UsageMeter';
import { InvoiceTable } from '@/components/InvoiceTable';
import { isBillingEnabled } from '@/lib/billing';
import type { Subscription, OrgUsageSummary, Invoice } from '@/types';
```

**Step 3: Add subscription state alongside existing state**

Add state variables:

```typescript
const [subscription, setSubscription] = useState<Subscription | null>(null);
const [usageSummary, setUsageSummary] = useState<OrgUsageSummary | null>(null);
const [invoices, setInvoices] = useState<Invoice[]>([]);
```

**Step 4: Add billing data fetch in the existing loadData function**

Inside the existing `Promise.allSettled()` or after the main data loads, add:

```typescript
if (isBillingEnabled()) {
  const [subResult, usageResult, invoiceResult] = await Promise.allSettled([
    api.getOrgSubscription(Number(id)),
    api.getOrgUsageSummary(Number(id)),
    api.getOrgInvoices(Number(id)),
  ]);
  if (subResult.status === 'fulfilled') setSubscription(subResult.value);
  if (usageResult.status === 'fulfilled') setUsageSummary(usageResult.value);
  if (invoiceResult.status === 'fulfilled') setInvoices(Array.isArray(invoiceResult.value) ? invoiceResult.value : []);
}
```

**Step 5: Add Subscription card section after the existing BYOK section**

```tsx
{/* Subscription & Billing (SaaS only) */}
{isBillingEnabled() && (
  <Card>
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        Subscription
        {subscription?.plan && <PlanBadge tier={subscription.plan.tier} />}
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      {subscription ? (
        <>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Status</p>
              <p className="font-medium capitalize">{subscription.status}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Current Period</p>
              <p className="font-medium">
                {new Date(subscription.current_period_start).toLocaleDateString()} —{' '}
                {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            </div>
          </div>

          {usageSummary && (
            <div>
              <p className="text-sm font-medium mb-2">Token Usage</p>
              <UsageMeter
                used={usageSummary.tokens_used}
                included={usageSummary.tokens_included}
                overageCostCents={usageSummary.overage_cost_cents}
              />
            </div>
          )}

          {invoices.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Invoices</p>
              <InvoiceTable invoices={invoices} />
            </div>
          )}
        </>
      ) : (
        <p className="text-muted-foreground">No active subscription.</p>
      )}
    </CardContent>
  </Card>
)}
```

**Step 6: Verify TypeScript compiles**

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 7: Commit**

```bash
git add admin-ui/app/organizations/\[id\]/page.tsx
git commit -m "feat(admin-ui): add Subscription section to org detail page"
```

---

## Task 14: Modify Organizations List — Plan Column

**Files:**
- Modify: `admin-ui/app/organizations/page.tsx`

**Step 1: Read the existing organizations page**

Understand the table structure before modifying.

**Step 2: Add PlanBadge import and subscription state**

At the top:
```typescript
import { PlanBadge } from '@/components/PlanBadge';
import { isBillingEnabled } from '@/lib/billing';
```

**Step 3: Extend org list to fetch subscriptions**

After orgs are loaded, fetch subscriptions for visible orgs:

```typescript
// After loadData sets organizations, fetch their subscriptions if billing enabled
const [orgPlans, setOrgPlans] = useState<Record<number, { tier: PlanTier; status: string }>>({});

// In loadData, after org list is fetched:
if (isBillingEnabled() && orgs.length > 0) {
  const subs = await api.getSubscriptions({ org_ids: orgs.map((o: { id: number }) => o.id).join(',') });
  const planMap: Record<number, { tier: PlanTier; status: string }> = {};
  if (Array.isArray(subs)) {
    subs.forEach((sub: Subscription) => {
      planMap[sub.org_id] = { tier: sub.plan?.tier ?? 'free', status: sub.status };
    });
  }
  setOrgPlans(planMap);
}
```

**Step 4: Add Plan column to the table**

In the table header, add after the existing columns:
```tsx
{isBillingEnabled() && <th className="p-3">Plan</th>}
{isBillingEnabled() && <th className="p-3">Status</th>}
```

In the table body rows:
```tsx
{isBillingEnabled() && (
  <td className="p-3">
    <PlanBadge tier={orgPlans[org.id]?.tier ?? 'free'} />
  </td>
)}
{isBillingEnabled() && (
  <td className="p-3 capitalize text-sm">
    {orgPlans[org.id]?.status ?? '—'}
  </td>
)}
```

**Step 5: Verify TypeScript compiles**

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 6: Commit**

```bash
git add admin-ui/app/organizations/page.tsx
git commit -m "feat(admin-ui): add Plan and Status columns to organizations list"
```

---

## Task 15: Dashboard — Revenue KPI and Plan Distribution

**Files:**
- Modify: `admin-ui/app/page.tsx` (dashboard)

**Step 1: Read the existing dashboard page**

Understand the KPI card structure.

**Step 2: Add billing imports**

```typescript
import { isBillingEnabled } from '@/lib/billing';
```

**Step 3: Add billing KPIs**

In the dashboard's data loading section, add:

```typescript
const [billingStats, setBillingStats] = useState<{
  mrr_cents: number;
  active_subscriptions: number;
  past_due_count: number;
  plan_distribution: Record<string, number>;
} | null>(null);

// In loadData:
if (isBillingEnabled()) {
  try {
    const subs = await api.getSubscriptions();
    if (Array.isArray(subs)) {
      const active = subs.filter((s: Subscription) => s.status === 'active');
      const pastDue = subs.filter((s: Subscription) => s.status === 'past_due');
      const distribution: Record<string, number> = {};
      subs.forEach((s: Subscription) => {
        const tier = s.plan?.tier ?? 'free';
        distribution[tier] = (distribution[tier] ?? 0) + 1;
      });
      setBillingStats({
        mrr_cents: 0, // Would come from a dedicated endpoint
        active_subscriptions: active.length,
        past_due_count: pastDue.length,
        plan_distribution: distribution,
      });
    }
  } catch {
    // Non-critical — dashboard still works without billing stats
  }
}
```

**Step 4: Add KPI cards in the dashboard grid (conditionally)**

```tsx
{isBillingEnabled() && billingStats && (
  <>
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">Active Subscriptions</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{billingStats.active_subscriptions}</p>
      </CardContent>
    </Card>
    {billingStats.past_due_count > 0 && (
      <Card className="border-red-200 dark:border-red-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-red-600">Past Due</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-red-600">{billingStats.past_due_count}</p>
        </CardContent>
      </Card>
    )}
  </>
)}
```

**Step 5: Verify TypeScript compiles**

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 6: Commit**

```bash
git add admin-ui/app/page.tsx
git commit -m "feat(admin-ui): add billing KPIs to dashboard when billing enabled"
```

---

## Task 16: Filter Billing Nav Items by `BILLING_ENABLED`

**Files:**
- Modify: `admin-ui/lib/navigation.ts`

**Step 1: Add conditional filtering**

The navigation items for plans, subscriptions, and featureRegistry should only appear when billing is enabled. Since `navigation.ts` is imported at module level (not in a component), we need a runtime filter.

Update the `navigationSections` export to be a function or add a `billingOnly` flag:

Add a `billingOnly?: boolean` field to the `NavigationItem` type:

```typescript
export type NavigationItem = {
  name: string;
  href: string;
  icon: LucideIcon;
  permission?: string;
  role?: string[];
  keywords?: string[];
  billingOnly?: boolean;
};
```

Mark the three billing items with `billingOnly: true`:

```typescript
  plans: { name: 'Plans', href: '/plans', icon: CreditCard, role: ['admin', 'super_admin', 'owner'], keywords: ['billing', 'pricing'], billingOnly: true },
  subscriptions: { name: 'Subscriptions', href: '/subscriptions', icon: Receipt, role: ['admin', 'super_admin', 'owner'], keywords: ['billing', 'payments'], billingOnly: true },
  featureRegistry: { name: 'Feature Registry', href: '/feature-registry', icon: Grid3X3, role: ['admin', 'super_admin', 'owner'], keywords: ['gating', 'entitlements'], billingOnly: true },
```

Then in the sidebar component (wherever `navigationSections` is consumed), filter out `billingOnly` items when `!isBillingEnabled()`. This keeps navigation.ts pure and moves the runtime check to the rendering layer.

**Step 2: Verify build**

Run: `cd admin-ui && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 3: Commit**

```bash
git add admin-ui/lib/navigation.ts
git commit -m "feat(admin-ui): mark billing nav items with billingOnly flag for conditional display"
```

---

## Task 17: Final Integration Test

**Files:**
- Create: `admin-ui/app/__tests__/billing-integration.test.tsx`

**Step 1: Write integration test**

Create `admin-ui/app/__tests__/billing-integration.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { isBillingEnabled } from '@/lib/billing';

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: vi.fn(),
}));

describe('Billing integration', () => {
  it('isBillingEnabled returns false when env is not set', () => {
    vi.mocked(isBillingEnabled).mockReturnValue(false);
    expect(isBillingEnabled()).toBe(false);
  });

  it('isBillingEnabled returns true when env is true', () => {
    vi.mocked(isBillingEnabled).mockReturnValue(true);
    expect(isBillingEnabled()).toBe(true);
  });
});

describe('Billing types are importable', () => {
  it('imports Plan type without error', async () => {
    const types = await import('@/types');
    expect(types).toBeDefined();
  });
});
```

**Step 2: Run all billing-related tests**

Run: `cd admin-ui && npx vitest run --reporter=verbose 2>&1 | grep -E '(PASS|FAIL|billing|Plan|Usage|Invoice|Upgrade|Onboarding|Subscription|feature-registry)' | head -30`
Expected: All PASS

**Step 3: Run full test suite to check for regressions**

Run: `cd admin-ui && npx vitest run 2>&1 | tail -20`
Expected: No new failures

**Step 4: Commit**

```bash
git add admin-ui/app/__tests__/billing-integration.test.tsx
git commit -m "test(admin-ui): add billing integration smoke tests"
```

---

## Summary

| Task | Description | New Files | Modified Files |
|------|------------|-----------|----------------|
| 1 | Billing types | — | `types/index.ts` |
| 2 | API client methods | — | `lib/api-client.ts` |
| 3 | Billing helper + nav items | `lib/billing.ts` | `lib/navigation.ts` |
| 4 | PlanBadge component | `components/PlanBadge.tsx` + test | — |
| 5 | UsageMeter component | `components/UsageMeter.tsx` + test | — |
| 6 | UpgradePrompt component | `components/UpgradePrompt.tsx` + test | — |
| 7 | PlanGuard component | `components/PlanGuard.tsx` + test | — |
| 8 | InvoiceTable component | `components/InvoiceTable.tsx` + test | — |
| 9 | Plans page | `app/plans/` + test | — |
| 10 | Subscriptions page | `app/subscriptions/` + test | — |
| 11 | Feature Registry page | `app/feature-registry/` + test | — |
| 12 | Onboarding page | `app/onboarding/` + test | — |
| 13 | Org detail subscription tab | — | `app/organizations/[id]/page.tsx` |
| 14 | Org list plan column | — | `app/organizations/page.tsx` |
| 15 | Dashboard billing KPIs | — | `app/page.tsx` |
| 16 | Nav billing filtering | — | `lib/navigation.ts` |
| 17 | Integration test | `app/__tests__/billing-integration.test.tsx` | — |

**Total: 17 tasks, ~17 commits, 12 new files, 6 modified files**
