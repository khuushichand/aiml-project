import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  clearHostedSessionOnResponse,
  getBackendAuthHeaders,
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

  try {
    const headers = getBackendAuthHeaders(request);
    await fetch(buildApiUrlForRequest(request, '/auth/logout'), {
      method: 'POST',
      headers: Object.fromEntries(headers.entries()),
    });
  } catch (error) {
    console.warn('Hosted frontend backend logout failed', {
      error: error instanceof Error ? error.message : String(error),
    });
  }

  clearHostedSessionOnResponse(response);
  response.status(200).json({ ok: true });
}
