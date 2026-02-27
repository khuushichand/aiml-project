'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type LoadOptions = {
  signal?: AbortSignal;
};

export type UseResourceStateOptions<T> = {
  load: (options?: LoadOptions) => Promise<T>;
  deps?: readonly unknown[];
  enabled?: boolean;
  initialValue: T;
  defaultError?: string;
  resetOnError?: boolean;
};

export type UseResourceStateResult<T> = {
  value: T;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
};

const NO_DEPS: readonly unknown[] = [];

const depsChanged = (previous: readonly unknown[], next: readonly unknown[]): boolean => {
  if (previous.length !== next.length) return true;
  return next.some((value, index) => !Object.is(value, previous[index]));
};

export const useResourceState = <T>({
  load,
  deps = NO_DEPS,
  enabled = true,
  initialValue,
  defaultError = 'Failed to load data',
  resetOnError = true,
}: UseResourceStateOptions<T>): UseResourceStateResult<T> => {
  const initialValueRef = useRef(initialValue);
  const [value, setValue] = useState<T>(initialValueRef.current);
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
      setValue(data);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      const message = err instanceof Error && err.message ? err.message : defaultError;
      setError(message);
      if (resetOnError) {
        setValue(initialValueRef.current);
      }
    } finally {
      setLoading(false);
    }
  }, [defaultError, load, resetOnError]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    void runLoad(controller.signal);
    return () => controller.abort();
  }, [enabled, runLoad, stableDeps]);

  const reload = useCallback(async () => {
    await runLoad();
  }, [runLoad]);

  return { value, loading, error, reload };
};
