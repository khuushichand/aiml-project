type StatsRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is StatsRecord =>
  typeof value === 'object' && value !== null;

const toNumber = (value: unknown): number | undefined => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return undefined;
  }
  return value;
};

const numberFrom = (...values: unknown[]): number | undefined => {
  for (const value of values) {
    const parsed = toNumber(value);
    if (parsed !== undefined) {
      return parsed;
    }
  }
  return undefined;
};

const recordNumber = (record: StatsRecord | undefined, key: string): number | undefined =>
  numberFrom(record?.[key]);

// DashboardUIStats is a UI-only flattened shape, distinct from the canonical DashboardStats in types.
export interface DashboardUIStats {
  users: number;
  activeUsers: number;
  organizations: number;
  teams: number;
  apiKeys: number;
  activeApiKeys: number;
  providers: number;
  enabledProviders: number;
  storageUsedMb: number;
  storageQuotaMb: number;
  activeAcpSessions: number | null;
  tokensToday: { prompt: number; completion: number; total: number } | null;
  mcpInvocationsToday: number | null;
}

const extractOverrides = (statsResponse?: unknown): Partial<DashboardUIStats> => {
  if (!isRecord(statsResponse)) {
    return {};
  }

  const users = isRecord(statsResponse.users) ? statsResponse.users : undefined;
  const storage = isRecord(statsResponse.storage) ? statsResponse.storage : undefined;
  const apiKeys = isRecord(statsResponse.api_keys) ? statsResponse.api_keys : undefined;
  const providers = isRecord(statsResponse.providers) ? statsResponse.providers : undefined;

  return {
    users: numberFrom(
      recordNumber(users, 'total'),
      statsResponse['total_users'],
      statsResponse['users'],
      statsResponse['users_total'],
      statsResponse['totalUsers']
    ),
    activeUsers: numberFrom(
      recordNumber(users, 'active'),
      statsResponse['active_users'],
      statsResponse['activeUsers']
    ),
    organizations: numberFrom(
      statsResponse['total_organizations'],
      statsResponse['organizations']
    ),
    teams: numberFrom(
      statsResponse['total_teams'],
      statsResponse['teams']
    ),
    apiKeys: numberFrom(
      recordNumber(apiKeys, 'total'),
      statsResponse['total_api_keys'],
      statsResponse['api_keys'],
      statsResponse['apiKeys']
    ),
    activeApiKeys: numberFrom(
      recordNumber(apiKeys, 'active'),
      statsResponse['active_api_keys'],
      statsResponse['activeApiKeys']
    ),
    providers: numberFrom(
      recordNumber(providers, 'total'),
      statsResponse['total_providers'],
      statsResponse['providers']
    ),
    enabledProviders: numberFrom(
      recordNumber(providers, 'enabled'),
      statsResponse['enabled_providers'],
      statsResponse['enabledProviders']
    ),
    storageUsedMb: numberFrom(
      recordNumber(storage, 'total_used_mb'),
      statsResponse['storage_used_mb'],
      statsResponse['storageUsedMb']
    ),
    storageQuotaMb: numberFrom(
      recordNumber(storage, 'total_quota_mb'),
      statsResponse['storage_quota_mb'],
      statsResponse['storageQuotaMb']
    ),
  };
};

export function buildDashboardUIStats({
  computedStats,
  statsResponse,
}: {
  computedStats: DashboardUIStats;
  statsResponse?: unknown;
}): DashboardUIStats {
  const overrides = extractOverrides(statsResponse);
  const merged: DashboardUIStats = { ...computedStats };

  (Object.keys(overrides) as Array<keyof DashboardUIStats>).forEach((key) => {
    const value = overrides[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic numeric override merge
      (merged as any)[key] = value;
    }
  });

  return merged;
}
