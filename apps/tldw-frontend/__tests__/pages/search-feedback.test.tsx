import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
}));

vi.mock('next/router', () => ({
  useRouter: () => ({
    query: {},
    isReady: true,
    replace: vi.fn(),
    push: vi.fn(),
    pathname: '/search',
  }),
}));

vi.mock('@web/components/layout/Layout', () => ({
  Layout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@web/components/ui/ToastProvider', () => ({
  useToast: () => ({ show: mocks.showToast }),
}));

vi.mock('@web/components/VlmBackendsCard', () => ({
  VlmBackendsCard: () => null,
}));

vi.mock('@web/components/ui/HotkeysOverlay', () => ({
  default: () => null,
  HotkeysOverlay: () => null,
}));

vi.mock('@web/components/ui/JsonEditor', () => ({
  default: () => <div data-testid="json-editor" />,
  JsonEditor: () => <div data-testid="json-editor" />,
}));

vi.mock('@web/components/ui/JsonViewer', () => ({
  default: () => <div data-testid="json-viewer" />,
}));

vi.mock('@web/components/ui/JsonTree', () => ({
  default: () => <div data-testid="json-tree" />,
}));

vi.mock('@web/lib/api', () => ({
  apiClient: mocks.apiClient,
}));

import SearchPage from '@web/pages/search';

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
  });
  mocks.apiClient.get.mockResolvedValue({});
  mocks.apiClient.post.mockImplementation((url: string) => {
    if (url === '/rag/search') {
      return Promise.resolve({
        generated_answer: 'Answer text',
        documents: [
          {
            id: 'doc-1',
            content: 'Doc content',
            metadata: { title: 'Doc 1', source: 'media_db' },
          },
        ],
        academic_citations: ['Citation 1'],
      });
    }
    return Promise.resolve({});
  });
});

describe.skipIf(SKIP_INTEGRATION_TESTS)('SearchPage source feedback', () => {
  it('sends explicit feedback for a document source', async () => {
    const user = userEvent.setup();
    render(<SearchPage />);

    await user.type(screen.getByPlaceholderText('Search your media...'), 'What is onboarding?');
    const searchButtons = screen.getAllByRole('button', { name: 'Search' });
    await user.click(searchButtons[0]);

    await screen.findByText('Documents');
    await user.click(screen.getByLabelText('Pro mode: source feedback'));

    const yesButton = await screen.findByRole('button', { name: /Send source helpful feedback/i });
    await user.click(yesButton);

    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/feedback/explicit',
        expect.objectContaining({
          helpful: true,
          query: 'What is onboarding?',
          document_ids: ['doc-1'],
        })
      );
    });
  });

  it('emits citation_used implicit feedback when copying citations', async () => {
    const user = userEvent.setup();
    render(<SearchPage />);

    await user.type(screen.getByPlaceholderText('Search your media...'), 'What is onboarding?');
    const searchButtons = screen.getAllByRole('button', { name: 'Search' });
    await user.click(searchButtons[0]);

    await screen.findByText('Documents');
    const copyWithCitations = await screen.findByRole('button', { name: 'Copy with citations' });
    await user.click(copyWithCitations);

    await waitFor(() => {
      expect(mocks.apiClient.post).toHaveBeenCalledWith(
        '/rag/feedback/implicit',
        expect.objectContaining({
          event_type: 'citation_used',
          doc_id: 'doc-1',
          impression_list: ['doc-1'],
          corpus: 'media_db',
        })
      );
    });
  });
});
