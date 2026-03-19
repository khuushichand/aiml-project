import { describe, expect, it } from 'vitest';

import {
  buildHostedSessionCookies,
  clearHostedSessionCookies,
} from '@web/lib/server-auth';

describe('hosted server auth', () => {
  it('sets httpOnly access and refresh cookies', () => {
    const cookies = buildHostedSessionCookies({
      accessToken: 'access-1',
      refreshToken: 'refresh-1',
      expiresIn: 1800,
    });

    expect(cookies.access.httpOnly).toBe(true);
    expect(cookies.refresh.httpOnly).toBe(true);
    expect(cookies.session.httpOnly).toBe(false);
    expect(cookies.authMode.value).toBe('jwt');
  });

  it('clears hosted session cookies on logout', () => {
    const cookies = clearHostedSessionCookies();

    expect(cookies.access.maxAge).toBe(0);
    expect(cookies.refresh.maxAge).toBe(0);
    expect(cookies.session.maxAge).toBe(0);
    expect(cookies.authMode.maxAge).toBe(0);
  });
});
