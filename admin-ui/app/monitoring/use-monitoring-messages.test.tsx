/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useMonitoringMessages } from './use-monitoring-messages';

function Harness() {
  const { error, setError, success, setSuccess } = useMonitoringMessages();

  return (
    <div>
      <div data-testid="error">{error}</div>
      <div data-testid="success">{success}</div>
      <button onClick={() => setError('boom')}>Set Error</button>
      <button onClick={() => setSuccess('saved')}>Set Success</button>
      <button onClick={() => setSuccess('updated')}>Set Success Updated</button>
      <button onClick={() => setSuccess('')}>Clear Success</button>
    </div>
  );
}

describe('useMonitoringMessages', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  it('manages error and success messages independently', () => {
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Error' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set Success' }));

    expect(screen.getByTestId('error').textContent).toBe('boom');
    expect(screen.getByTestId('success').textContent).toBe('saved');
  });

  it('auto-clears success messages after the default timeout', async () => {
    vi.useFakeTimers();
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Success' }));
    expect(screen.getByTestId('success').textContent).toBe('saved');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByTestId('success').textContent).toBe('');
  });

  it('resets the timer when success updates before timeout', async () => {
    vi.useFakeTimers();
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Success' }));
    await vi.advanceTimersByTimeAsync(2000);
    fireEvent.click(screen.getByRole('button', { name: 'Set Success Updated' }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3999);
    });
    expect(screen.getByTestId('success').textContent).toBe('updated');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.getByTestId('success').textContent).toBe('');
  });

  it('cancels pending timer when success is manually cleared', async () => {
    vi.useFakeTimers();
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Success' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear Success' }));

    await vi.advanceTimersByTimeAsync(4000);
    expect(screen.getByTestId('success').textContent).toBe('');
  });
});
