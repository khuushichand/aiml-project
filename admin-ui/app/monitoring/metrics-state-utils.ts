import type { Metric, Watchlist } from './types';

export const normalizeWatchlistsPayload = (value: unknown): Watchlist[] => {
  if (Array.isArray(value)) return value as Watchlist[];
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if (Array.isArray(obj.watchlists)) {
      return obj.watchlists as Watchlist[];
    }
  }
  return [];
};

export const buildMetricsFromSnapshot = (
  snapshot: unknown,
  warningThreshold: number,
  criticalThreshold: number
): Metric[] => {
  if (!snapshot || typeof snapshot !== 'object') {
    return [];
  }

  const metrics: Metric[] = [];
  Object.entries(snapshot).forEach(([key, value]) => {
    if (typeof value !== 'number' && typeof value !== 'string') {
      return;
    }

    metrics.push({
      name: key,
      value,
      status: typeof value === 'number' && value > criticalThreshold
        ? 'critical'
        : typeof value === 'number' && value > warningThreshold
          ? 'warning'
          : 'healthy',
    });
  });

  return metrics;
};
