import { describe, expect, it } from 'vitest';
import {
  buildUsageCostForecast,
  calculateLinearRegression,
  normalizeDailyCostPoints,
  type DailyCostPoint,
} from './usage-forecast';

describe('usage-forecast', () => {
  it('calculates linear regression with increasing slope', () => {
    const regression = calculateLinearRegression([10, 20, 30, 40, 50]);
    expect(regression.slope).toBeGreaterThan(0);
    expect(regression.intercept).toBeGreaterThanOrEqual(0);
  });

  it('builds confidence bands for 7/30/90 day horizons', () => {
    const points: DailyCostPoint[] = [
      { day: '2026-02-01', costUsd: 10 },
      { day: '2026-02-02', costUsd: 12 },
      { day: '2026-02-03', costUsd: 14 },
      { day: '2026-02-04', costUsd: 16 },
      { day: '2026-02-05', costUsd: 18 },
      { day: '2026-02-06', costUsd: 20 },
      { day: '2026-02-07', costUsd: 22 },
      { day: '2026-02-08', costUsd: 24 },
      { day: '2026-02-09', costUsd: 26 },
      { day: '2026-02-10', costUsd: 28 },
      { day: '2026-02-11', costUsd: 30 },
    ];

    const forecast = buildUsageCostForecast(points);
    expect(forecast.bands).toHaveLength(3);
    forecast.bands.forEach((band) => {
      expect(band.lowEstimateUsd).toBeLessThanOrEqual(band.expectedCostUsd);
      expect(band.expectedCostUsd).toBeLessThanOrEqual(band.highEstimateUsd);
      expect(['low', 'medium', 'high']).toContain(band.confidence);
    });
  });

  it('projects a budget exceed date when trend crosses monthly budget', () => {
    const points = normalizeDailyCostPoints([
      { group_value: '2026-02-10', total_cost_usd: 10 },
      { group_value: '2026-02-11', total_cost_usd: 12 },
      { group_value: '2026-02-12', total_cost_usd: 14 },
      { group_value: '2026-02-13', total_cost_usd: 16 },
      { group_value: '2026-02-14', total_cost_usd: 18 },
    ]);

    const forecast = buildUsageCostForecast(points, 120);
    expect(forecast.budgetExceededByDate).toBeTruthy();
  });
});
