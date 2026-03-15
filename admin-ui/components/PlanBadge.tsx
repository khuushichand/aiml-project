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
