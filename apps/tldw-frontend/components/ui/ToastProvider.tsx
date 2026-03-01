import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { cn } from '@web/lib/utils';

type Variant = 'info' | 'success' | 'warning' | 'danger';

export interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: Variant;
  duration?: number; // ms
  actionLabel?: string;
  onAction?: () => void | Promise<void>;
}

interface ToastContextType {
  show: (t: Omit<ToastItem, 'id'>) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((t: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const item: ToastItem = { id, variant: 'info', duration: 3200, ...t };
    setToasts((prev) => [...prev, item]);
    if (item.duration && item.duration > 0) {
      setTimeout(() => remove(id), item.duration);
    }
  }, [remove]);

  const value = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[360px] flex-col space-y-2">
        {toasts.map((t) => (
          <div key={t.id} className={cn('pointer-events-auto animate-fade-in-up rounded-md border p-3 shadow-lg backdrop-blur', variantClass(t.variant))}>
            {t.title && <div className="text-sm font-semibold">{t.title}</div>}
            {t.description && <div className="mt-0.5 text-sm text-text">{t.description}</div>}
            {t.actionLabel && t.onAction && (
              <button
                type="button"
                className="mt-2 inline-flex items-center rounded border border-current/40 px-2 py-1 text-xs font-medium hover:bg-black/5"
                onClick={() => {
                  void t.onAction?.();
                  remove(t.id);
                }}
              >
                {t.actionLabel}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function variantClass(v?: Variant) {
  switch (v) {
    case 'success': return 'border-success/30 bg-success/10 text-success';
    case 'warning': return 'border-warn/30 bg-warn/10 text-warn';
    case 'danger': return 'border-danger/30 bg-danger/10 text-danger';
    case 'info':
    default: return 'border-primary/30 bg-primary/10 text-primary';
  }
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
