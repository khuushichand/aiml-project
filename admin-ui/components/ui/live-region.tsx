'use client';

import type { ReactNode } from 'react';

interface LiveRegionProps {
  children: ReactNode;
  /** aria-live politeness level. Default: 'polite' */
  politeness?: 'polite' | 'assertive' | 'off';
  className?: string;
}

/**
 * Wrapper that announces dynamic content changes to screen readers.
 * Use around loading indicators, status messages, and content that
 * changes asynchronously.
 */
export function LiveRegion({
  children,
  politeness = 'polite',
  className,
}: LiveRegionProps) {
  const statusRole = politeness === 'polite' ? 'status' : undefined;
  return (
    <div
      role={statusRole}
      aria-live={politeness}
      aria-atomic="true"
      className={className}
    >
      {children}
    </div>
  );
}
