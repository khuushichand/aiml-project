import React from 'react';
import { cn } from '@web/lib/utils';

export interface TabItem {
  key: string;
  label: string;
}

export function Tabs({ items, value, onChange, className }: { items: readonly TabItem[]; value: string; onChange: (k: string) => void; className?: string }) {
  return (
    <div className={cn('border-b border-border', className)}>
      <nav className="-mb-px flex space-x-6" aria-label="Tabs">
        {items.map((item) => {
          const active = item.key === value;
          return (
            <button
              key={item.key}
              className={cn(
                'whitespace-nowrap border-b-2 px-1 py-2 text-sm font-medium',
                active ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text'
              )}
              onClick={() => onChange(item.key)}
            >
              {item.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
