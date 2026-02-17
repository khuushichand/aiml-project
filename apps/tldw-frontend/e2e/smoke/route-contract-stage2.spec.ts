import fs from 'node:fs/promises';
import path from 'node:path';
import { test, expect, seedAuth } from './smoke.setup';

const LOAD_TIMEOUT = 30_000;
const OUTPUT_DATE = process.env.TLDW_STAGE2_OUTPUT_DATE;
const OUTPUT_SUFFIX = process.env.TLDW_STAGE2_OUTPUT_SUFFIX;
const OUTPUT_FILE = OUTPUT_DATE
  ? `stage2_route_contract_check_${OUTPUT_DATE}${OUTPUT_SUFFIX ? `_${OUTPUT_SUFFIX}` : ''}.json`
  : 'stage2_route_contract_check_2026-02-16.json';
const OUTPUT_PATH = path.resolve(process.cwd(), `../../Docs/Plans/artifacts/${OUTPUT_FILE}`);

type RouteContract = {
  route: string;
  expectedTitle: string;
  disallowedFinalPaths: string[];
};

type RouteContractResult = {
  route: string;
  status: number;
  finalPath: string;
  redirected: boolean;
  hasPlaceholderPanel: boolean;
  hasRedirectPanel: boolean;
  hasExpectedTitle: boolean;
};

const ROUTE_CONTRACTS: RouteContract[] = [
  {
    route: '/admin/data-ops',
    expectedTitle: 'Data Operations Is Coming Soon',
    disallowedFinalPaths: ['/admin/server'],
  },
  {
    route: '/admin/watchlists-runs',
    expectedTitle: 'Watchlist Runs Admin Is Coming Soon',
    disallowedFinalPaths: ['/admin/server'],
  },
  {
    route: '/admin/watchlists-items',
    expectedTitle: 'Watchlist Items Admin Is Coming Soon',
    disallowedFinalPaths: ['/admin/server'],
  },
  {
    route: '/connectors',
    expectedTitle: 'Connectors Hub Is Coming Soon',
    disallowedFinalPaths: ['/settings'],
  },
  {
    route: '/connectors/sources',
    expectedTitle: 'Connector Sources Is Coming Soon',
    disallowedFinalPaths: ['/settings'],
  },
  {
    route: '/connectors/jobs',
    expectedTitle: 'Connector Jobs Is Coming Soon',
    disallowedFinalPaths: ['/settings'],
  },
  {
    route: '/connectors/browse',
    expectedTitle: 'Connector Browse Is Coming Soon',
    disallowedFinalPaths: ['/settings'],
  },
  {
    route: '/profile',
    expectedTitle: 'Profile Page Is Coming Soon',
    disallowedFinalPaths: ['/settings'],
  },
  {
    route: '/config',
    expectedTitle: 'Configuration Center Is Coming Soon',
    disallowedFinalPaths: ['/settings'],
  },
  {
    route: '/admin/orgs',
    expectedTitle: 'Organization Management Is Coming Soon',
    disallowedFinalPaths: ['/admin/server'],
  },
  {
    route: '/admin/maintenance',
    expectedTitle: 'Maintenance Console Is Coming Soon',
    disallowedFinalPaths: ['/admin/server'],
  },
];

test.describe('Stage 2 route contracts', () => {
  test('wrong-content routes render placeholders and do not misroute', async ({ page }, testInfo) => {
    await seedAuth(page);
    const results: RouteContractResult[] = [];

    for (const contract of ROUTE_CONTRACTS) {
      const response = await page.goto(contract.route, {
        waitUntil: 'domcontentloaded',
        timeout: LOAD_TIMEOUT,
      });
      await page.waitForLoadState('networkidle', { timeout: LOAD_TIMEOUT }).catch(() => {});

      const status = response?.status() ?? 0;
      const finalPath = new URL(page.url()).pathname;
      const hasPlaceholderPanel = await page
        .getByTestId('route-placeholder-panel')
        .isVisible()
        .catch(() => false);
      const hasRedirectPanel = (await page.getByTestId('route-redirect-panel').count()) > 0;
      const hasExpectedTitle =
        (await page.getByRole('heading', { name: contract.expectedTitle }).count()) > 0;
      const redirected = finalPath !== contract.route;

      results.push({
        route: contract.route,
        status,
        finalPath,
        redirected,
        hasPlaceholderPanel,
        hasRedirectPanel,
        hasExpectedTitle,
      });

      expect(
        status,
        `Expected HTTP 2xx/3xx for ${contract.route}, received status ${status}`
      ).toBeGreaterThanOrEqual(200);
      expect(
        status,
        `Expected HTTP 2xx/3xx for ${contract.route}, received status ${status}`
      ).toBeLessThan(400);

      expect(
        finalPath,
        `Expected ${contract.route} to remain on its own route and not auto-redirect`
      ).toBe(contract.route);
      expect(
        contract.disallowedFinalPaths.includes(finalPath),
        `Route ${contract.route} unexpectedly landed on disallowed path ${finalPath}`
      ).toBe(false);
      expect(
        hasPlaceholderPanel,
        `Expected ${contract.route} to render route placeholder panel`
      ).toBe(true);
      expect(
        hasRedirectPanel,
        `Expected ${contract.route} to avoid RouteRedirect panel`
      ).toBe(false);
      expect(
        hasExpectedTitle,
        `Expected ${contract.route} placeholder title to be "${contract.expectedTitle}"`
      ).toBe(true);
    }

    const artifact = {
      generatedAt: new Date().toISOString(),
      baseUrl: testInfo.project.use.baseURL,
      routeCount: ROUTE_CONTRACTS.length,
      results,
    };

    await fs.writeFile(OUTPUT_PATH, `${JSON.stringify(artifact, null, 2)}\n`, 'utf8');
    testInfo.annotations.push({
      type: 'stage2-route-contract-artifact',
      description: OUTPUT_PATH,
    });
  });
});
