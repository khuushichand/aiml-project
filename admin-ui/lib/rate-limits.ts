export const RATE_LIMIT_REQUIRED_ERROR = 'Please specify at least one rate limit';
export const RATE_LIMIT_MINIMUM_ERROR =
  'Hourly/daily limits must be at least 60/1440 to convert to per-minute limits. Set a per-minute limit or increase the values.';

export const normalizeRateLimitValue = (value: number | null): number | null => {
  if (value === null) return null;
  return value > 0 ? value : null;
};

export const deriveLimitPerMinute = (value: number | null, divisor: number): number | null => {
  if (value === null) return null;
  const perMinute = Math.floor(value / divisor);
  return perMinute > 0 ? perMinute : null;
};

export const getDerivedLimitPerMin = (
  rpm: number | null,
  rph: number | null,
  rpd: number | null
): number | null =>
  rpm ?? deriveLimitPerMinute(rph, 60) ?? deriveLimitPerMinute(rpd, 1440);

export const validateRateLimitInputs = (
  rpm: number | null,
  rph: number | null,
  rpd: number | null
): { error: string | null; derivedLimitPerMin: number | null } => {
  const hasAny = rpm !== null || rph !== null || rpd !== null;
  if (!hasAny) {
    return { error: RATE_LIMIT_REQUIRED_ERROR, derivedLimitPerMin: null };
  }
  const derivedLimitPerMin = getDerivedLimitPerMin(rpm, rph, rpd);
  if (derivedLimitPerMin === null) {
    return { error: RATE_LIMIT_MINIMUM_ERROR, derivedLimitPerMin };
  }
  return { error: null, derivedLimitPerMin };
};
