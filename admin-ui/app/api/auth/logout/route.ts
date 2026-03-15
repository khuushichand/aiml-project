import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrlForRequest } from '@/lib/api-config';
import { clearAdminSessionCookies, getBackendAuthHeaders } from '@/lib/server-auth';

export async function POST(request: NextRequest): Promise<NextResponse> {
  const headers = getBackendAuthHeaders(request);

  try {
    await fetch(buildApiUrlForRequest(request, '/auth/logout'), {
      method: 'POST',
      headers,
      cache: 'no-store',
    });
  } catch (error) {
    console.warn('Admin UI backend logout failed', {
      error: error instanceof Error ? error.message : String(error),
    });
  }

  const response = NextResponse.json({ ok: true });
  clearAdminSessionCookies(response);
  return response;
}
