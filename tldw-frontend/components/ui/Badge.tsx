import React from 'react';
import { cn } from '@/lib/utils';

type Variant = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'primary';

export function Badge({ children, variant = 'neutral', className }: { children: React.ReactNode; variant?: Variant; className?: string }) {
  const styles: Record<Variant, string> = {
    neutral: 'bg-gray-100 text-gray-800',
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800',
    info: 'bg-blue-100 text-blue-800',
    primary: 'bg-blue-600 text-white',
  };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', styles[variant], className)}>
      {children}
    </span>
  );
}
