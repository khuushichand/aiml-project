export interface LlmUsageTrendRow {
  group_value: string;
  group_value_secondary?: string | null;
  total_tokens: number;
}

const DEFAULT_TREND_DAYS = 7;

const getUtcDayKey = (value: Date): string => value.toISOString().slice(0, 10);

export const buildRecentUtcDayKeys = (
  days: number = DEFAULT_TREND_DAYS,
  endDate: Date = new Date()
): string[] => {
  const clampedDays = Number.isFinite(days) && days > 0 ? Math.floor(days) : DEFAULT_TREND_DAYS;
  const endDay = new Date(Date.UTC(
    endDate.getUTCFullYear(),
    endDate.getUTCMonth(),
    endDate.getUTCDate()
  ));
  const keys: string[] = [];
  for (let offset = clampedDays - 1; offset >= 0; offset -= 1) {
    const day = new Date(endDay);
    day.setUTCDate(endDay.getUTCDate() - offset);
    keys.push(getUtcDayKey(day));
  }
  return keys;
};

const normalizeDayValue = (value: string | null | undefined): string | null => {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed.slice(0, 10);
};

export const buildProviderTokenTrendMap = (
  rows: LlmUsageTrendRow[],
  options?: {
    days?: number;
    endDate?: Date;
  }
): Record<string, number[]> => {
  const dayKeys = buildRecentUtcDayKeys(options?.days, options?.endDate);
  const dayIndexByKey = new Map(dayKeys.map((key, index) => [key, index]));
  const trendByProvider: Record<string, number[]> = {};

  rows.forEach((row) => {
    const providerKey = row.group_value?.trim().toLowerCase();
    const dayKey = normalizeDayValue(row.group_value_secondary);
    if (!providerKey || !dayKey) return;

    const dayIndex = dayIndexByKey.get(dayKey);
    if (dayIndex === undefined) return;

    if (!trendByProvider[providerKey]) {
      trendByProvider[providerKey] = Array.from({ length: dayKeys.length }, () => 0);
    }

    const tokenCount = Number.isFinite(row.total_tokens) ? row.total_tokens : 0;
    trendByProvider[providerKey][dayIndex] += tokenCount;
  });

  return trendByProvider;
};

export const buildSparklinePoints = (
  series: number[],
  options?: {
    width?: number;
    height?: number;
    padding?: number;
  }
): string => {
  if (!Array.isArray(series) || series.length === 0) {
    return '';
  }

  const width = options?.width ?? 84;
  const height = options?.height ?? 24;
  const padding = options?.padding ?? 2;

  const minValue = Math.min(...series);
  const maxValue = Math.max(...series);
  const range = maxValue - minValue;
  const step = series.length > 1 ? (width - (padding * 2)) / (series.length - 1) : 0;

  return series
    .map((value, index) => {
      const x = padding + (step * index);
      const y = range === 0
        ? height / 2
        : height - padding - (((value - minValue) / range) * (height - (padding * 2)));
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');
};

