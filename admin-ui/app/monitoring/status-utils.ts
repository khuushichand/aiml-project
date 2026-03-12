import { normalizeMonitoringHealthStatus } from '@/lib/monitoring-health';
import type { SystemHealthStatus } from './types';

export const normalizeHealthStatus = (status?: string): SystemHealthStatus =>
  normalizeMonitoringHealthStatus(status);
