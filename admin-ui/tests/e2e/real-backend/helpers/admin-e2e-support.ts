export const ADMIN_E2E_SUPPORT_HEADER = 'X-TLDW-Admin-E2E-Key';
export const ADMIN_E2E_SUPPORT_KEY_ENV = 'TLDW_ADMIN_E2E_SUPPORT_KEY';
export const DEFAULT_ADMIN_E2E_SUPPORT_KEY = 'playwright-admin-e2e-support-key';

export const getAdminE2ESupportKey = (): string =>
  process.env[ADMIN_E2E_SUPPORT_KEY_ENV]?.trim() || DEFAULT_ADMIN_E2E_SUPPORT_KEY;

export const getAdminE2ESupportHeaders = (): Record<string, string> => ({
  [ADMIN_E2E_SUPPORT_HEADER]: getAdminE2ESupportKey(),
});

export const postAdminE2EJson = async <T>(
  baseUrl: string,
  path: string,
  body?: unknown,
): Promise<T> => {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: {
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...getAdminE2ESupportHeaders(),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(`Admin e2e request failed for ${path}: ${response.status} ${detail}`.trim());
  }

  return response.json() as Promise<T>;
};
