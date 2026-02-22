import fs from 'node:fs/promises';
import path from 'node:path';
import { test, expect } from '@playwright/test';
import { seedAuth } from './smoke.setup';

const TELEMETRY_KEY = 'tldw:route:alias:telemetry';
const LOAD_TIMEOUT = 30_000;

type RollupRow = {
  path: string;
  hits: number;
  share: number;
};

type TelemetryState = {
  counters?: Record<string, number>;
  alias_hits?: Record<string, number>;
  destination_hits?: Record<string, number>;
  last_event_at?: number | null;
  last_redirect?: {
    source_path: string;
    destination_path: string;
    preserve_params: boolean;
    query_or_hash_carried: boolean;
  } | null;
};

const toRollupRows = (
  map: Record<string, number>,
  total: number,
  limit: number,
): RollupRow[] => {
  if (!Number.isFinite(total) || total <= 0) return [];

  return Object.entries(map)
    .sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return a[0].localeCompare(b[0]);
    })
    .slice(0, limit)
    .map(([route, hits]) => ({
      path: route,
      hits,
      share: hits / total,
    }));
};

test('captures week-3 natural alias telemetry rollup', async ({ page }, testInfo) => {
  await seedAuth(page);

  // Passive capture only: do not clear storage and do not trigger synthetic alias flows.
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: LOAD_TIMEOUT });
  await page.waitForLoadState('networkidle', { timeout: LOAD_TIMEOUT }).catch(() => {});

  const telemetryState = await page.evaluate((key) => {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return { parse_error: true, raw };
    }
  }, TELEMETRY_KEY);

  expect((telemetryState as { parse_error?: boolean } | null)?.parse_error).not.toBe(true);

  const typedState = (telemetryState ?? {}) as TelemetryState;
  const totalRedirects = typedState.counters?.route_alias_redirect ?? 0;
  const topAliasSources = toRollupRows(typedState.alias_hits ?? {}, totalRedirects, 10);
  const topDestinations = toRollupRows(typedState.destination_hits ?? {}, totalRedirects, 10);

  const capture = {
    captured_at: new Date().toISOString(),
    source: 'natural-passive-session',
    run_context: {
      base_url: testInfo.project.use.baseURL,
      browser: testInfo.project.name,
      seeded_auth: true,
      synthetic_alias_flows_executed: false,
    },
    rollup: {
      total_redirects: totalRedirects,
      last_event_at: typedState.last_event_at ?? null,
      top_alias_sources: topAliasSources,
      top_destinations: topDestinations,
      last_redirect: typedState.last_redirect ?? null,
    },
  };

  const outputPath = path.resolve(
    process.cwd(),
    '../../Docs/Product/WebUI/M1_4_Alias_Rollup_Week3_Natural_2026_02_13.json',
  );
  await fs.writeFile(outputPath, `${JSON.stringify(capture, null, 2)}\n`, 'utf8');

  testInfo.annotations.push({
    type: 'alias-rollup-output',
    description: outputPath,
  });

  console.log(`\\nNatural alias rollup written to: ${outputPath}`);
  console.log(`Natural alias rollup total redirects: ${totalRedirects}`);
});
