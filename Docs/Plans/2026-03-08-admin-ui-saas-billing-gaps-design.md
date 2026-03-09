# Admin UI SaaS Production Readiness — Billing & Feature Gating Design

**Date**: 2026-03-08
**Status**: Approved
**Scope**: Admin UI feature gaps for multi-tenant SaaS with open-core self-hosted option

## Context

The admin UI is a Next.js 15 app with 33+ pages covering user/org/team management, RBAC, monitoring, audit logging, data ops, feature flags, budgets, usage tracking, and BYOK. It has solid foundations but is missing billing, subscription management, and structured feature gating needed to run as a SaaS.

### Deployment Model

- **Multi-tenant SaaS** — hosted, orgs as tenant boundary
- **Self-hosted open-core** — same codebase, feature-gated (no billing UI, all features enabled)

### Monetization Model

- Flat subscription tiers (Free, Pro, Enterprise)
- Usage-based overage (tokens beyond baseline included credits)
- Open-core: self-hosted is free, SaaS has premium features

### Scale Target

- Early access / beta (<50 orgs)

### Approach

Stripe-first: Stripe handles payment processing, invoicing, metered billing. Admin UI manages plans and subscriptions through backend endpoints that sync with Stripe.

## What Already Works

- Feature flags with org/user/global scopes (ready for open-core gating)
- Budget/quota system with soft/hard enforcement
- Usage tracking with token counts, provider breakdown, cost in USD
- Org/team/member hierarchy (multi-tenant structure)
- RBAC with permission matrix and `PermissionGuard` component
- Data ops: backups, exports, retention policies, DSR handling
- Audit logging with actor tracking
- JWT auth with httpOnly cookies, middleware caching, server-side proxy

## Gap Analysis

### Tier 1 — Must Have for Launch

| Gap | What's Missing | Builds On |
|-----|---------------|-----------|
| Subscription/Plan Management | No plan definitions, no way to assign plan to org, no plan limits enforcement | Budgets page quota concepts; feature flags org-level scoping |
| Billing Integration | No payment processing, invoice history, payment method management | BYOK tracks `total_cost_usd`; usage page tracks consumption |
| Tenant Onboarding Flow | No signup → org creation → plan selection → provisioning wizard | Org creation exists (name + slug only) |
| Feature Gating in UI | Feature flags exist but nothing checks them to hide/show SaaS-only features | `PermissionGuard` component pattern is reusable |
| Org-level Plan/Status | Org detail page has no plan tier, subscription status, usage summary | Org detail has BYOK, members, teams tabs |

### Tier 2 — Needed Shortly After Launch

| Gap | What's Missing |
|-----|---------------|
| Usage-to-Billing Pipeline | Usage data exists but no metered billing calculation (baseline vs. overage) |
| Email/Notification System | Monitoring alerts exist but no transactional email (welcome, invoice, usage warnings) |
| Self-Service Org Settings | Admins can manage orgs, but org owners can't self-manage plan, billing, invites |
| Tenant Data Export | Data ops exports audit logs and user lists, not org-scoped content data |
| Open-Core Feature Registry | No central definition of free vs. paid vs. enterprise features |

### Tier 3 — Enterprise / Growth Stage

| Gap | What's Missing |
|-----|---------------|
| SSO/SAML Configuration | No SSO setup page per org |
| Custom Domain / White-Label | No branding configuration |
| SLA / Support Tier Management | No support tier tracking |
| Multi-Region / Data Residency | No region selection or data residency controls |
| Advanced Analytics / Reporting | Usage page is operational, not BI-oriented |

## Design — Tier 1 Implementation

### New Pages

**1. Plans Management (`/plans`)**
- List all plans (Free, Pro, Enterprise) with pricing, included credits, feature set
- CRUD operations backed by Stripe Products/Prices
- Each plan defines: name, monthly price, included token credits, overage rate per 1K tokens, feature keys enabled
- Visual feature comparison matrix (reuse role comparison pattern from `/roles/matrix`)

**2. Subscriptions (`/subscriptions`)**
- List all active subscriptions across orgs
- Filter by plan, status (active, past_due, canceled, trialing)
- Quick actions: cancel, change plan, extend trial
- Links to org detail page

**3. Org Detail → Subscription Tab (new tab on existing `/organizations/[id]`)**
- Current plan, status, billing period
- Usage meter: tokens used / included, overage amount
- Payment method summary (last 4 digits, expiry)
- Invoice history (pulled from Stripe)
- Change plan / cancel subscription actions

**4. Onboarding Wizard (`/onboarding`)**
- Step 1: Create org (name, slug)
- Step 2: Select plan
- Step 3: Stripe Checkout redirect for payment (skip for Free tier)
- Step 4: Invite initial members
- Admin can trigger for any new customer, or share a link

**5. Feature Registry (`/feature-registry`)**
- Central mapping: plan tier → enabled feature keys
- Ties into existing feature flags system
- Shows which orgs have which features based on their plan
- "Free", "Pro", "Enterprise" columns with checkboxes per feature

### New Components

**`PlanGuard`** — mirrors `PermissionGuard` but checks org's plan tier
- Props: `requiredPlan: string | string[]`, `fallback?: ReactNode`
- Uses org context to resolve current plan
- Shows upgrade prompt as default fallback

**`PlanBadge`** — pill showing plan name with color coding (Free=gray, Pro=blue, Enterprise=purple)

**`UsageMeter`** — horizontal bar showing tokens used / included with overage zone
- Green under 80%, yellow 80-100%, red in overage
- Shows dollar amount for overage

