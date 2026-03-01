/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  useWatchlistActions,
  type WatchlistApiClient,
} from './use-watchlist-actions';

type HarnessProps = {
  apiClient: WatchlistApiClient;
  confirm: (options: { title: string; message: string; confirmText?: string; variant?: string; icon?: string }) => Promise<boolean>;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
  onReloadRequested: () => void | Promise<void>;
};

function Harness({
  apiClient,
  confirm,
  setError,
  setSuccess,
  onReloadRequested,
}: HarnessProps) {
  const {
    showCreateWatchlist,
    setShowCreateWatchlist,
    newWatchlist,
    setNewWatchlist,
    deletingWatchlistId,
    handleCreateWatchlist,
    handleDeleteWatchlist,
  } = useWatchlistActions({
    apiClient,
    confirm,
    setError,
    setSuccess,
    onReloadRequested,
  });

  return (
    <div>
      <div data-testid="dialog-open">{String(showCreateWatchlist)}</div>
      <div data-testid="draft-name">{newWatchlist.name}</div>
      <div data-testid="draft-target">{newWatchlist.target}</div>
      <div data-testid="deleting-id">{deletingWatchlistId ?? ''}</div>
      <button onClick={() => setShowCreateWatchlist(true)}>Open Dialog</button>
      <button
        onClick={() =>
          setNewWatchlist({
            ...newWatchlist,
            name: 'CPU Usage',
            target: 'cpu_usage',
            description: 'CPU threshold',
          })
        }
      >
        Fill Draft
      </button>
      <button onClick={() => { void handleCreateWatchlist(); }}>Create</button>
      <button
        onClick={() => {
          void handleDeleteWatchlist({
            id: 'watch-1',
            name: 'CPU Usage',
            description: 'CPU threshold',
            target: 'cpu_usage',
            type: 'metric',
            threshold: 85,
            status: 'warning',
          });
        }}
      >
        Delete
      </button>
    </div>
  );
}

type WatchlistApiClientMock = WatchlistApiClient & {
  createWatchlist: ReturnType<typeof vi.fn>;
  deleteWatchlist: ReturnType<typeof vi.fn>;
};

const buildApiClient = (): WatchlistApiClientMock => ({
  createWatchlist: vi.fn().mockResolvedValue({}),
  deleteWatchlist: vi.fn().mockResolvedValue({}),
});

const createDeferred = <T,>() => {
  let resolve: (value: T) => void = () => {};
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
};

describe('useWatchlistActions', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('validates required fields before creating a watchlist', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      expect(setError).toHaveBeenCalledWith('Name and target are required');
    });
    expect(apiClient.createWatchlist).not.toHaveBeenCalled();
    expect(onReloadRequested).not.toHaveBeenCalled();
  });

  it('creates a watchlist, resets draft state, and requests reload on success', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open Dialog' }));
    fireEvent.click(screen.getByRole('button', { name: 'Fill Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      expect(apiClient.createWatchlist).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'CPU Usage',
          target: 'cpu_usage',
        })
      );
    });

    await waitFor(() => {
      expect(setError).toHaveBeenCalledWith('');
      expect(setSuccess).toHaveBeenCalledWith('Watchlist created successfully');
      expect(onReloadRequested).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('dialog-open').textContent).toBe('false');
      expect(screen.getByTestId('draft-name').textContent).toBe('');
      expect(screen.getByTestId('draft-target').textContent).toBe('');
    });
  });

  it('aborts deletion when confirmation is declined', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(false);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(confirm).toHaveBeenCalledTimes(1);
    });
    expect(apiClient.deleteWatchlist).not.toHaveBeenCalled();
    expect(onReloadRequested).not.toHaveBeenCalled();
  });

  it('deletes once while pending and clears deleting state after completion', async () => {
    const apiClient = buildApiClient();
    const deferredDelete = createDeferred<Record<string, never>>();
    apiClient.deleteWatchlist.mockReturnValue(deferredDelete.promise);
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => {
      expect(apiClient.deleteWatchlist).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('deleting-id').textContent).toBe('watch-1');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(apiClient.deleteWatchlist).toHaveBeenCalledTimes(1);

    deferredDelete.resolve({});

    await waitFor(() => {
      expect(screen.getByTestId('deleting-id').textContent).toBe('');
    });
    expect(setSuccess).toHaveBeenCalledWith('Watchlist deleted');
    expect(onReloadRequested).toHaveBeenCalledTimes(1);
  });
});
