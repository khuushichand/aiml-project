'use client';

import type { ReactNode } from 'react';
import { Label } from '@/components/ui/label';

type FieldProps = {
  id: string;
  label: string;
  children: ReactNode;
};

export const Field = ({ id, label, children }: FieldProps) => (
  <div className="space-y-1">
    <Label htmlFor={id} className="text-xs uppercase text-muted-foreground">
      {label}
    </Label>
    {children}
  </div>
);
