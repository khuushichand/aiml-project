/* @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import GlobalError from '../global-error';

describe('GlobalError', () => {
  it('adds dedicated dark-mode style hooks for the retry button and icon container', () => {
    const { container } = render(
      <GlobalError
        error={new Error('Boom')}
        reset={vi.fn()}
      />
    );

    const retryButton = screen.getByRole('button', { name: 'Try Again' });
    expect(retryButton.className).toContain('global-error-retry');

    expect(container.querySelector('.global-error-icon')).not.toBeNull();

    const styleText = document.head.querySelector('style')?.textContent
      ?? document.body.querySelector('style')?.textContent
      ?? '';
    expect(styleText).toContain('.global-error-retry');
    expect(styleText).toContain('.global-error-icon');
  });
});
