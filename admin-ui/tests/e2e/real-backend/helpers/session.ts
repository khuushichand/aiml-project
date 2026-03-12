import { type Page } from '@playwright/test';

import { type RealBackendProjectEnv } from './project-env';

type SeedScenario = 'jwt_admin' | 'dsr_jwt_admin';
type SeedAlias = 'admin' | 'non_admin';

export type SeedResponse = {
  users: Record<SeedAlias | 'requester', { key: string; username: string; email: string }>;
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
      return process.env.TLDW_ADMIN_E2E_ADMIN_PASSWORD || 'AdminPass123!';
    }
    return process.env.TLDW_ADMIN_E2E_MEMBER_PASSWORD || 'MemberPass123!';
  }

  private async primeAuthenticatedSession(): Promise<void> {
    await this.page.waitForURL(/\/login(?:\?|$)/, { timeout: 5_000 }).catch(() => null);

    let lastCurrentUserStatus = 0;
    let lastWarmFailure = 'not_attempted';

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
        const warmed = await this.page.evaluate(async ({ userId }) => {
          const endpoints = [
            `/api/proxy/admin/users/${userId}/effective-permissions`,
            '/api/proxy/admin/orgs',
          ];
          for (const endpoint of endpoints) {
            const response = await fetch(endpoint, { credentials: 'include' }).catch(() => null);
            if (!response || !response.ok) {
              return {
                ok: false,
                failedEndpoint: endpoint,
                status: response?.status ?? 0,
              };
            }
          }
          return {
            ok: true,
            failedEndpoint: null,
            status: 200,
          };
        }, { userId: currentUser.body.id });
        if (warmed.ok) {
          return;
        }
        lastWarmFailure = `${warmed.failedEndpoint ?? 'unknown'}:${warmed.status}`;
      }

      await this.page.waitForTimeout(250);
    }

    throw new Error(
      `Seeded session did not reach an authenticated browser state (last /users/me status=${lastCurrentUserStatus}, last warm failure=${lastWarmFailure})`,
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
    }
    await this.page.goto('/login?postAuthSmoke=1');
    await this.primeAuthenticatedSession();
    return seed;
  }
}
