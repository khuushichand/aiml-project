'use client';

import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { useCallback, useMemo } from 'react';

type SerializableValue = string | number | boolean | null | undefined;

interface UseUrlStateOptions<T extends SerializableValue> {
  defaultValue?: T;
  serialize?: (value: T) => string;
  deserialize?: (value: string) => T;
}

/**
 * Hook to sync state with URL search params
 * Persists filter/search state across page refreshes and allows sharing URLs
 */
export function useUrlState<T extends SerializableValue>(
  key: string,
  options: UseUrlStateOptions<T> = {}
): [T | undefined, (value: T | undefined) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const {
    defaultValue,
    serialize = (v: T) => String(v),
    deserialize = (v: string) => v as T,
  } = options;

  // Get current value from URL
  const value = useMemo(() => {
    const paramValue = searchParams.get(key);
    if (paramValue === null) {
      return defaultValue;
    }
    try {
      return deserialize(paramValue);
    } catch {
      return defaultValue;
    }
  }, [searchParams, key, defaultValue, deserialize]);

  // Update URL with new value
  const setValue = useCallback(
    (newValue: T | undefined) => {
      const current = new URLSearchParams(Array.from(searchParams.entries()));

      if (newValue === undefined || newValue === null || newValue === '' || newValue === defaultValue) {
        current.delete(key);
      } else {
        current.set(key, serialize(newValue));
      }

      const search = current.toString();
      const query = search ? `?${search}` : '';

      // Use replace to avoid adding to browser history for every keystroke
      router.replace(`${pathname}${query}`, { scroll: false });
    },
    [key, pathname, router, searchParams, serialize, defaultValue]
  );

  return [value, setValue];
}

/**
 * Hook for managing multiple URL state values at once
 * Useful for complex filter panels
 */
export function useUrlMultiState<T extends Record<string, SerializableValue>>(
  defaults: T
): [T, (updates: Partial<T>) => void, () => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Get all current values from URL
  const values = useMemo(() => {
    const result = { ...defaults } as T;
    for (const key of Object.keys(defaults) as Array<keyof T>) {
      const paramValue = searchParams.get(key as string);
      if (paramValue !== null) {
        // Handle number conversion
        if (typeof defaults[key] === 'number') {
          (result as Record<keyof T, SerializableValue>)[key] = Number(paramValue);
        } else if (typeof defaults[key] === 'boolean') {
          (result as Record<keyof T, SerializableValue>)[key] = paramValue === 'true';
        } else {
          (result as Record<keyof T, SerializableValue>)[key] = paramValue;
        }
      }
    }
    return result;
  }, [searchParams, defaults]);

  // Update multiple values at once
  const setValues = useCallback(
    (updates: Partial<T>) => {
      const current = new URLSearchParams(Array.from(searchParams.entries()));

      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === null || value === '' || value === defaults[key]) {
          current.delete(key);
        } else {
          current.set(key, String(value));
        }
      }

      const search = current.toString();
      const query = search ? `?${search}` : '';
      router.replace(`${pathname}${query}`, { scroll: false });
    },
    [pathname, router, searchParams, defaults]
  );

  // Clear all filters
  const clearAll = useCallback(() => {
    router.replace(pathname, { scroll: false });
  }, [pathname, router]);

  return [values, setValues, clearAll];
}

/**
 * Hook specifically for pagination state in URL
 */
export function useUrlPagination(
  defaultPage: number = 1,
  defaultPageSize: number = 20
) {
  const [page, setPage] = useUrlState<number>('page', {
    defaultValue: defaultPage,
    deserialize: (v) => Math.max(1, parseInt(v, 10) || 1),
  });

  const [pageSize, setPageSize] = useUrlState<number>('pageSize', {
    defaultValue: defaultPageSize,
    deserialize: (v) => parseInt(v, 10) || defaultPageSize,
  });

  return {
    page: page ?? defaultPage,
    pageSize: pageSize ?? defaultPageSize,
    setPage,
    setPageSize,
    resetPagination: () => {
      setPage(defaultPage);
    },
  };
}
