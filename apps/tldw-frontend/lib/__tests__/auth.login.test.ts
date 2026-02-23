import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authService, type LoginCredentials } from '../auth';
import { apiClient } from '@web/lib/api';

vi.mock('@web/lib/api', () => {
  return {
    apiClient: {
      post: vi.fn(),
      get: vi.fn(),
    },
  };
});

const mockedApiClient = apiClient as unknown as {
  post: ReturnType<typeof vi.fn>;
  get: ReturnType<typeof vi.fn>;
};

describe('authService.login error handling', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  type ApiErrorLike = Error & {
    status?: number;
    statusCode?: number;
    detail?: string;
    retryAfter?: number;
  };

  function makeError(message: string, status?: number, detail?: string, retryAfter?: number): Error {
    const err = new Error(message) as ApiErrorLike;
    if (status !== undefined) {
      err.status = status;
      err.statusCode = status;
    }
    if (detail !== undefined) {
      err.detail = detail;
    }
    if (retryAfter !== undefined) {
      err.retryAfter = retryAfter;
    }
    return err;
  }

  const credentials: LoginCredentials = { username: 'user', password: 'pass' };

  it('returns a clear message for invalid credentials (401)', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Unauthorized', 401, 'Invalid username or password')
    );

    await expect(authService.login(credentials)).rejects.toThrow('Invalid username or password');
  });

  it('returns a clear message when MFA is required (401 with MFA in detail)', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Unauthorized', 401, 'MFA required for this account')
    );

    await expect(authService.login(credentials)).rejects.toThrow(/MFA required/i);
  });

  it('handles network errors gracefully', async () => {
    mockedApiClient.post.mockRejectedValueOnce(new Error('Network error'));

    await expect(authService.login(credentials)).rejects.toThrow(/network/i);
  });

  it('handles errors without detail field', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Unknown error', 400)
    );

    await expect(authService.login(credentials)).rejects.toThrow('Unknown error');
  });

  it('returns a clear message for account lockout (423)', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Locked', 423, 'Account locked due to too many failed attempts')
    );

    await expect(authService.login(credentials)).rejects.toThrow(
      'Account locked due to too many failed attempts'
    );
  });

  it('returns a clear message for rate limiting (429) with retry-after', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Too many requests', 429, 'Too many login attempts', 60)
    );

    await expect(authService.login(credentials)).rejects.toThrow(
      'Too many login attempts. Please wait 60 seconds and try again.'
    );
  });

  it('returns a generic rate limit message when Retry-After is missing (429)', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Too many requests', 429, 'Too many login attempts')
    );

    await expect(authService.login(credentials)).rejects.toThrow(
      'Too many login attempts. Please wait and try again.'
    );
  });

  it('returns a service-unavailable style message for server errors (5xx)', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('Internal server error', 500, 'Internal error')
    );

    await expect(authService.login(credentials)).rejects.toThrow(
      'Internal error'
    );
  });

  it('returns a fallback message for other server errors (503)', async () => {
    mockedApiClient.post.mockRejectedValueOnce(
      makeError('', 503)
    );

    await expect(authService.login(credentials)).rejects.toThrow(
      'Authentication service is temporarily unavailable. Please try again later.'
    );
  });
});
