import { NextResponse } from 'next/server';

let appVersion = '0.0.0';
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  appVersion = require('../../../package.json').version;
} catch {
  // Standalone builds may not bundle package.json.
}

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(
    {
      status: 'ok',
      timestamp: new Date().toISOString(),
      version: appVersion,
    },
    {
      status: 200,
      headers: { 'Cache-Control': 'no-store' },
    }
  );
}
