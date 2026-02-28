import { useCallback } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useResourceState, type LoadOptions } from './use-resource-state';

type HarnessProps = {
  dep?: string;
  load: (options?: LoadOptions) => Promise<string[]>;
  withDeps?: boolean;
  resetOnError?: boolean;
};

function Harness({
  dep = 'default',
  load,
  withDeps = true,
  resetOnError = true,
}: HarnessProps) {
  const loadResource = useCallback((options?: LoadOptions) => load(options), [load]);
  const { value, error, reload } = useResourceState({
    load: loadResource,
    deps: withDeps ? [dep] : undefined,
    initialValue: ['initial'],
    resetOnError,
  });

  return (
    <div>
      <div data-testid="value">{value.join(',')}</div>
      <div data-testid="error">{error}</div>
      <button onClick={() => void reload()}>Reload</button>
    </div>
  );
}

describe('useResourceState', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('does not reload when dependency values are unchanged between renders', async () => {
    const load = vi.fn().mockResolvedValue(['loaded']);
    const { rerender } = render(<Harness dep="alpha" load={load} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(1);
    });

    rerender(<Harness dep="alpha" load={load} />);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(load).toHaveBeenCalledTimes(1);
  });

  it('reloads exactly once when dependency values change', async () => {
    const load = vi.fn().mockResolvedValue(['loaded']);
    const { rerender } = render(<Harness dep="alpha" load={load} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(1);
    });

    rerender(<Harness dep="beta" load={load} />);

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
    });
  });

  it('resets to initial value and exposes error when load fails', async () => {
    const load = vi.fn().mockRejectedValue(new Error('boom'));
    render(<Harness load={load} />);

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('boom');
    });
    expect(screen.getByTestId('value').textContent).toBe('initial');
  });

  it('supports manual reload', async () => {
    const load = vi.fn()
      .mockResolvedValueOnce(['first'])
      .mockResolvedValueOnce(['second']);
    render(<Harness load={load} />);

    await waitFor(() => {
      expect(screen.getByTestId('value').textContent).toBe('first');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));

    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByTestId('value').textContent).toBe('second');
  });
});
