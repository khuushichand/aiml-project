/* @vitest-environment jsdom */
import { useState } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Button } from './button';
import { ConfirmProvider, useConfirm } from './confirm-dialog';

function ConfirmHarness() {
  const confirm = useConfirm();
  const [result, setResult] = useState('idle');

  return (
    <div>
      <Button
        onClick={async () => {
          const accepted = await confirm({
            title: 'Delete item?',
            message: 'Confirm deletion',
            confirmText: 'Delete',
            variant: 'danger',
          });
          setResult(accepted ? 'confirmed' : 'cancelled');
        }}
      >
        Open confirm
      </Button>
      <p data-testid="confirm-result">{result}</p>
    </div>
  );
}

afterEach(() => {
  cleanup();
});

describe('useConfirm', () => {
  it('resolves true when confirm button is pressed', async () => {
    render(
      <ConfirmProvider>
        <ConfirmHarness />
      </ConfirmProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open confirm' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(screen.getByTestId('confirm-result').textContent).toBe('confirmed');
    });
  });

  it('resolves false when cancel button is pressed', async () => {
    render(
      <ConfirmProvider>
        <ConfirmHarness />
      </ConfirmProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open confirm' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => {
      expect(screen.getByTestId('confirm-result').textContent).toBe('cancelled');
    });
  });
});
