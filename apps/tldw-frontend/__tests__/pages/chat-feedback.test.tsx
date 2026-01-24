import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// TODO: These integration tests require a comprehensive test harness with:
// - QueryClientProvider (React Query)
// - Router context (react-router-dom)
// - Dexie/IndexedDB mock
// - Various UI providers (Toast, Layout, Theme)
// Skip until a shared test wrapper is created.
const SKIP_INTEGRATION_TESTS = true;

const mocks = vi.hoisted(() => ({
  showToast: vi.fn(),
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  streamSSE: vi.fn(),
}));

vi.mock('@web/components/layout/Layout', () => ({
  Layout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@web/components/ui/ToastProvider', () => ({
  useToast: () => ({ show: mocks.showToast }),
}));

vi.mock('@web/components/ui/JsonEditor', () => ({
  default: () => <div data-testid="json-editor" />,
  JsonEditor: () => <div data-testid="json-editor" />,
}));

vi.mock('@web/components/ui/HotkeysOverlay', () => ({
  default: () => null,
  HotkeysOverlay: () => null,
}));

vi.mock('@web/lib/api', () => ({
  apiClient: mocks.apiClient,
  getApiBaseUrl: () => 'http://example.com/api/v1',
  buildAuthHeaders: () => ({}),
}));

vi.mock('@web/lib/sse', () => ({
  streamSSE: mocks.streamSSE,
}));

import ChatPage from '@web/pages/chat';

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
  });
  mocks.apiClient.get.mockImplementation((url: string) => {
    if (url.startsWith('/llm/providers')) {
      return Promise.resolve({ providers: [] });
    }
    if (url.startsWith('/chats?')) {
      return Promise.resolve({ chats: [] });
    }
    if (url.startsWith('/chats/')) {
      return Promise.resolve({ messages: [] });
    }
    return Promise.resolve({});
  });
  mocks.apiClient.post.mockResolvedValue({});
  mocks.streamSSE.mockImplementation(async (_url, _opts, onDelta, onJSON, onDone) => {
    if (onJSON) onJSON({ tldw_system_message_id: 'sys_1' });
    if (onDelta) onDelta('Hello from stream');
    if (onJSON) onJSON({ tldw_message_id: 'msg_1' });
    if (onDone) onDone();
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe.skipIf(SKIP_INTEGRATION_TESTS)('ChatPage feedback (streaming)', () => {
  it('sends feedback with streamed message IDs for system and assistant messages', async () => {
    const user = userEvent.setup();
    render(<ChatPage />);

    const composer = screen.getByPlaceholderText('Type your message…');
    await user.type(composer, 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await screen.findByText('Hello from stream');
    await waitFor(() => expect(mocks.streamSSE).toHaveBeenCalled());

    const systemContainer = screen.getByTestId('message-container-sys_1');
    const systemFeedbackButton = within(systemContainer).getByRole('button', {
      name: /Send helpful feedback/i,
    });

    const assistantContainer = screen.getByTestId('message-container-msg_1');
    const assistantFeedbackButton = within(assistantContainer).getByRole('button', {
      name: /Send helpful feedback/i,
    });

    await user.click(assistantFeedbackButton);
    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/feedback/explicit',
        expect.objectContaining({ message_id: 'msg_1', helpful: true })
      );
    });

    await user.click(systemFeedbackButton);
    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/feedback/explicit',
        expect.objectContaining({ message_id: 'sys_1', helpful: true })
      );
    });
  });

  it('submits detailed feedback from the modal', async () => {
    const user = userEvent.setup();
    render(<ChatPage />);

    const composer = screen.getByPlaceholderText('Type your message…');
    await user.type(composer, 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await screen.findByText('Hello from stream');
    await waitFor(() => expect(mocks.streamSSE).toHaveBeenCalled());

    const assistantContainer = screen.getByTestId('message-container-msg_1');
    const detailsButton = within(assistantContainer).getByRole('button', {
      name: /Open feedback details/i,
    });

    await user.click(detailsButton);

    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: /Rate 3 out of 5/i }));
    await user.click(within(dialog).getByLabelText('Missing important details'));
    await user.type(within(dialog).getByLabelText('Additional comments (optional)'), 'Needs more specifics.');
    await user.click(within(dialog).getByRole('button', { name: /Submit Feedback/i }));

    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/feedback/explicit',
        expect.objectContaining({
          feedback_type: 'relevance',
          message_id: 'msg_1',
          relevance_score: 3,
          issues: ['missing_details'],
          user_notes: 'Needs more specifics.',
        })
      );
    });
  });

  it('emits dwell_time implicit feedback after a response settles', async () => {
    vi.useFakeTimers();
    render(<ChatPage />);

    const composer = screen.getByPlaceholderText('Type your message…');
    fireEvent.change(composer, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await vi.advanceTimersByTimeAsync(3100);
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();

    expect(mocks.apiClient.post).toHaveBeenCalledWith(
      '/rag/feedback/implicit',
      expect.objectContaining({
        event_type: 'dwell_time',
        message_id: 'msg_1',
        dwell_ms: 3000,
      })
    );
  });

  it('emits citation_used implicit feedback when copying citations', async () => {
    const user = userEvent.setup();
    mocks.streamSSE.mockImplementation(async (_url, _opts, onDelta, onJSON, onDone) => {
      if (onJSON) onJSON({ tldw_system_message_id: 'sys_1' });
      if (onDelta) onDelta('Answer text\n\nSources:\n- Doc 1');
      if (onJSON) onJSON({ tldw_message_id: 'msg_1' });
      if (onDone) onDone();
    });

    render(<ChatPage />);

    const composer = screen.getByPlaceholderText('Type your message…');
    await user.type(composer, 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    const assistantContainer = await screen.findByTestId('message-container-msg_1');
    const copyButton = within(assistantContainer).getByRole('button', { name: /Copy with citations/i });
    await user.click(copyButton);

    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/rag/feedback/implicit',
        expect.objectContaining({
          event_type: 'citation_used',
          message_id: 'msg_1',
        })
      );
    });
  });

  it('includes document ids for citation_used when tool results include documents', async () => {
    const user = userEvent.setup();
    mocks.streamSSE.mockImplementation(async (_url, _opts, onDelta, onJSON, onDone) => {
      if (onJSON) onJSON({ tldw_system_message_id: 'sys_1' });
      if (onDelta) onDelta('Answer text\n\nSources:\n- Doc 1');
      if (onJSON) {
        onJSON({
          tldw_tool_results: [
            {
              name: 'rag.search',
              content: {
                documents: [
                  { id: 'doc-1', metadata: { chunk_id: 'chunk-1', corpus: 'media_db' } },
                ],
              },
            },
          ],
        });
      }
      if (onJSON) onJSON({ tldw_message_id: 'msg_1' });
      if (onDone) onDone();
    });

    render(<ChatPage />);

    const composer = screen.getByPlaceholderText('Type your message…');
    await user.type(composer, 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    const assistantContainer = await screen.findByTestId('message-container-msg_1');
    const copyButton = within(assistantContainer).getByRole('button', { name: /Copy with citations/i });
    await user.click(copyButton);

    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/rag/feedback/implicit',
        expect.objectContaining({
          event_type: 'citation_used',
          message_id: 'msg_1',
          doc_id: 'doc-1',
          chunk_ids: ['chunk-1'],
          impression_list: ['doc-1'],
          corpus: 'media_db',
        })
      );
    });
  });
});
