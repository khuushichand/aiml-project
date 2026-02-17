import { describe, expect, it } from 'vitest';
import {
  resolveSecurityHealth,
  SECURITY_HEALTH_UNAVAILABLE_MESSAGE,
} from './security-health';

describe('resolveSecurityHealth', () => {
  it('returns data when the response is fulfilled with valid shape', () => {
    const result = resolveSecurityHealth({
      status: 'fulfilled',
      value: {
        risk_score: 52,
        recent_security_events: 3,
        failed_logins_24h: 1,
        suspicious_activity: 0,
        mfa_adoption_rate: 80,
      },
    });

    expect(result.error).toBe('');
    expect(result.data).not.toBeNull();
    expect(result.data?.risk_score).toBe(52);
  });

  it('returns unavailable state when response is rejected', () => {
    const result = resolveSecurityHealth({
      status: 'rejected',
      reason: new Error('network down'),
    });

    expect(result.data).toBeNull();
    expect(result.error).toBe(SECURITY_HEALTH_UNAVAILABLE_MESSAGE);
  });

  it('returns unavailable state when fulfilled value is invalid', () => {
    const result = resolveSecurityHealth({
      status: 'fulfilled',
      value: { foo: 'bar' },
    });

    expect(result.data).toBeNull();
    expect(result.error).toBe(SECURITY_HEALTH_UNAVAILABLE_MESSAGE);
  });
});
