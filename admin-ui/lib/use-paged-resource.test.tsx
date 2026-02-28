import { useCallback } from 'react';
import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { type LoadOptions, usePagedResource } from './use-paged-resource';

type HarnessProps = {
  dep?: string;
  load: (options?: LoadOptions) => Promise<{ items: string[]; total: number }>;
  withDeps?: boolean;
};

function Harness({ dep = 'default', load, withDeps = true }: HarnessProps) {
  const loadResource = useCallback((options?: LoadOptions) => load(options), [load]);

  usePagedResource({
    load: loadResource,
    deps: withDeps ? [dep] : undefined,
  });

  return null;
}

describe('usePagedResource', () => {
  it('does not reload when dependency values are unchanged between renders', async () => {
    const load = vi.fn().mockResolvedValue({ items: [], total: 0 });

    const { rerender } = render(<Harness dep="alpha" load={load} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(1);
    });

    rerender(<Harness dep="alpha" load={load} />);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(load).toHaveBeenCalledTimes(1);
  });

  it('reloads exactly once when dependency values change', async () => {
    const load = vi.fn().mockResolvedValue({ items: [], total: 0 });

    const { rerender } = render(<Harness dep="alpha" load={load} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(1);
    });

    rerender(<Harness dep="beta" load={load} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
    });
  });

  it('does not reload on parent rerender when deps are omitted', async () => {
    const load = vi.fn().mockResolvedValue({ items: [], total: 0 });

    const { rerender } = render(<Harness load={load} withDeps={false} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(1);
    });

    rerender(<Harness load={load} withDeps={false} />);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(load).toHaveBeenCalledTimes(1);
  });
});
