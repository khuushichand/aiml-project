'use client';

import { ReactNode } from 'react';
import ErrorBoundary from '@/components/ErrorBoundary';
import { PermissionProvider } from '@/components/PermissionGuard';
import { OrgContextProvider } from '@/components/OrgContextSwitcher';
import { ToastProvider } from '@/components/ui/toast';
import { ConfirmProvider } from '@/components/ui/confirm-dialog';
import { KeyboardShortcutsProvider } from '@/components/KeyboardShortcuts';

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ConfirmProvider>
          <PermissionProvider>
            <OrgContextProvider>
              <KeyboardShortcutsProvider>
                {children}
              </KeyboardShortcutsProvider>
            </OrgContextProvider>
          </PermissionProvider>
        </ConfirmProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
