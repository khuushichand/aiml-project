import React from 'react';
import { cn } from '@/lib/utils';

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded bg-gray-200', className)} />;
}

export function LineSkeleton({ width = '100%', height = 12, className }: { width?: string | number; height?: number; className?: string }) {
  return <div className={cn('animate-pulse rounded bg-gray-200', className)} style={{ width, height }} />;
}

export function CardSkeleton() {
  return (
    <div className="rounded border p-3">
      <LineSkeleton width="60%" height={14} />
      <div className="mt-2 space-y-2">
        <LineSkeleton width="40%" />
        <LineSkeleton width="90%" />
        <LineSkeleton width="75%" />
      </div>
    </div>
  );
}
