import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DraftListSidebar } from '../DraftListSidebar';
import type { Draft } from '@web/types/content-review';

describe('DraftListSidebar', () => {
  const drafts: Draft[] = [
    {
      id: 'draft-1',
      title: 'Draft One',
      status: 'pending',
      mediaType: 'audio',
      content: 'Content',
      keywords: [],
      assetStatus: 'missing',
    },
    {
      id: 'draft-2',
      title: 'Draft Two',
      status: 'in_progress',
      mediaType: 'video',
      content: 'Content',
      keywords: [],
      assetStatus: 'present',
    },
  ];

  it('renders drafts and highlights the selected item', () => {
    render(<DraftListSidebar drafts={drafts} selectedId="draft-2" onSelect={vi.fn()} />);

    expect(screen.getByText('2 items')).toBeInTheDocument();
    expect(screen.getByText('Source missing')).toBeInTheDocument();

    const selected = screen.getByRole('button', { name: /Draft Two/i });
    expect(selected).toHaveClass('border-primary');
  });

  it('calls onSelect with the draft id', () => {
    const handleSelect = vi.fn();
    render(<DraftListSidebar drafts={drafts} selectedId="draft-1" onSelect={handleSelect} />);

    fireEvent.click(screen.getByRole('button', { name: /Draft Two/i }));
    expect(handleSelect).toHaveBeenCalledWith('draft-2');
  });
});
