import type { NextApiRequest, NextApiResponse } from 'next';

import { buildApiUrlForRequest } from '@web/lib/api-config';
import {
  appendProxyHeaders,
  getBackendAuthHeaders,
  getRequestBody,
  sendMethodNotAllowed,
  setForwardedResponseHeaders,
} from '@web/lib/server-auth';

const ALLOWED_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

const getBackendPath = (request: NextApiRequest): string => {
  const rawPath = request.query.path;
  if (Array.isArray(rawPath) && rawPath.length > 0) {
    return `/${rawPath.map((segment) => encodeURIComponent(segment)).join('/')}`;
  }
  if (typeof rawPath === 'string' && rawPath.trim()) {
    return `/${encodeURIComponent(rawPath.trim())}`;
  }
  return '/';
};

export default async function handler(
  request: NextApiRequest,
  response: NextApiResponse,
): Promise<void> {
  if (!request.method || !ALLOWED_METHODS.includes(request.method)) {
    sendMethodNotAllowed(response, ALLOWED_METHODS);
    return;
  }

  const backendUrl = new URL(
    buildApiUrlForRequest(request, getBackendPath(request)),
  );
  const requestUrl = new URL(request.url || '/api/proxy', 'http://localhost');
  backendUrl.search = requestUrl.search;

  const headers = getBackendAuthHeaders(request);
  appendProxyHeaders(request, headers);

  const backendResponse = await fetch(backendUrl.toString(), {
    method: request.method,
    headers,
    body: getRequestBody(request),
  });

  setForwardedResponseHeaders(backendResponse, response);
  response.status(backendResponse.status);

  const contentType = backendResponse.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    response.json(await backendResponse.json().catch(() => null));
    return;
  }

  const body = Buffer.from(await backendResponse.arrayBuffer());
  if (!body.length) {
    response.end();
    return;
  }
  response.send(body);
}
