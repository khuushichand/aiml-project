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
  const billingEnabled = isBillingEnabled();
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    if (!billingEnabled) {
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
        if (!cancelled) setAllowed(false);
      });
    return () => { cancelled = true; };
  }, [billingEnabled, selectedOrg, orgLoading, requiredPlan]);

  if (!billingEnabled) {
    return <>{children}</>;
  }

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
