import { type Page } from '@playwright/test';

import { getFixturePassword } from './fixture-secrets';
import { type RealBackendProjectEnv } from './project-env';

export type SeedScenario = 'jwt_admin' | 'dsr_jwt_admin' | 'single_user_admin';
export type SeedAlias = 'admin' | 'owner' | 'super_admin' | 'non_admin';

type SeededUser = {
  id: number;
  key: string;
  username: string;
  email: string;
};

type SeededAlertFixture = {
  alert_id: string;
  alert_identity?: string;
  message?: string;
};

export type SeedResponse = {
  users: Record<SeedAlias | 'requester', SeededUser>;
  fixtures: {
    alerts: SeededAlertFixture[];
    organizations?: Array<{ id: number; name: string; slug: string }>;
  };
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
    private readonly page: Page,
    private readonly projectEnv: RealBackendProjectEnv,
  ) {}

  private getPasswordForAlias(alias: SeedAlias): string {
    if (alias === 'admin') {
      return getFixturePassword('admin');
    }
    if (alias === 'owner') {
      return getFixturePassword('owner');
    }
    if (alias === 'super_admin') {
      return getFixturePassword('super_admin');
    }
    return getFixturePassword('member');
  }

  private async primeAuthenticatedSession(): Promise<void> {
    await this.page.waitForURL(/\/login(?:\?|$)/, { timeout: 5_000 }).catch(() => null);

    let lastCurrentUserStatus = 0;

    for (let attempt = 0; attempt < 60; attempt += 1) {
      const currentUser = await this.page.evaluate(async () => {
        try {
          const response = await fetch('/api/proxy/users/me', {
            credentials: 'include',
          });
          const body = await response.json().catch(() => null);
          if (response.ok && body) {
            localStorage.setItem('user', JSON.stringify(body));
          }
          return {
            ok: response.ok,
            status: response.status,
            body,
          };
        } catch {
          return {
            ok: false,
            status: 0,
            body: null,
          };
        }
      });
      lastCurrentUserStatus = currentUser.status;

      if (currentUser.ok && currentUser.body && typeof currentUser.body.id === 'number') {
        return;
      }

      await this.page.waitForTimeout(250);
    }

    throw new Error(
      `Seeded session did not reach an authenticated browser state (last /users/me status=${lastCurrentUserStatus})`,
    );
  }

  async seed(scenario: SeedScenario = 'jwt_admin'): Promise<SeedResponse> {
    return postJson<SeedResponse>(
      this.projectEnv.apiBaseUrl,
      '/api/v1/test-support/admin-e2e/seed',
      { scenario },
    );
  }

  async as(alias: SeedAlias, scenario: SeedScenario = 'jwt_admin'): Promise<SeedResponse> {
    const seed = await this.seed(scenario);
    const principal = seed.users[alias];
    if (!principal) {
      throw new Error(`Missing seeded principal for alias '${alias}'`);
    }

    if (this.projectEnv.authMode === 'multi_user') {
      let loginResult: { ok: boolean; status: number } | null = null;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        await this.page.goto('/login?postAuthSmoke=1');
        loginResult = await this.page.evaluate(
          async ({ username, password }) => {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            try {
              const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData.toString(),
                credentials: 'include',
              });
              return {
                ok: response.ok,
                status: response.status,
              };
            } catch {
              return {
                ok: false,
                status: 0,
              };
            }
          },
          {
            username: principal.username,
            password: this.getPasswordForAlias(alias),
          },
        );
        if (loginResult.ok) {
          break;
        }
        if (loginResult.status !== 404 && loginResult.status < 500) {
          break;
        }
        await this.page.waitForTimeout(1_000);
      }
      if (!loginResult?.ok) {
        throw new Error(`Seeded session login failed with status ${loginResult?.status ?? 0}`);
      }
    } else {
      let loginResult: { ok: boolean; status: number } | null = null;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        await this.page.goto('/login?postAuthSmoke=1');
        loginResult = await this.page.evaluate(
          async ({ apiKey }) => {
            try {
              const response = await fetch('/api/auth/apikey', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({ apiKey }),
                credentials: 'include',
              });
              return {
                ok: response.ok,
                status: response.status,
              };
            } catch {
              return {
                ok: false,
                status: 0,
              };
            }
          },
          {
            apiKey: principal.key,
          },
        );
        if (loginResult.ok) {
          break;
        }
        if (loginResult.status !== 404 && loginResult.status < 500) {
          break;
        }
        await this.page.waitForTimeout(1_000);
      }
      if (!loginResult?.ok) {
        throw new Error(`Seeded session login failed with status ${loginResult?.status ?? 0}`);
      }
    }
    await this.page.goto('/login?postAuthSmoke=1');
    await this.primeAuthenticatedSession();
    return seed;
  }
}
