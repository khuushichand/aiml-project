import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrl } from '@/lib/api-config';
import { setApiKeySessionCookies } from '@/lib/server-auth';

const isAdminApiKeyLoginEnabled = (): boolean =>
  process.env.ADMIN_UI_ALLOW_API_KEY_LOGIN === 'true'
  || process.env.NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN === 'true';

const isEnterpriseAdminUiMode = (): boolean =>
  process.env.ADMIN_UI_ENTERPRISE_MODE === 'true';

const isSingleUserAuthMode = (): boolean =>
  process.env.AUTH_MODE === 'single_user';

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (isEnterpriseAdminUiMode() || !isAdminApiKeyLoginEnabled() || !isSingleUserAuthMode()) {
    return NextResponse.json(
      { detail: 'Admin UI API key login is disabled. Use multi-user credentials.' },
      { status: 403 }
    );
  }

  const body = await request.json().catch(() => null) as { apiKey?: string } | null;
  const apiKey = body?.apiKey?.trim();

  if (!apiKey) {
    return NextResponse.json({ detail: 'API key is required' }, { status: 400 });
  }

  const response = await fetch(buildApiUrl('/users/me'), {
    method: 'GET',
    headers: {
      'X-API-KEY': apiKey,
    },
    cache: 'no-store',
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload) {
    return NextResponse.json(payload ?? { detail: 'API key validation failed' }, { status: response.status });
  }

  const nextResponse = NextResponse.json({ user: payload }, { status: 200 });
  setApiKeySessionCookies(nextResponse, apiKey);
  return nextResponse;
}
