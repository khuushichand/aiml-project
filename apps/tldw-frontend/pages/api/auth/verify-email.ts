import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  readBackendJson,
  readJsonBody,
  sendMethodNotAllowed,
} from '@web/lib/server-auth';

const resolveToken = (request: NextApiRequest): string | null => {
  if (request.method === 'GET') {
    const token = Array.isArray(request.query.token)
      ? request.query.token[0]
      : request.query.token;
    return typeof token === 'string' && token.trim() ? token.trim() : null;
  }

  const body = readJsonBody<{ token?: string }>(request);
  if (typeof body?.token === 'string' && body.token.trim()) {
    return body.token.trim();
  }
  return null;
};

export default async function handler(
  request: NextApiRequest,
  response: NextApiResponse,
): Promise<void> {
  if (request.method !== 'GET' && request.method !== 'POST') {
    sendMethodNotAllowed(response, ['GET', 'POST']);
    return;
  }

  const token = resolveToken(request);
  if (!token) {
    response.status(400).json({ detail: 'Verification token is required' });
    return;
  }

  const backendResponse = await fetch(
    buildApiUrlForRequest(
      request,
      `/auth/verify-email?token=${encodeURIComponent(token)}`,
    ),
    {
      method: 'GET',
      headers: {},
    },
  );

  response
    .status(backendResponse.status)
    .json((await readBackendJson<Record<string, unknown>>(backendResponse)) ?? {
      detail: 'Email verification failed',
    });
}
