import { describe, it, expect } from '@jest/globals';
import { buildDashboardUIStats, type DashboardUIStats } from './dashboard';

const baseStats: DashboardUIStats = {
  users: 10,
  activeUsers: 7,
  organizations: 3,
  teams: 2,
  apiKeys: 4,
  activeApiKeys: 3,
  providers: 5,
  enabledProviders: 4,
  storageUsedMb: 120,
  storageQuotaMb: 500,
};

describe('buildDashboardUIStats', () => {
  it('returns computed stats when response is missing', () => {
    const result = buildDashboardUIStats({ computedStats: baseStats });
    expect(result).toEqual(baseStats);
  });

  it('overrides computed stats with nested system stats response', () => {
    const response = {
      users: { total: 20, active: 15 },
      storage: { total_used_mb: 300, total_quota_mb: 600 },
      api_keys: { total: 8, active: 5 },
      providers: { total: 9, enabled: 7 },
      total_organizations: 6,
      total_teams: 4,
    };

    const result = buildDashboardUIStats({
      computedStats: baseStats,
      statsResponse: response,
    });

    expect(result.users).toBe(20);
    expect(result.activeUsers).toBe(15);
    expect(result.organizations).toBe(6);
    expect(result.teams).toBe(4);
    expect(result.apiKeys).toBe(8);
    expect(result.activeApiKeys).toBe(5);
    expect(result.providers).toBe(9);
    expect(result.enabledProviders).toBe(7);
    expect(result.storageUsedMb).toBe(300);
    expect(result.storageQuotaMb).toBe(600);
  });

  it('overrides computed stats with flat totals response', () => {
    const response = {
      total_users: 2,
      active_users: 1,
      organizations: 9,
      teams: 11,
      total_api_keys: 12,
      active_api_keys: 10,
      total_providers: 4,
      enabled_providers: 3,
      storage_used_mb: 42,
      storage_quota_mb: 100,
    };

    const result = buildDashboardUIStats({
      computedStats: baseStats,
      statsResponse: response,
    });

    expect(result.users).toBe(2);
    expect(result.activeUsers).toBe(1);
    expect(result.organizations).toBe(9);
    expect(result.teams).toBe(11);
    expect(result.apiKeys).toBe(12);
    expect(result.activeApiKeys).toBe(10);
    expect(result.providers).toBe(4);
    expect(result.enabledProviders).toBe(3);
    expect(result.storageUsedMb).toBe(42);
    expect(result.storageQuotaMb).toBe(100);
  });
});
