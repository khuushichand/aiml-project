import '@testing-library/jest-dom/vitest';
import 'fake-indexeddb/auto';
import React from 'react';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Mock next/dynamic to render the actual component instead of a loading wrapper
// This is needed because dynamic({ ssr: false }) doesn't render in jsdom tests
vi.mock('next/dynamic', () => ({
  default: (
    importFn: () => Promise<{ default: React.ComponentType<Record<string, unknown>> }>
  ) => {
    // Return a component that uses React.lazy internally
    const LazyComponent = React.lazy(importFn);

    return function DynamicWrapper(props: Record<string, unknown>) {
      return React.createElement(
        React.Suspense,
        { fallback: null },
        React.createElement(LazyComponent, props)
      );
    };
  },
}));

// Mock the Dexie database to avoid IndexedDB issues in tests
vi.mock('@/db/dexie/schema', () => {
  const mockTable = {
    toArray: vi.fn().mockResolvedValue([]),
    get: vi.fn().mockResolvedValue(undefined),
    put: vi.fn().mockResolvedValue(undefined),
    add: vi.fn().mockResolvedValue(undefined),
    delete: vi.fn().mockResolvedValue(undefined),
    where: vi.fn().mockReturnThis(),
    equals: vi.fn().mockReturnThis(),
    first: vi.fn().mockResolvedValue(undefined),
    count: vi.fn().mockResolvedValue(0),
    bulkPut: vi.fn().mockResolvedValue(undefined),
    bulkDelete: vi.fn().mockResolvedValue(undefined),
  };

  return {
    db: {
      chatHistories: mockTable,
      messages: mockTable,
      prompts: mockTable,
      webshares: mockTable,
      sessionFiles: mockTable,
      userSettings: mockTable,
      customModels: mockTable,
      modelNickname: mockTable,
      processedMedia: mockTable,
      compareStates: mockTable,
      contentDrafts: mockTable,
      draftBatches: mockTable,
      draftAssets: mockTable,
      folders: mockTable,
      keywords: mockTable,
      folderKeywordLinks: mockTable,
      conversationKeywordLinks: mockTable,
      audiobookProjects: mockTable,
      audiobookChapterAssets: mockTable,
      ttsClips: mockTable,
      transaction: vi.fn().mockImplementation(async (_mode, _tables, cb) => cb()),
    },
    PageAssistDexieDB: vi.fn(),
  };
});

// Mock React Query to provide QueryClient context for page tests
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query');
  return {
    ...actual,
    useQuery: vi.fn().mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }),
    useMutation: vi.fn().mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
    }),
    useQueryClient: vi.fn().mockReturnValue({
      invalidateQueries: vi.fn(),
      setQueryData: vi.fn(),
    }),
  };
});

afterEach(() => {
  cleanup();
});
