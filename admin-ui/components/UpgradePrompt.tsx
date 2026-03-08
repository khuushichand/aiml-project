import Link from 'next/link';
import { ArrowUpCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

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
          <Link
            href="/plans"
            className="ml-4 inline-flex h-9 items-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
          >
            Upgrade Plan
          </Link>
        )}
      </AlertDescription>
    </Alert>
  );
}
