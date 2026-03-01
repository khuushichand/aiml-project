'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type LoadOptions = {
  signal?: AbortSignal;
};

export type PagedResponse<T> = {
  items: T[];
  total: number;
};

export type UsePagedResourceOptions<T> = {
  load: (options?: LoadOptions) => Promise<PagedResponse<T>>;
  deps?: readonly unknown[];
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

const NO_DEPS: readonly unknown[] = [];

const depsChanged = (previous: readonly unknown[], next: readonly unknown[]): boolean => {
  if (previous.length !== next.length) return true;
  return next.some((value, index) => !Object.is(value, previous[index]));
};

export const usePagedResource = <T>({
  load,
  deps = NO_DEPS,
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
  const depsRef = useRef<readonly unknown[]>(deps);

  if (depsChanged(depsRef.current, deps)) {
    depsRef.current = deps;
  }

  const stableDeps = depsRef.current;

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
  }, [enabled, runLoad, stableDeps]);

  const reload = useCallback(async () => {
    await runLoad();
  }, [runLoad]);

  return { items, total, loading, error, reload };
};
