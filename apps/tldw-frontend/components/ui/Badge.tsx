import React from 'react';
import { cn } from '@web/lib/utils';

type Variant = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'primary';

export function Badge({ children, variant = 'neutral', className }: { children: React.ReactNode; variant?: Variant; className?: string }) {
  const styles: Record<Variant, string> = {
    neutral: 'bg-surface text-text',
    success: 'bg-success/10 text-success',
    warning: 'bg-warn/10 text-warn',
    danger: 'bg-danger/10 text-danger',
    info: 'bg-primary/10 text-primary',
    primary: 'bg-primary text-white',
  };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', styles[variant], className)}>
      {children}
    </span>
  );
}