**`UpgradePrompt`** — standardized CTA when a gated feature is accessed on a lower plan
- For non-admins: "Contact your admin to upgrade"
- For admins: direct "Upgrade Plan" button

**`InvoiceTable`** — paginated table of Stripe invoices
- Columns: date, amount, status (paid/open/void), PDF download link

**`OnboardingWizard`** — multi-step form component
- Step indicator, back/next navigation, validation per step
- Reuses existing form patterns (React Hook Form + Zod)

### API Client Additions

```typescript
// Plans
getPlans(params?)
createPlan(data)
updatePlan(planId, data)
deletePlan(planId)

// Subscriptions
getSubscriptions(params?)
getOrgSubscription(orgId)
createSubscription(orgId, data)  // triggers Stripe Checkout
updateSubscription(orgId, data)  // plan change
cancelSubscription(orgId)

// Usage/Billing
getOrgUsageSummary(orgId, period?)
getOrgInvoices(orgId, params?)

// Feature Registry
getFeatureRegistry()
updateFeatureRegistry(data)  // plan→features mapping

// Onboarding
createOnboardingSession(data)  // returns Stripe Checkout URL
```

### Modifications to Existing Pages

**Dashboard (`/`)**
- Add "Revenue" KPI card (MRR, active subscriptions count)
- Add "Plans Distribution" mini chart (pie/donut)
- Add "Past Due" to alerts banner
- All gated behind `BILLING_ENABLED`

**Organizations List (`/organizations`)**
- Add "Plan" column with `PlanBadge`
- Add plan filter dropdown
- Add "Subscription Status" column

**Organization Detail (`/organizations/[id]`)**
- New "Subscription" tab with `UsageMeter`, plan info, invoice history, change plan
- Existing "BYOK" tab gets note on whether keys count against org's usage

**Usage Page (`/usage`)**
- Add "Billing Period" context
- Add "Included vs. Overage" breakdown to Quota tab
- Add per-org usage ranking table

**Feature Flags Page (`/flags`)**
- Add "Managed by Feature Registry" badge on plan-gated flags
- Prevent manual override of registry-managed flags (or show warning)

**Budgets Page (`/budgets`)**
- Link budget limits to plan definitions where applicable
- Show "Plan Limit" vs. "Custom Override" distinction

### Data Flow

```
Admin creates Plan → API stores in DB + syncs to Stripe Product/Price
Admin onboards Org → Org created → Stripe Customer created → Checkout session
Stripe webhook → Backend updates subscription status in DB
Admin UI polls org subscription → shows current plan, usage, invoices
Usage tracking (existing) → Backend calculates overage against plan's included credits
Feature registry → Plan tier → feature flag keys → PlanGuard checks in UI
Self-hosted mode → No Stripe, feature registry returns all features enabled
```

### Navigation Changes

Add to the Governance section:
```
Governance
├── Security
├── Resource Governor
├── Budgets
├── Usage
├── Plans              ← NEW
├── Subscriptions      ← NEW
├── Feature Registry   ← NEW
├── Flags
├── Data Ops
```

### Open-Core Gating

Environment variable: `NEXT_PUBLIC_BILLING_ENABLED=true|false`

- **SaaS mode** (`true`): Plans, Subscriptions, Feature Registry pages visible. `PlanGuard` enforces limits. Onboarding includes plan selection + payment.
- **Self-hosted mode** (`false`): Those pages hidden from nav. `PlanGuard` always passes. Feature flags still work for admin-controlled gating but no billing enforcement.

Single codebase, no separate builds.

### Types

```typescript
interface Plan {
  id: string
  name: string
  stripe_product_id: string
  stripe_price_id: string
  monthly_price_cents: number
  included_token_credits: number
  overage_rate_per_1k_tokens_cents: number
  features: string[]  // feature flag keys
  is_default: boolean
  created_at: string
  updated_at: string
}

interface Subscription {
  id: string
  org_id: number
  plan_id: string
  stripe_subscription_id: string
  status: 'active' | 'past_due' | 'canceled' | 'trialing' | 'incomplete'
  current_period_start: string
  current_period_end: string
  trial_end?: string
  cancel_at?: string
}

interface OrgUsageSummary {
  org_id: string
  period_start: string
  period_end: string
  tokens_used: number
  tokens_included: number
  tokens_overage: number
  overage_cost_cents: number
  breakdown_by_provider: Record<string, number>
}

interface FeatureRegistryEntry {
  feature_key: string
  display_name: string
  description: string
  plans: string[]  // plan IDs that include this feature
  category: string
}
```

### Testing

- Unit tests for `PlanGuard`, `UsageMeter`, `PlanBadge`, `UpgradePrompt` components
- Page tests for Plans, Subscriptions, Feature Registry, Onboarding pages
- API client method tests (mock Stripe responses)
- Integration test: onboarding flow end-to-end with mocked Stripe Checkout
- Test `BILLING_ENABLED=false` mode hides all billing UI and `PlanGuard` passes through

### Scope Summary

- **5 new pages** (Plans, Subscriptions, Feature Registry, Onboarding, Org Subscription tab)
- **6 new components** (PlanGuard, PlanBadge, UsageMeter, UpgradePrompt, InvoiceTable, OnboardingWizard)
- **~12 new API client methods**
- **6 existing pages modified** (Dashboard, Org List, Org Detail, Usage, Flags, Budgets)
- **1 environment variable** for open-core gating
