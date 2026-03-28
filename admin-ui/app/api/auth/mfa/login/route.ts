import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrlForRequest } from '@/lib/api-config';
import { setJwtSessionCookies } from '@/lib/server-auth';
import { checkRateLimit, extractClientIp } from '@/lib/rate-limiter';

type MfaLoginResponsePayload = {
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
};

export async function POST(request: NextRequest): Promise<NextResponse> {
  const rateCheck = checkRateLimit(extractClientIp(request.headers));
  if (!rateCheck.allowed) {
    return NextResponse.json(
      { detail: 'Too many login attempts. Please try again later.' },
      {
        status: 429,
        headers: { 'Retry-After': String(rateCheck.retryAfterSeconds) },
      }
    );
  }

  const body = await request.text();
  const response = await fetch(buildApiUrlForRequest(request, '/auth/mfa/login'), {
    method: 'POST',
    headers: {
      'Content-Type': request.headers.get('content-type') ?? 'application/json',
    },
    body,
    cache: 'no-store',
  });

  const payload = await response.json().catch(() => null) as MfaLoginResponsePayload | null;
  if (!response.ok || !payload) {
    return NextResponse.json(payload ?? { detail: 'MFA login failed' }, { status: response.status });
  }

  if (typeof payload.access_token !== 'string') {
    return NextResponse.json({ detail: 'MFA login failed' }, { status: 500 });
  }

  const nextResponse = NextResponse.json(
    {
      token_type: payload.token_type,
      expires_in: payload.expires_in,
    },
    { status: response.status }
  );

  setJwtSessionCookies(nextResponse, {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresIn: payload.expires_in,
  });

  return nextResponse;
}
