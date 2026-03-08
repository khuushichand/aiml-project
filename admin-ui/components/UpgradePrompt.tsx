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
