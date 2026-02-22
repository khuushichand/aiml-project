export type DailyCostPoint = {
  day: string;
  costUsd: number;
};

export type ForecastConfidence = 'low' | 'medium' | 'high';

export type ForecastBand = {
  horizonDays: number;
  expectedCostUsd: number;
  lowEstimateUsd: number;
  highEstimateUsd: number;
  confidence: ForecastConfidence;
};

export type UsageCostForecast = {
  sampleSize: number;
  slopePerDayUsd: number;
  rSquared: number;
  monthlyRunRateUsd: number;
  bands: ForecastBand[];
  budgetExceededByDate: string | null;
};

type RegressionModel = {
  slope: number;
  intercept: number;
  rSquared: number;
  stdDev: number;
};

const isValidDay = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value);

const roundMoney = (value: number) => Number(value.toFixed(4));

const confidenceFromModel = (sampleSize: number, rSquared: number): ForecastConfidence => {
  if (sampleSize >= 21 && rSquared >= 0.7) return 'high';
  if (sampleSize >= 10 && rSquared >= 0.4) return 'medium';
  return 'low';
};

const marginMultiplierByConfidence: Record<ForecastConfidence, number> = {
  high: 1.0,
  medium: 1.5,
  low: 2.0,
};

const projectHorizon = (model: RegressionModel, sampleSize: number, horizonDays: number) => {
  let sum = 0;
  for (let i = 0; i < horizonDays; i += 1) {
    const x = sampleSize + i;
    const y = Math.max(0, model.intercept + model.slope * x);
    sum += y;
  }
  return sum;
};

const toUtcDate = (day: string) => new Date(`${day}T00:00:00Z`);

const getMonthKey = (day: string) => day.slice(0, 7);

const endOfUtcMonth = (day: string) => {
  const date = toUtcDate(day);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0));
};

const projectBudgetExceededByDate = (
  points: DailyCostPoint[],
  model: RegressionModel,
  monthlyBudgetUsd: number
): string | null => {
  if (!Number.isFinite(monthlyBudgetUsd) || monthlyBudgetUsd <= 0 || points.length === 0) {
    return null;
  }

  const sorted = [...points].sort((a, b) => a.day.localeCompare(b.day));
  const latest = sorted[sorted.length - 1];
  if (!latest) return null;

  const monthKey = getMonthKey(latest.day);
  let monthSpendToDate = 0;
  sorted.forEach((point) => {
    if (getMonthKey(point.day) === monthKey) {
      monthSpendToDate += point.costUsd;
    }
  });

  if (monthSpendToDate >= monthlyBudgetUsd) {
    return latest.day;
  }

  const latestDate = toUtcDate(latest.day);
  const monthEnd = endOfUtcMonth(latest.day);
  const dayMs = 24 * 60 * 60 * 1000;

  let projectedMonthTotal = monthSpendToDate;
  for (let i = 1; latestDate.getTime() + i * dayMs <= monthEnd.getTime(); i += 1) {
    const x = sorted.length - 1 + i;
    const predicted = Math.max(0, model.intercept + model.slope * x);
    projectedMonthTotal += predicted;
    if (projectedMonthTotal > monthlyBudgetUsd) {
      const exceededDate = new Date(latestDate.getTime() + i * dayMs);
      return exceededDate.toISOString().slice(0, 10);
    }
  }

  return null;
};

export const normalizeDailyCostPoints = (
  rows: Array<{ group_value?: string; total_cost_usd?: number }>
): DailyCostPoint[] => {
  const grouped = new Map<string, number>();
  rows.forEach((row) => {
    const day = typeof row.group_value === 'string' ? row.group_value.slice(0, 10) : '';
    if (!isValidDay(day)) return;
    const cost = Number(row.total_cost_usd ?? 0);
    if (!Number.isFinite(cost)) return;
    grouped.set(day, (grouped.get(day) ?? 0) + cost);
  });

  return [...grouped.entries()]
    .map(([day, costUsd]) => ({ day, costUsd }))
    .sort((a, b) => a.day.localeCompare(b.day));
};

export const calculateLinearRegression = (values: number[]): RegressionModel => {
  if (values.length === 0) {
    return { slope: 0, intercept: 0, rSquared: 0, stdDev: 0 };
  }

  const n = values.length;
  const xValues = Array.from({ length: n }, (_, index) => index);
  const xMean = xValues.reduce((sum, value) => sum + value, 0) / n;
  const yMean = values.reduce((sum, value) => sum + value, 0) / n;

  let numerator = 0;
  let denominator = 0;
  for (let i = 0; i < n; i += 1) {
    numerator += (xValues[i] - xMean) * (values[i] - yMean);
    denominator += (xValues[i] - xMean) ** 2;
  }

  const slope = denominator === 0 ? 0 : numerator / denominator;
  const intercept = yMean - slope * xMean;

  let ssRes = 0;
  let ssTot = 0;
  for (let i = 0; i < n; i += 1) {
    const predicted = intercept + slope * xValues[i];
    ssRes += (values[i] - predicted) ** 2;
    ssTot += (values[i] - yMean) ** 2;
  }

  const rSquared = ssTot === 0 ? 1 : Math.max(0, Math.min(1, 1 - ssRes / ssTot));
  const stdDev = n > 1 ? Math.sqrt(ssRes / (n - 1)) : 0;

  return {
    slope,
    intercept,
    rSquared,
    stdDev,
  };
};

export const buildUsageCostForecast = (
  points: DailyCostPoint[],
  monthlyBudgetUsd?: number | null
): UsageCostForecast => {
  if (points.length === 0) {
    return {
      sampleSize: 0,
      slopePerDayUsd: 0,
      rSquared: 0,
      monthlyRunRateUsd: 0,
      bands: [
        { horizonDays: 7, expectedCostUsd: 0, lowEstimateUsd: 0, highEstimateUsd: 0, confidence: 'low' },
        { horizonDays: 30, expectedCostUsd: 0, lowEstimateUsd: 0, highEstimateUsd: 0, confidence: 'low' },
        { horizonDays: 90, expectedCostUsd: 0, lowEstimateUsd: 0, highEstimateUsd: 0, confidence: 'low' },
      ],
      budgetExceededByDate: null,
    };
  }

  const values = points.map((point) => point.costUsd);
  const model = calculateLinearRegression(values);
  const confidence = confidenceFromModel(points.length, model.rSquared);
  const marginMultiplier = marginMultiplierByConfidence[confidence];
  const horizons = [7, 30, 90];

  const bands = horizons.map((horizonDays) => {
    const expectedCostUsd = Math.max(0, projectHorizon(model, points.length, horizonDays));
    const margin = model.stdDev * Math.sqrt(horizonDays) * marginMultiplier;
    return {
      horizonDays,
      expectedCostUsd: roundMoney(expectedCostUsd),
      lowEstimateUsd: roundMoney(Math.max(0, expectedCostUsd - margin)),
      highEstimateUsd: roundMoney(expectedCostUsd + margin),
      confidence,
    };
  });

  const monthlyBand = bands.find((band) => band.horizonDays === 30);
  const monthlyRunRateUsd = monthlyBand ? monthlyBand.expectedCostUsd : 0;
  const budgetExceededByDate = projectBudgetExceededByDate(
    points,
    model,
    Number(monthlyBudgetUsd ?? 0),
  );

  return {
    sampleSize: points.length,
    slopePerDayUsd: roundMoney(model.slope),
    rSquared: roundMoney(model.rSquared),
    monthlyRunRateUsd,
    bands,
    budgetExceededByDate,
  };
};
