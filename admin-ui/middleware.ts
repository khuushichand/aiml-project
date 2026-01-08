import { NextRequest, NextResponse } from 'next/server';

const AUTH_COOKIE_NAMES = ['access_token', 'x_api_key', 'x-api-key'];

const hasAuthCookie = (request: NextRequest): boolean =>
  AUTH_COOKIE_NAMES.some((name) => {
    const cookie = request.cookies.get(name);
    return !!cookie?.value?.trim();
  });

const hasAuthHeader = (request: NextRequest): boolean => {
  const authorization = request.headers.get('authorization');
  if (authorization && authorization.trim()) {
    return true;
  }
  const apiKey = request.headers.get('x-api-key');
  return !!apiKey?.trim();
};

const hasAuthSession = (request: NextRequest): boolean =>
  hasAuthCookie(request) || hasAuthHeader(request);

export function middleware(request: NextRequest) {
  if (hasAuthSession(request)) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = '/login';
  loginUrl.searchParams.set(
    'redirectTo',
    `${request.nextUrl.pathname}${request.nextUrl.search}`
  );
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ['/((?!login(?:/|$)|api(?:/|$)|_next|.*\\..*).*)'],
};
