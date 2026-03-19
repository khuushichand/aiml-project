import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  clearHostedSessionOnResponse,
  getBackendAuthHeaders,
  readBackendJson,
  readHostedSessionState,
  sendMethodNotAllowed,
} from '@web/lib/server-auth';

export default async function handler(
  request: NextApiRequest,
  response: NextApiResponse,
): Promise<void> {
  if (request.method !== 'GET') {
    sendMethodNotAllowed(response, ['GET']);
    return;
  }

  const session = readHostedSessionState(request);
  if (!session.accessToken) {
    response.status(200).json({
      authenticated: false,
      authMode: null,
      user: null,
    });
    return;
  }

  const backendResponse = await fetch(buildApiUrlForRequest(request, '/users/me'), {
    method: 'GET',
    headers: Object.fromEntries(getBackendAuthHeaders(request).entries()),
  });

  if (!backendResponse.ok) {
    clearHostedSessionOnResponse(response);
    response.status(200).json({
      authenticated: false,
      authMode: null,
      user: null,
    });
    return;
  }

  const user = await readBackendJson<Record<string, unknown>>(backendResponse);
  response.status(200).json({
    authenticated: true,
    authMode: session.authMode || 'jwt',
    user,
  });
}
