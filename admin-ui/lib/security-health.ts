import type { SecurityHealthData } from '@/types';
import { isSecurityHealthData } from './type-guards';

export interface SecurityHealthResolution {
  data: SecurityHealthData | null;
  error: string;
}

export const SECURITY_HEALTH_UNAVAILABLE_MESSAGE = 'Security telemetry is currently unavailable.';

export const resolveSecurityHealth = (
  result: PromiseSettledResult<unknown>
): SecurityHealthResolution => {
  if (result.status === 'fulfilled' && isSecurityHealthData(result.value)) {
    return {
      data: result.value,
      error: '',
    };
  }
  return {
    data: null,
    error: SECURITY_HEALTH_UNAVAILABLE_MESSAGE,
  };
};
