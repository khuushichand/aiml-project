'use client';

import { useCallback, useEffect, useState } from 'react';

export type LoadOptions = {
  signal?: AbortSignal;
};

export type PagedResponse<T> = {
  items: T[];
  total: number;
};

export type UsePagedResourceOptions<T> = {
  load: (options?: LoadOptions) => Promise<PagedResponse<T>>;
  deps?: unknown[];
  enabled?: boolean;
  initialItems?: T[];
  initialTotal?: number;
  defaultError?: string;
  resetOnError?: boolean;
};

export type UsePagedResourceResult<T> = {
  items: T[];
  total: number;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
};

export const usePagedResource = <T>({
  load,
  deps = [],
  enabled = true,
  initialItems = [],
  initialTotal = 0,
  defaultError = 'Failed to load data',
  resetOnError = true,
}: UsePagedResourceOptions<T>): UsePagedResourceResult<T> => {
  const [items, setItems] = useState<T[]>(initialItems);
  const [total, setTotal] = useState(initialTotal);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState('');

  const runLoad = useCallback(async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setError('');
      const data = await load({ signal });
      setItems(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      const message = err instanceof Error && err.message ? err.message : defaultError;
      setError(message);
      if (resetOnError) {
        setItems([]);
        setTotal(0);
      }
    } finally {
      setLoading(false);
    }
  }, [defaultError, load, resetOnError]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    const controller = new AbortController();
    void runLoad(controller.signal);
    return () => controller.abort();
  }, [enabled, runLoad, deps]);

  const reload = useCallback(async () => {
    await runLoad();
  }, [runLoad]);

  return { items, total, loading, error, reload };
};
