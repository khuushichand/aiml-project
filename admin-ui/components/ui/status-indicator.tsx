'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export type StatusType =
  | 'healthy'
  | 'warning'
  | 'critical'
  | 'active'
  | 'inactive'
  | 'online'
  | 'offline'
  | 'degraded'
  | 'down'
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'expired';

export interface StatusIndicatorProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusType;
  showDot?: boolean;
  showText?: boolean;
  size?: 'sm' | 'md';
}

const statusConfig: Record<StatusType, { dot: string; text: string; label: string }> = {
  healthy: { dot: 'bg-green-500', text: 'text-green-600 dark:text-green-400', label: 'Healthy' },
  warning: { dot: 'bg-yellow-500', text: 'text-yellow-600 dark:text-yellow-400', label: 'Warning' },
  critical: { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400', label: 'Critical' },
  active: { dot: 'bg-green-500', text: 'text-green-600 dark:text-green-400', label: 'Active' },
  inactive: { dot: 'bg-gray-400', text: 'text-gray-500 dark:text-gray-400', label: 'Inactive' },
  online: { dot: 'bg-green-500', text: 'text-green-600 dark:text-green-400', label: 'Online' },
  offline: { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400', label: 'Offline' },
  degraded: { dot: 'bg-yellow-500', text: 'text-yellow-600 dark:text-yellow-400', label: 'Degraded' },
  down: { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400', label: 'Down' },
  pending: { dot: 'bg-blue-500', text: 'text-blue-600 dark:text-blue-400', label: 'Pending' },
  running: { dot: 'bg-blue-500 animate-pulse', text: 'text-blue-600 dark:text-blue-400', label: 'Running' },
  completed: { dot: 'bg-green-500', text: 'text-green-600 dark:text-green-400', label: 'Completed' },
  failed: { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400', label: 'Failed' },
  expired: { dot: 'bg-gray-400', text: 'text-gray-500 dark:text-gray-400', label: 'Expired' },
};

const StatusIndicator = React.forwardRef<HTMLSpanElement, StatusIndicatorProps>(
  ({ status, showDot = true, showText = true, size = 'md', className, ...props }, ref) => {
    const config = statusConfig[status] || statusConfig.inactive;
    const dotSize = size === 'sm' ? 'h-1.5 w-1.5' : 'h-2 w-2';
    const textSize = size === 'sm' ? 'text-xs' : 'text-sm';

    return (
      <span
        ref={ref}
        className={cn('inline-flex items-center gap-1.5', className)}
        role="status"
        aria-label={config.label}
        {...props}
      >
        {showDot && (
          <span
            className={cn('rounded-full shrink-0', dotSize, config.dot)}
            aria-hidden="true"
          />
        )}
        {showText && (
          <span className={cn('font-medium', textSize, config.text)}>
            {config.label}
          </span>
        )}
      </span>
    );
  }
);

StatusIndicator.displayName = 'StatusIndicator';

export { StatusIndicator };
