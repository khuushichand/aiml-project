import type { SecurityHealthData } from '@/types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

export const isSecurityHealthData = (data: unknown): data is SecurityHealthData => {
  if (!isRecord(data)) return false;
  const knownKeys = [
    'risk_score',
    'recent_security_events',
    'failed_logins_24h',
    'suspicious_activity',
    'mfa_adoption_rate',
    'active_sessions',
    'api_keys_active',
    'last_security_scan',
  ];
  if (!knownKeys.some((key) => key in data)) return false;
  const numberKeys = [
    'risk_score',
    'recent_security_events',
    'failed_logins_24h',
    'suspicious_activity',
    'mfa_adoption_rate',
    'active_sessions',
    'api_keys_active',
  ];
  for (const key of numberKeys) {
    const value = data[key];
    if (value !== undefined && typeof value !== 'number') return false;
  }
  if (data.last_security_scan !== undefined && typeof data.last_security_scan !== 'string') return false;
  return true;
};
