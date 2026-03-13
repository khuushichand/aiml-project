import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrlForRequest } from '@/lib/api-config';
import {
  appendProxyHeaders,
  buildProxyResponse,
  getBackendAuthHeaders,
  getRequestBody,
} from '@/lib/server-auth';

const forward = async (request: NextRequest): Promise<NextResponse> => {
  const backendPath = request.nextUrl.pathname.replace(/^\/api\/proxy/, '') || '/';
  const backendUrl = new URL(buildApiUrlForRequest(request, backendPath));
  backendUrl.search = request.nextUrl.search;

  const headers = getBackendAuthHeaders(request);
  appendProxyHeaders(request, headers);

  const response = await fetch(backendUrl.toString(), {
    method: request.method,
    headers,
    body: await getRequestBody(request),
    cache: 'no-store',
  });

  return buildProxyResponse(response);
};

export async function GET(request: NextRequest): Promise<NextResponse> {
  return forward(request);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  return forward(request);
}

export async function PUT(request: NextRequest): Promise<NextResponse> {
  return forward(request);
}

export async function PATCH(request: NextRequest): Promise<NextResponse> {
  return forward(request);
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  return forward(request);
}
