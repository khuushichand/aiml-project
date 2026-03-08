import { cn } from '@/lib/utils';
import { formatCents } from '@/lib/formatters';

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
