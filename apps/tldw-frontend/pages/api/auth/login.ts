import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  readBackendJson,
  readRequestContentType,
  sanitizeTokenPayload,
  sendMethodNotAllowed,
  setHostedSessionCookies,
} from '@web/lib/server-auth';

type LoginResponsePayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
  session_token?: string;
  mfa_required?: boolean;
  message?: string;
  detail?: string;
};

export default async function handler(
  request: NextApiRequest,
  response: NextApiResponse,
): Promise<void> {
  if (request.method !== 'POST') {
    sendMethodNotAllowed(response, ['POST']);
    return;
  }

  const backendResponse = await fetch(buildApiUrlForRequest(request, '/auth/login'), {
    method: 'POST',
    headers: {
      'Content-Type': readRequestContentType(request) || 'application/x-www-form-urlencoded',
    },
    body: typeof request.body === 'string' ? request.body : String(request.body || ''),
  });

  const payload = await readBackendJson<LoginResponsePayload>(backendResponse);
  if (
    backendResponse.ok &&
    payload &&
    typeof payload.access_token === 'string'
  ) {
    setHostedSessionCookies(response, {
      accessToken: payload.access_token,
      refreshToken: payload.refresh_token,
      expiresIn: payload.expires_in,
    });
  }

  response.status(backendResponse.status).json(
    sanitizeTokenPayload(payload as Record<string, unknown> | null) ?? {
      detail: 'Login failed',
    },
  );
}
