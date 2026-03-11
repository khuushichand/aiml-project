import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  EMPTY_BILLING_CELL_PLACEHOLDER,
  fetchDashboardBillingStats,
  fetchOrganizationPlanMap,
  formatBillingDate,
  isBillingEnabled,
  normalizeInvoices,
} from '@/lib/billing';

const originalBillingEnv = process.env.NEXT_PUBLIC_BILLING_ENABLED;

describe('billing integration helpers', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.NEXT_PUBLIC_BILLING_ENABLED;
  });

  afterEach(() => {
    if (originalBillingEnv === undefined) {
      delete process.env.NEXT_PUBLIC_BILLING_ENABLED;
    } else {
      process.env.NEXT_PUBLIC_BILLING_ENABLED = originalBillingEnv;
    }
  });

  it('reads billing enablement from NEXT_PUBLIC_BILLING_ENABLED', () => {
    expect(isBillingEnabled()).toBe(false);

    process.env.NEXT_PUBLIC_BILLING_ENABLED = 'true';
    expect(isBillingEnabled()).toBe(true);

    process.env.NEXT_PUBLIC_BILLING_ENABLED = 'false';
    expect(isBillingEnabled()).toBe(false);
  });

  it('formats billing dates with an explicit locale', () => {
    const iso = '2026-03-08T12:00:00Z';
    expect(formatBillingDate(iso)).toBe(new Date(iso).toLocaleDateString('en-CA'));
  });

  it('normalizes unexpected invoice payloads to an empty list and warns', () => {
    const warn = vi.fn();

    expect(normalizeInvoices({ total: 1 }, warn)).toEqual([]);
    expect(warn).toHaveBeenCalledWith(
      'Unexpected organization invoice payload:',
      'object'
    );
    expect(formatBillingDate(undefined)).toBe(EMPTY_BILLING_CELL_PLACEHOLDER);
  });

  it('logs and falls back when organization plan data cannot be loaded', async () => {
    const warn = vi.fn();

    await expect(
      fetchOrganizationPlanMap(
        async () => {
          throw new Error('subscriptions offline');
        },
        warn
      )
    ).resolves.toEqual({});

    expect(warn).toHaveBeenCalledWith(
      'Failed to fetch subscription plans:',
      expect.any(Error)
    );
  });

  it('logs and falls back when dashboard billing stats cannot be loaded', async () => {
    const warn = vi.fn();

    await expect(
      fetchDashboardBillingStats(
        async () => {
          throw new Error('billing stats offline');
        },
        warn
      )
    ).resolves.toBeNull();

    expect(warn).toHaveBeenCalledWith(
      'Failed to fetch billing stats:',
      expect.any(Error)
    );
  });
});
