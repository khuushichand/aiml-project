import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReattachSourceModal } from '../ReattachSourceModal';

describe('ReattachSourceModal', () => {
  it('renders nothing when closed', () => {
    render(
      <ReattachSourceModal
        isOpen={false}
        tab="file"
        url=""
        error={null}
        largeFileWarningBytes={1024}
        onTabChange={vi.fn()}
        onUrlChange={vi.fn()}
        onFileChange={vi.fn()}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('handles tab changes, file upload, and submit', async () => {
    const user = userEvent.setup();
    const handleTabChange = vi.fn();
    const handleFileChange = vi.fn();
    const handleUrlChange = vi.fn();
    const handleClose = vi.fn();
    const handleSubmit = vi.fn();

    render(
      <ReattachSourceModal
        isOpen
        tab="file"
        url=""
        error={null}
        largeFileWarningBytes={1024}
        onTabChange={handleTabChange}
        onUrlChange={handleUrlChange}
        onFileChange={handleFileChange}
        onClose={handleClose}
        onSubmit={handleSubmit}
      />
    );

    const dialog = screen.getByRole('dialog');
    const fileInput = dialog.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['hello'], 'hello.txt', { type: 'text/plain' });

    await user.upload(fileInput, file);
    expect(handleFileChange).toHaveBeenCalledWith(file);

    await user.click(within(dialog).getByRole('button', { name: /Provide URL/i }));
    expect(handleTabChange).toHaveBeenCalledWith('url');

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalled();

    await user.click(within(dialog).getByRole('button', { name: /Attach Source/i }));
    expect(handleSubmit).toHaveBeenCalled();
  });

  it('updates the url input and displays error', async () => {
    const user = userEvent.setup();
    const handleUrlChange = vi.fn();

    render(
      <ReattachSourceModal
        isOpen
        tab="url"
        url=""
        error="Invalid URL"
        largeFileWarningBytes={1024}
        onTabChange={vi.fn()}
        onUrlChange={handleUrlChange}
        onFileChange={vi.fn()}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    const dialog = screen.getByRole('dialog');
    const urlInput = within(dialog).getByPlaceholderText('https://...');

    await user.type(urlInput, 'https://example.com');
    expect(handleUrlChange).toHaveBeenCalled();
    expect(within(dialog).getByText('Invalid URL')).toBeInTheDocument();
  });
});
