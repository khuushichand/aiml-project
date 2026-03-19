import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  getRequestBody,
  readBackendJson,
  readRequestContentType,
  sendMethodNotAllowed,
} from '@web/lib/server-auth';

export default async function handler(
  request: NextApiRequest,
  response: NextApiResponse,
): Promise<void> {
  if (request.method !== 'POST') {
    sendMethodNotAllowed(response, ['POST']);
    return;
  }

  const backendResponse = await fetch(
    buildApiUrlForRequest(request, '/auth/magic-link/request'),
    {
      method: 'POST',
      headers: {
        'Content-Type': readRequestContentType(request) || 'application/json',
      },
      body: getRequestBody(request),
    },
  );

  response
    .status(backendResponse.status)
    .json((await readBackendJson<Record<string, unknown>>(backendResponse)) ?? {
      detail: 'Magic link request failed',
    });
}
