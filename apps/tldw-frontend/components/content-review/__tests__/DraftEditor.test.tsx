import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DraftEditor } from '../DraftEditor';
import type { Draft } from '@web/types/content-review';

describe('DraftEditor', () => {
  const draft: Draft = {
    id: 'draft-1',
    title: 'Sample Draft',
    status: 'in_progress',
    mediaType: 'audio',
    content: 'Content',
    keywords: [],
    assetStatus: 'missing',
  };

  it('shows offline and source-required notices', () => {
    render(
      <DraftEditor
        draft={draft}
        isOnline={false}
        dirty={false}
        editorText="Content"
        keywordsInput=""
        commitDisabled
        onOpenReattach={vi.fn()}
        onSaveDraft={vi.fn()}
        onEditorChange={vi.fn()}
        onKeywordsChange={vi.fn()}
        onCommit={vi.fn()}
      />
    );

    expect(screen.getByText(/You are offline/i)).toBeInTheDocument();
    expect(screen.getByText(/Source required to commit/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Commit/i })).toBeDisabled();
  });

  it('invokes callbacks for reattach and commit', () => {
    const handleReattach = vi.fn();
    const handleCommit = vi.fn();

    render(
      <DraftEditor
        draft={{ ...draft, assetStatus: 'missing' }}
        isOnline
        dirty
        editorText="Content"
        keywordsInput=""
        commitDisabled={false}
        onOpenReattach={handleReattach}
        onSaveDraft={vi.fn()}
        onEditorChange={vi.fn()}
        onKeywordsChange={vi.fn()}
        onCommit={handleCommit}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Commit/i }));
    expect(handleCommit).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Reattach Source/i }));
    expect(handleReattach).toHaveBeenCalled();
  });

  it('disables save button when draft is not dirty', () => {
    render(
      <DraftEditor
        draft={draft}
        isOnline
        dirty={false}
        editorText="Content"
        keywordsInput=""
        commitDisabled
        onOpenReattach={vi.fn()}
        onSaveDraft={vi.fn()}
        onEditorChange={vi.fn()}
        onKeywordsChange={vi.fn()}
        onCommit={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /Save Draft/i })).toBeDisabled();
  });
});
