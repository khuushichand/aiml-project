import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { useQueryClient } from '@tanstack/react-query';

import { useToast } from '@web/components/ui/ToastProvider';
import { renderWithProviders } from '@web/__tests__/testUtils/renderWithProviders';

function HarnessConsumer() {
  const queryClient = useQueryClient();
  const toast = useToast();

  return (
    <div>
      {typeof queryClient.getDefaultOptions === 'function' && typeof toast.show === 'function'
        ? 'provider-ready'
        : 'provider-broken'}
    </div>
  );
}

describe('research run console test harness', () => {
  it('provides query and toast context for page-level tests', () => {
    renderWithProviders(<HarnessConsumer />);

    expect(screen.getByText('provider-ready')).toBeInTheDocument();
  });
});
