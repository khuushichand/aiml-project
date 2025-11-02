import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'info' | 'success' | 'warning' | 'danger';

export interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: Variant;
  duration?: number; // ms
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
            {t.description && <div className="mt-0.5 text-sm text-gray-700">{t.description}</div>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function variantClass(v?: Variant) {
  switch (v) {
    case 'success': return 'border-green-200 bg-green-50 text-green-900';
    case 'warning': return 'border-yellow-200 bg-yellow-50 text-yellow-900';
    case 'danger': return 'border-red-200 bg-red-50 text-red-900';
    case 'info':
    default: return 'border-blue-200 bg-blue-50 text-blue-900';
  }
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
