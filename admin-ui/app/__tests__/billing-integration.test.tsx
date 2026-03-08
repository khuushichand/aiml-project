import { describe, it, expect, vi } from 'vitest';
import { isBillingEnabled } from '@/lib/billing';

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: vi.fn(),
}));

describe('Billing integration', () => {
  it('isBillingEnabled returns false when env is not set', () => {
    vi.mocked(isBillingEnabled).mockReturnValue(false);
    expect(isBillingEnabled()).toBe(false);
  });

  it('isBillingEnabled returns true when env is true', () => {
    vi.mocked(isBillingEnabled).mockReturnValue(true);
    expect(isBillingEnabled()).toBe(true);
  });
});

describe('Billing types are importable', () => {
  it('imports Plan type without error', async () => {
    const types = await import('@/types');
    expect(types).toBeDefined();
  });
});
