'use client';

import Link from 'next/link';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { AlertTriangle } from 'lucide-react';

type AlertSeverity = 'info' | 'warning' | 'error' | 'critical';

type DashboardAlertSummaryItem = {
  severity?: AlertSeverity;
};

type AlertsBannerProps = {
  alerts: DashboardAlertSummaryItem[];
};

export const summarizeAlertSeverities = (alerts: DashboardAlertSummaryItem[]) => {
  const summary = {
    critical: 0,
    warning: 0,
    info: 0,
  };

  alerts.forEach((alert) => {
    const severity = (alert.severity ?? 'info').toLowerCase();
    if (severity === 'critical' || severity === 'error') {
      summary.critical += 1;
      return;
    }
    if (severity === 'warning') {
      summary.warning += 1;
      return;
    }
    summary.info += 1;
  });

  return summary;
};

const getAlertToneClasses = (critical: number, warning: number) => {
  if (critical > 0) {
    return {
      container: 'border-red-200 bg-red-50',
      icon: 'text-red-700',
      description: 'text-red-900',
    };
  }
  if (warning > 0) {
    return {
      container: 'border-yellow-200 bg-yellow-50',
      icon: 'text-yellow-700',
      description: 'text-yellow-900',
    };
  }
  return {
    container: 'border-blue-200 bg-blue-50',
    icon: 'text-blue-700',
    description: 'text-blue-900',
  };
};

export const AlertsBanner = ({ alerts }: AlertsBannerProps) => {
  if (alerts.length <= 0) return null;

  const summary = summarizeAlertSeverities(alerts);
  const tone = getAlertToneClasses(summary.critical, summary.warning);
  const total = summary.critical + summary.warning + summary.info;

  return (
    <Alert className={cn('mb-6', tone.container)}>
      <AlertTriangle className={cn('h-4 w-4', tone.icon)} />
      <AlertDescription className={cn('space-y-2', tone.description)} aria-live="polite" aria-atomic="true">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={summary.critical > 0 ? 'destructive' : 'secondary'}>
            {summary.critical} critical
          </Badge>
          <Badge className="bg-yellow-500 text-white">
            {summary.warning} warning
          </Badge>
          <Badge className="bg-blue-500 text-white">
            {summary.info} info
          </Badge>
        </div>
        <div>
          {total} active alert{total !== 1 ? 's' : ''} require attention.{' '}
          <Link href="/monitoring" className="underline font-medium">View all</Link>
        </div>
      </AlertDescription>
    </Alert>
  );
};
