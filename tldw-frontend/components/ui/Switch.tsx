import React from 'react';
import { cn } from '@/lib/utils';

export function Switch({ checked, onChange, label, className }: { checked: boolean; onChange: (v: boolean) => void; label?: string; className?: string }) {
  return (
    <label className={cn('inline-flex cursor-pointer items-center space-x-3', className)}>
      <span className="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-300 transition-colors" aria-checked={checked} role="switch" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onChange(!checked); }}>
        <span className={cn('inline-block h-5 w-5 transform rounded-full bg-white transition', checked ? 'translate-x-6' : 'translate-x-1')} />
        <input type="checkbox" className="sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      </span>
      {label && <span className="text-sm text-gray-700">{label}</span>}
    </label>
  );
}
