'use client';

/**
 * Returns true when the SaaS billing surface is enabled.
 * Self-hosted deployments set NEXT_PUBLIC_BILLING_ENABLED=false (or omit it).
 */
export function isBillingEnabled(): boolean {
  return process.env.NEXT_PUBLIC_BILLING_ENABLED === 'true';
}
