import { NextResponse } from 'next/server';
import { buildApiUrl } from '@/lib/api-config';

export async function GET(): Promise<NextResponse> {
  const timestamp = new Date().toISOString();

  // Probe backend health with 2-second timeout
  let backendReachable = false;
  let backendError: string | null = null;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const response = await fetch(buildApiUrl('/health'), {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    backendReachable = response.ok;
    if (!response.ok) {
      backendError = `Backend returned ${response.status}`;
    }
  } catch (error) {
    backendError = error instanceof Error ? error.message : 'Unknown error';
  }

  const status = backendReachable ? 'ready' : 'not_ready';
  const httpStatus = backendReachable ? 200 : 503;

  return NextResponse.json(
    {
      status,
      timestamp,
      backend: backendReachable ? 'reachable' : 'unreachable',
      ...(backendError ? { backend_error: backendError } : {}),
    },
    { status: httpStatus, headers: { 'Cache-Control': 'no-store' } }
  );
}
