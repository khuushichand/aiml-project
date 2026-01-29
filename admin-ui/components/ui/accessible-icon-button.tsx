'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button, type ButtonProps } from './button';
import type { LucideIcon } from 'lucide-react';

export interface AccessibleIconButtonProps extends Omit<ButtonProps, 'children'> {
  /** The Lucide icon component to render */
  icon: LucideIcon;
  /** Required accessible label - becomes aria-label and title */
  label: string;
  /** Optional icon size class (default: h-4 w-4) */
  iconClassName?: string;
}

const AccessibleIconButton = React.forwardRef<HTMLButtonElement, AccessibleIconButtonProps>(
  ({ icon: Icon, label, iconClassName, className, size = 'icon', ...props }, ref) => {
    return (
      <Button
        ref={ref}
        size={size}
        className={className}
        aria-label={label}
        title={label}
        {...props}
      >
        <Icon className={cn('h-4 w-4', iconClassName)} aria-hidden="true" />
      </Button>
    );
  }
);

AccessibleIconButton.displayName = 'AccessibleIconButton';

export { AccessibleIconButton };
