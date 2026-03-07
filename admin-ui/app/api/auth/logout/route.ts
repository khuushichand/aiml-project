import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrl } from '@/lib/api-config';
import { clearAdminSessionCookies, getBackendAuthHeaders } from '@/lib/server-auth';

export async function POST(request: NextRequest): Promise<NextResponse> {
  const headers = getBackendAuthHeaders(request);

  await fetch(buildApiUrl('/auth/logout'), {
    method: 'POST',
    headers,
    cache: 'no-store',
  }).catch(() => {
    // Best-effort server logout. Local session cookies are still cleared below.
  });

  const response = NextResponse.json({ ok: true });
  clearAdminSessionCookies(response);
  return response;
}
