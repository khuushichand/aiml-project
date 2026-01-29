'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { LucideIcon, Inbox } from 'lucide-react';
import { Button } from './button';

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: 'default' | 'outline' | 'secondary';
}

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Icon to display (defaults to Inbox) */
  icon?: LucideIcon;
  /** Main heading text */
  title: string;
  /** Description text below the title */
  description?: string;
  /** Action buttons to display */
  actions?: EmptyStateAction[];
}

const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ icon: Icon = Inbox, title, description, actions, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'flex flex-col items-center justify-center py-12 px-4 text-center',
          className
        )}
        role="status"
        aria-live="polite"
        {...props}
      >
        <div className="rounded-full bg-muted p-4 mb-4">
          <Icon className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        </div>
        <h3 className="text-lg font-semibold mb-1">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground max-w-sm mb-4">{description}</p>
        )}
        {actions && actions.length > 0 && (
          <div className="flex flex-wrap gap-2 justify-center">
            {actions.map((action, index) => (
              <Button
                key={index}
                variant={action.variant || (index === 0 ? 'default' : 'outline')}
                onClick={action.onClick}
              >
                {action.label}
              </Button>
            ))}
          </div>
        )}
      </div>
    );
  }
);

EmptyState.displayName = 'EmptyState';

export { EmptyState };
