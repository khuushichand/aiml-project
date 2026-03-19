import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  getRequestBody,
  readBackendJson,
  readRequestContentType,
  sanitizeTokenPayload,
  sendMethodNotAllowed,
  setHostedSessionCookies,
} from '@web/lib/server-auth';

type MagicLinkVerifyPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
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

  const backendResponse = await fetch(
    buildApiUrlForRequest(request, '/auth/magic-link/verify'),
    {
      method: 'POST',
      headers: {
        'Content-Type': readRequestContentType(request) || 'application/json',
      },
      body: getRequestBody(request),
    },
  );

  const payload = await readBackendJson<MagicLinkVerifyPayload>(backendResponse);
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
      detail: 'Magic link verification failed',
    },
  );
}
