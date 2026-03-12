import { type BrowserContext } from '@playwright/test';

import { type RealBackendProjectEnv } from './project-env';

type SeedScenario = 'jwt_admin' | 'dsr_jwt_admin';
type SeedAlias = 'admin' | 'non_admin';

type SeedResponse = {
  users: Record<SeedAlias | 'requester', { key: string }>;
};

type BootstrapCookie = {
  name: string;
  value: string;
  path?: string;
  http_only?: boolean;
  same_site?: 'Lax' | 'Strict' | 'None';
};

type BootstrapResponse = {
  cookies: BootstrapCookie[];
};

const postJson = async <T>(
  baseUrl: string,
  path: string,
  body: unknown,
): Promise<T> => {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(`Request failed for ${path}: ${response.status} ${detail}`.trim());
  }

  return response.json() as Promise<T>;
};

export class SeededSession {
  constructor(
    private readonly context: BrowserContext,
    private readonly projectEnv: RealBackendProjectEnv,
  ) {}

  async seed(scenario: SeedScenario = 'jwt_admin'): Promise<SeedResponse> {
    return postJson<SeedResponse>(
      this.projectEnv.apiBaseUrl,
      '/api/v1/test-support/admin-e2e/seed',
      { scenario },
    );
  }

  async as(alias: SeedAlias, scenario: SeedScenario = 'jwt_admin'): Promise<void> {
    const seed = await this.seed(scenario);
    const principalKey = seed.users[alias]?.key;
    if (!principalKey) {
      throw new Error(`Missing principal key for alias '${alias}'`);
    }

    const session = await postJson<BootstrapResponse>(
      this.projectEnv.apiBaseUrl,
      '/api/v1/test-support/admin-e2e/bootstrap-jwt-session',
      { principal_key: principalKey },
    );

    await this.context.addCookies(
      session.cookies.map((cookie) => ({
        name: cookie.name,
        value: cookie.value,
        path: cookie.path || '/',
        httpOnly: Boolean(cookie.http_only),
        sameSite: cookie.same_site || 'Lax',
        url: this.projectEnv.uiBaseUrl,
      })),
    );
  }
}
