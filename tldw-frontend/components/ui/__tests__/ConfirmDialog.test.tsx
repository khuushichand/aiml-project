import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfirmDialog } from '../ConfirmDialog';

describe('ConfirmDialog', () => {
  it('renders the dialog and triggers confirm', async () => {
    const handleConfirm = vi.fn();
    const handleCancel = vi.fn();
    const user = userEvent.setup();

    render(
      <ConfirmDialog
        open
        title="Delete item"
        message="Are you sure?"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(handleConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel for overlay click and escape key', () => {
    const handleCancel = vi.fn();

    render(
      <ConfirmDialog
        open
        title="Discard changes"
        message="Leave without saving?"
        onConfirm={vi.fn()}
        onCancel={handleCancel}
      />
    );

    const overlay = document.querySelector('[aria-hidden="true"]');
    expect(overlay).not.toBeNull();
    fireEvent.click(overlay as HTMLElement);
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

    expect(handleCancel).toHaveBeenCalledTimes(2);
  });
});
