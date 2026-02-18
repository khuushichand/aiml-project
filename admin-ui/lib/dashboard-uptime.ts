import type { IncidentItem } from '@/types';

export interface DashboardUptimeSummary {
  uptimePercent: number | null;
  lastIncidentAt: string | null;
  windowDays: number;
}

export const DEFAULT_DASHBOARD_UPTIME_WINDOW_DAYS = 30;

export const DEFAULT_DASHBOARD_UPTIME_SUMMARY: DashboardUptimeSummary = {
  uptimePercent: null,
  lastIncidentAt: null,
  windowDays: DEFAULT_DASHBOARD_UPTIME_WINDOW_DAYS,
};

interface BuildDashboardUptimeSummaryInput {
  incidentsPayload?: unknown;
  now?: Date;
  windowDays?: number;
}

const toRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : null;

const toItems = (payload: unknown): IncidentItem[] => {
  if (Array.isArray(payload)) {
    return payload as IncidentItem[];
  }

  const record = toRecord(payload);
  if (!record) {
    return [];
  }

  const items = record.items;
  return Array.isArray(items) ? (items as IncidentItem[]) : [];
};

const parseTimestamp = (value: unknown): number | null => {
  if (typeof value !== 'string' || !value.trim()) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const mergeIntervals = (intervals: Array<[number, number]>): Array<[number, number]> => {
  if (intervals.length === 0) return [];

  const sorted = [...intervals].sort((a, b) => a[0] - b[0]);
  const merged: Array<[number, number]> = [sorted[0]];

  for (let i = 1; i < sorted.length; i += 1) {
    const [currentStart, currentEnd] = sorted[i];
    const previous = merged[merged.length - 1];

    if (currentStart <= previous[1]) {
      previous[1] = Math.max(previous[1], currentEnd);
    } else {
      merged.push([currentStart, currentEnd]);
    }
  }

  return merged;
};

export const buildDashboardUptimeSummary = ({
  incidentsPayload,
  now = new Date(),
  windowDays = DEFAULT_DASHBOARD_UPTIME_WINDOW_DAYS,
}: BuildDashboardUptimeSummaryInput): DashboardUptimeSummary => {
  const nowMs = now.getTime();
  if (!Number.isFinite(nowMs) || windowDays <= 0) {
    return {
      uptimePercent: null,
      lastIncidentAt: null,
      windowDays,
    };
  }

  const windowMs = windowDays * 24 * 60 * 60 * 1000;
  const windowStartMs = nowMs - windowMs;

  const incidents = toItems(incidentsPayload);
  if (incidents.length === 0) {
    return {
      uptimePercent: 100,
      lastIncidentAt: null,
      windowDays,
    };
  }

  let latestIncidentStartMs: number | null = null;
  const downtimeIntervals: Array<[number, number]> = [];

  incidents.forEach((incident) => {
    const startMs = parseTimestamp(incident.created_at);
    if (startMs === null) return;

    latestIncidentStartMs = latestIncidentStartMs === null
      ? startMs
      : Math.max(latestIncidentStartMs, startMs);

    const resolvedAtMs = parseTimestamp(incident.resolved_at);
    const updatedAtMs = parseTimestamp(incident.updated_at);
    const endMs = resolvedAtMs
      ?? (incident.status === 'resolved' ? updatedAtMs : null)
      ?? nowMs;

    if (!Number.isFinite(endMs) || endMs <= startMs) return;

    const clampedStart = Math.max(startMs, windowStartMs);
    const clampedEnd = Math.min(endMs, nowMs);

    if (clampedEnd > clampedStart) {
      downtimeIntervals.push([clampedStart, clampedEnd]);
    }
  });

  const mergedIntervals = mergeIntervals(downtimeIntervals);
  const downtimeMs = mergedIntervals.reduce((total, [start, end]) => total + (end - start), 0);
  const uptimePercent = Math.max(0, Math.min(100, ((windowMs - downtimeMs) / windowMs) * 100));

  return {
    uptimePercent: Number(uptimePercent.toFixed(2)),
    lastIncidentAt: latestIncidentStartMs === null
      ? null
      : new Date(latestIncidentStartMs).toISOString(),
    windowDays,
  };
};
