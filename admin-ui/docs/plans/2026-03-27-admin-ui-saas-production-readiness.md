# Admin-UI SaaS Production Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the admin-ui deployable as a SaaS admin panel in Docker with security headers, observability, and critical UX safety fixes.

**Architecture:** The admin-ui is a standalone Next.js 15 (App Router) application at `admin-ui/`. It communicates with the tldw backend exclusively through a server-side proxy at `admin-ui/app/api/proxy/[...path]/route.ts`. Auth uses httpOnly cookies (JWT or API key). The middleware at `admin-ui/middleware.ts` validates tokens with an in-memory LRU cache.

**Tech Stack:** Next.js 15.5.9, React 19, TypeScript 5.9, Radix UI, Tailwind CSS 4, Zod 4, Vitest 4, Playwright 1.57

---

## Task 1: Security Headers in next.config.js

**Files:**
- Modify: `admin-ui/next.config.js`
- Test: `admin-ui/lib/__tests__/security-headers.test.ts` (new)

**Step 1: Write the failing test**

Create `admin-ui/lib/__tests__/security-headers.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

// Import the config to verify headers are defined
const nextConfig = require('../../next.config.js');

describe('next.config.js security', () => {
  it('enables standalone output for Docker', () => {
    expect(nextConfig.output).toBe('standalone');
  });

  it('disables X-Powered-By header', () => {
    expect(nextConfig.poweredByHeader).toBe(false);
  });

  it('defines security headers for all routes', async () => {
    expect(typeof nextConfig.headers).toBe('function');
    const headers = await nextConfig.headers();
    expect(headers).toHaveLength(1);
    expect(headers[0].source).toBe('/:path*');

    const headerMap = Object.fromEntries(
      headers[0].headers.map((h: { key: string; value: string }) => [h.key, h.value])
    );

    expect(headerMap['X-Frame-Options']).toBe('DENY');
    expect(headerMap['X-Content-Type-Options']).toBe('nosniff');
    expect(headerMap['Referrer-Policy']).toBe('strict-origin-when-cross-origin');
    expect(headerMap['Content-Security-Policy']).toContain("frame-ancestors 'none'");
    expect(headerMap['Strict-Transport-Security']).toContain('max-age=');
    expect(headerMap['Permissions-Policy']).toContain('camera=()');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run lib/__tests__/security-headers.test.ts`
Expected: FAIL — `output` is undefined, `poweredByHeader` is undefined, `headers` is undefined

**Step 3: Write minimal implementation**

Replace `admin-ui/next.config.js` with:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  outputFileTracingRoot: `${__dirname}/..`,
  poweredByHeader: false,

  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self'",
              "connect-src 'self'",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join('; '),
          },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
          { key: 'X-DNS-Prefetch-Control', value: 'on' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run lib/__tests__/security-headers.test.ts`
Expected: PASS

**Step 5: Verify build still works**

Run: `cd admin-ui && npx next build`
Expected: Build completes. Output includes `.next/standalone/` directory.

**Step 6: Commit**

```bash
git add admin-ui/next.config.js admin-ui/lib/__tests__/security-headers.test.ts
git commit -m "feat(admin-ui): add standalone output and security headers to next.config.js"
```

---

## Task 2: Health Check Endpoint

**Files:**
- Create: `admin-ui/app/api/health/route.ts`
- Test: `admin-ui/app/api/health/__tests__/route.test.ts` (new)

**Step 1: Write the failing test**

Create `admin-ui/app/api/health/__tests__/route.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock next/server before importing route
vi.mock('next/server', () => ({
  NextResponse: {
    json: (body: unknown, init?: ResponseInit) => ({
      body,
      status: init?.status ?? 200,
      headers: new Map(Object.entries(init?.headers ?? {})),
    }),
  },
}));

describe('GET /api/health', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('returns ok status with timestamp', async () => {
    const { GET } = await import('../route');
    const response = await GET();
    expect(response.body).toMatchObject({
      status: 'ok',
    });
    expect(response.body).toHaveProperty('timestamp');
    expect(response.body).toHaveProperty('version');
  });

  it('returns Cache-Control no-store header', async () => {
    const { GET } = await import('../route');
    const response = await GET();
    expect(response.headers.get('Cache-Control')).toBe('no-store');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run app/api/health/__tests__/route.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

Create `admin-ui/app/api/health/route.ts`:

```typescript
import { NextResponse } from 'next/server';

// Read version once at module load time.
let appVersion = '0.0.0';
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  appVersion = require('../../../package.json').version;
} catch {
  // Standalone builds may not bundle package.json — fall back gracefully.
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
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run app/api/health/__tests__/route.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/api/health/route.ts admin-ui/app/api/health/__tests__/route.test.ts
git commit -m "feat(admin-ui): add /api/health endpoint for container health checks"
```

---

## Task 3: Environment Validation

**Files:**
- Create: `admin-ui/lib/env.ts`
- Test: `admin-ui/lib/__tests__/env.test.ts` (new)

**Step 1: Write the failing test**

Create `admin-ui/lib/__tests__/env.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('env validation', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('succeeds when NEXT_PUBLIC_API_URL is set', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
    const { validateEnv } = await import('../env');
    expect(() => validateEnv()).not.toThrow();
  });

  it('throws when NEXT_PUBLIC_API_URL is missing', async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    const { validateEnv } = await import('../env');
    expect(() => validateEnv()).toThrow(/NEXT_PUBLIC_API_URL/);
  });

  it('throws when NEXT_PUBLIC_API_URL is not a valid URL', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'not-a-url';
    const { validateEnv } = await import('../env');
    expect(() => validateEnv()).toThrow();
  });

  it('defaults NEXT_PUBLIC_API_VERSION to v1', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
    delete process.env.NEXT_PUBLIC_API_VERSION;
    const { validateEnv } = await import('../env');
    const env = validateEnv();
    expect(env.NEXT_PUBLIC_API_VERSION).toBe('v1');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run lib/__tests__/env.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

Create `admin-ui/lib/env.ts`:

```typescript
import { z } from 'zod';

const envSchema = z.object({
  NEXT_PUBLIC_API_URL: z
    .string({ required_error: 'NEXT_PUBLIC_API_URL is required' })
    .url('NEXT_PUBLIC_API_URL must be a valid URL'),
  NEXT_PUBLIC_API_VERSION: z.string().default('v1'),
  NEXT_PUBLIC_DEFAULT_AUTH_MODE: z
    .enum(['password', 'apikey'])
    .default('password'),
  NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN: z
    .string()
    .transform((v) => v === 'true')
    .default('false'),
  NEXT_PUBLIC_BILLING_ENABLED: z
    .string()
    .transform((v) => v === 'true')
    .default('false'),
});

export type AppEnv = z.infer<typeof envSchema>;

let cachedEnv: AppEnv | null = null;

export function validateEnv(): AppEnv {
  if (cachedEnv) return cachedEnv;

  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    const errors = result.error.issues
      .map((i) => `  ${i.path.join('.')}: ${i.message}`)
      .join('\n');
    throw new Error(`Environment validation failed:\n${errors}`);
  }

  cachedEnv = result.data;
  return cachedEnv;
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run lib/__tests__/env.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/lib/env.ts admin-ui/lib/__tests__/env.test.ts
git commit -m "feat(admin-ui): add Zod-based environment validation"
```

---

## Task 4: Auth Cache Invalidation on Logout

**Files:**
- Modify: `admin-ui/middleware.ts` (export `invalidateAuthCache`)
- Modify: `admin-ui/app/api/auth/logout/route.ts` (call invalidation)
- Test: `admin-ui/lib/__tests__/auth-cache-invalidation.test.ts` (new)

**Step 1: Write the failing test**

Create `admin-ui/lib/__tests__/auth-cache-invalidation.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

describe('auth cache invalidation', () => {
  it('exports invalidateAuthCache function from middleware', async () => {
    // The middleware module should export invalidateAuthCache
    const mod = await import('../../middleware');
    expect(typeof mod.invalidateAuthCache).toBe('function');
  });

  it('invalidateAuthCache accepts a token string without throwing', async () => {
    const { invalidateAuthCache } = await import('../../middleware');
    // Should not throw even with an unknown token
    await expect(invalidateAuthCache('some-token')).resolves.not.toThrow();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run lib/__tests__/auth-cache-invalidation.test.ts`
Expected: FAIL — `invalidateAuthCache` is not exported

**Step 3: Add the export to middleware.ts**

In `admin-ui/middleware.ts`, add the following function after the `setCachedAuth` function (after line 88) and before `safeDecodeCookieValue`:

```typescript
/**
 * Invalidate all auth cache entries for a given raw token.
 * Called by the logout route to prevent revoked tokens from being accepted
 * for the remainder of the cache TTL (up to 30 seconds).
 */
export const invalidateAuthCache = async (rawToken: string): Promise<void> => {
  const normalized = rawToken.replace(/^Bearer\s+/i, '').trim();
  if (!normalized || normalized.length > MAX_TOKEN_LENGTH) return;

  for (const kind of ['jwt', 'apiKey'] as AuthTokenKind[]) {
    const cacheKey = await buildAuthCacheKey(kind, normalized);
    if (cacheKey) {
      authCache.delete(cacheKey);
    }
  }
};
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run lib/__tests__/auth-cache-invalidation.test.ts`
Expected: PASS

**Step 5: Wire into logout route**

Modify `admin-ui/app/api/auth/logout/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrlForRequest } from '@/lib/api-config';
import {
  clearAdminSessionCookies,
  getBackendAuthHeaders,
  ACCESS_TOKEN_COOKIE,
  API_KEY_COOKIE,
  LEGACY_API_KEY_COOKIE,
} from '@/lib/server-auth';
import { invalidateAuthCache } from '@/middleware';

export async function POST(request: NextRequest): Promise<NextResponse> {
  const headers = getBackendAuthHeaders(request);

  // Invalidate cached auth entries for the tokens being cleared.
  for (const name of [ACCESS_TOKEN_COOKIE, API_KEY_COOKIE, LEGACY_API_KEY_COOKIE]) {
    const value = request.cookies.get(name)?.value;
    if (value) {
      await invalidateAuthCache(value);
    }
  }

  try {
    await fetch(buildApiUrlForRequest(request, '/auth/logout'), {
      method: 'POST',
      headers,
      cache: 'no-store',
    });
  } catch (error) {
    console.warn('Admin UI backend logout failed', {
      error: error instanceof Error ? error.message : String(error),
    });
  }

  const response = NextResponse.json({ ok: true });
  clearAdminSessionCookies(response);
  return response;
}
```

**Step 6: Run all tests**

Run: `cd admin-ui && npx vitest run`
Expected: All tests pass

**Step 7: Commit**

```bash
git add admin-ui/middleware.ts admin-ui/app/api/auth/logout/route.ts admin-ui/lib/__tests__/auth-cache-invalidation.test.ts
git commit -m "fix(admin-ui): invalidate auth cache on logout to prevent revoked token reuse"
```

---

## Task 5: Auth Endpoint Rate Limiting

**Files:**
- Create: `admin-ui/lib/rate-limiter.ts`
- Test: `admin-ui/lib/__tests__/rate-limiter.test.ts` (new)
- Modify: `admin-ui/app/api/auth/login/route.ts`

**Step 1: Write the failing test**

Create `admin-ui/lib/__tests__/rate-limiter.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('rate limiter', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('allows requests under the limit', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      expect(checkRateLimit('127.0.0.1').allowed).toBe(true);
    }
  });

  it('blocks requests over the limit', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      checkRateLimit('127.0.0.1');
    }
    const result = checkRateLimit('127.0.0.1');
    expect(result.allowed).toBe(false);
    expect(result.retryAfterSeconds).toBeGreaterThan(0);
  });

  it('resets after the window expires', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      checkRateLimit('127.0.0.1');
    }
    expect(checkRateLimit('127.0.0.1').allowed).toBe(false);

    // Advance past the 60-second window
    vi.advanceTimersByTime(61_000);

    expect(checkRateLimit('127.0.0.1').allowed).toBe(true);
  });

  it('tracks different IPs independently', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      checkRateLimit('1.1.1.1');
    }
    expect(checkRateLimit('1.1.1.1').allowed).toBe(false);
    expect(checkRateLimit('2.2.2.2').allowed).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run lib/__tests__/rate-limiter.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

Create `admin-ui/lib/rate-limiter.ts`:

```typescript
const MAX_REQUESTS = 10;
const WINDOW_MS = 60_000;
const MAX_ENTRIES = 10_000;

const store = new Map<string, number[]>();

function pruneEntry(timestamps: number[], now: number): number[] {
  const cutoff = now - WINDOW_MS;
  return timestamps.filter((t) => t > cutoff);
}

function pruneStore(): void {
  if (store.size <= MAX_ENTRIES) return;
  const now = Date.now();
  for (const [key, timestamps] of store) {
    const active = pruneEntry(timestamps, now);
    if (active.length === 0) {
      store.delete(key);
    } else {
      store.set(key, active);
    }
  }
}

export function checkRateLimit(ip: string): {
  allowed: boolean;
  retryAfterSeconds?: number;
} {
  const now = Date.now();
  pruneStore();

  const timestamps = pruneEntry(store.get(ip) ?? [], now);

  if (timestamps.length >= MAX_REQUESTS) {
    const oldestInWindow = timestamps[0];
    const retryAfterMs = oldestInWindow + WINDOW_MS - now;
    return {
      allowed: false,
      retryAfterSeconds: Math.ceil(Math.max(retryAfterMs, 1000) / 1000),
    };
  }

  timestamps.push(now);
  store.set(ip, timestamps);
  return { allowed: true };
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run lib/__tests__/rate-limiter.test.ts`
Expected: PASS

**Step 5: Wire into login route**

Read `admin-ui/app/api/auth/login/route.ts` first, then add rate limiting at the top of the POST handler. Add these lines near the top of the handler function:

```typescript
import { checkRateLimit } from '@/lib/rate-limiter';

// At the start of the POST handler, before any other logic:
const ip = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
  ?? request.headers.get('x-real-ip')
  ?? 'unknown';

const rateCheck = checkRateLimit(ip);
if (!rateCheck.allowed) {
  return NextResponse.json(
    { detail: 'Too many login attempts. Please try again later.' },
    {
      status: 429,
      headers: { 'Retry-After': String(rateCheck.retryAfterSeconds) },
    }
  );
}
```

Apply the same pattern to `admin-ui/app/api/auth/mfa/login/route.ts` and `admin-ui/app/api/auth/apikey/route.ts` if they exist.

**Step 6: Run all tests**

Run: `cd admin-ui && npx vitest run`
Expected: All tests pass

**Step 7: Commit**

```bash
git add admin-ui/lib/rate-limiter.ts admin-ui/lib/__tests__/rate-limiter.test.ts admin-ui/app/api/auth/login/route.ts
git commit -m "feat(admin-ui): add sliding-window rate limiting on auth endpoints"
```

---

## Task 6: Dockerfile for Admin-UI

**Files:**
- Create: `Dockerfiles/Dockerfile.admin-ui`

**Step 1: Write the Dockerfile**

Create `Dockerfiles/Dockerfile.admin-ui`:

```dockerfile
# Production Dockerfile for tldw Admin UI
# - Builds the Admin UI as a standalone Next.js app
# - Ships a minimal runtime image

FROM oven/bun:1.3.2-debian AS builder

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Copy only what's needed for install + build
COPY admin-ui/package.json admin-ui/bun.lock ./
RUN bun install --frozen-lockfile

COPY admin-ui/ ./

# Build-time configuration baked into client bundle
ARG NEXT_PUBLIC_API_URL=
ARG NEXT_PUBLIC_API_VERSION=v1
ARG NEXT_PUBLIC_DEFAULT_AUTH_MODE=password
ARG NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN=false
ARG NEXT_PUBLIC_BILLING_ENABLED=false

ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_API_VERSION=${NEXT_PUBLIC_API_VERSION}
ENV NEXT_PUBLIC_DEFAULT_AUTH_MODE=${NEXT_PUBLIC_DEFAULT_AUTH_MODE}
ENV NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN=${NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN}
ENV NEXT_PUBLIC_BILLING_ENABLED=${NEXT_PUBLIC_BILLING_ENABLED}

RUN bun run build


FROM node:20-bookworm-slim AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3001

WORKDIR /app

RUN useradd -m -u 10003 adminui

# Standalone output: server.js + traced runtime deps
COPY --from=builder --chown=adminui:adminui /app/.next/standalone /app
COPY --from=builder --chown=adminui:adminui /app/.next/static /app/.next/static
COPY --from=builder --chown=adminui:adminui /app/public /app/public

USER adminui

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD node -e "fetch('http://localhost:3001/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
```

**Step 2: Verify build**

Run: `docker build -f Dockerfiles/Dockerfile.admin-ui -t tldw-admin:test --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 .`
Expected: Build succeeds. Image runs and serves on port 3001.

**Step 3: Test health check**

Run:
```bash
docker run -d --name admin-test -p 3001:3001 -e NEXT_PUBLIC_API_URL=http://localhost:8000 tldw-admin:test
sleep 3
curl -s http://localhost:3001/api/health | python3 -m json.tool
docker rm -f admin-test
```
Expected: `{ "status": "ok", "timestamp": "...", "version": "0.1.0" }`

**Step 4: Commit**

```bash
git add Dockerfiles/Dockerfile.admin-ui
git commit -m "feat(admin-ui): add production Dockerfile for Docker deployment"
```

---

## Task 7: Docker Compose Overlay

**Files:**
- Create: `Dockerfiles/docker-compose.admin-ui.yml`

**Step 1: Write the compose file**

Create `Dockerfiles/docker-compose.admin-ui.yml`:

```yaml
# Overlay for admin-ui — use alongside the main docker-compose.yml:
#   docker compose -f docker-compose.yml -f Dockerfiles/docker-compose.admin-ui.yml up

services:
  admin-ui:
    build:
      context: ..
      dockerfile: Dockerfiles/Dockerfile.admin-ui
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://app:8000}
        NEXT_PUBLIC_API_VERSION: ${NEXT_PUBLIC_API_VERSION:-v1}
        NEXT_PUBLIC_DEFAULT_AUTH_MODE: ${NEXT_PUBLIC_DEFAULT_AUTH_MODE:-password}
        NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN: ${NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN:-false}
        NEXT_PUBLIC_BILLING_ENABLED: ${NEXT_PUBLIC_BILLING_ENABLED:-false}
    ports:
      - "${ADMIN_UI_PORT:-3001}:3001"
    environment:
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-}
      - JWT_ALGORITHM=${JWT_ALGORITHM:-HS256}
      - JWT_SECONDARY_SECRET=${JWT_SECONDARY_SECRET:-}
      - AUTH_MODE=${AUTH_MODE:-multi_user}
    depends_on:
      app:
        condition: service_healthy
    restart: unless-stopped
```

**Step 2: Commit**

```bash
git add Dockerfiles/docker-compose.admin-ui.yml
git commit -m "feat(admin-ui): add docker-compose overlay for admin-ui service"
```

---

## Task 8: Request Correlation IDs

**Files:**
- Modify: `admin-ui/middleware.ts` (add X-Request-ID header to responses)
- Modify: `admin-ui/lib/server-auth.ts` (forward X-Request-ID in proxy)
- Test: `admin-ui/lib/__tests__/correlation-id.test.ts` (new)

**Step 1: Write the failing test**

Create `admin-ui/lib/__tests__/correlation-id.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('correlation ID generation', () => {
  it('generateRequestId returns a valid UUID v4', async () => {
    const { generateRequestId } = await import('../correlation-id');
    const id = generateRequestId();
    expect(id).toMatch(UUID_REGEX);
  });

  it('generates unique IDs', async () => {
    const { generateRequestId } = await import('../correlation-id');
    const ids = new Set(Array.from({ length: 100 }, () => generateRequestId()));
    expect(ids.size).toBe(100);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run lib/__tests__/correlation-id.test.ts`
Expected: FAIL — module not found

**Step 3: Write the correlation ID utility**

Create `admin-ui/lib/correlation-id.ts`:

```typescript
export function generateRequestId(): string {
  return crypto.randomUUID();
}
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run lib/__tests__/correlation-id.test.ts`
Expected: PASS

**Step 5: Wire into middleware**

In `admin-ui/middleware.ts`, modify the `middleware` function (around line 314) to add the correlation ID header:

```typescript
import { generateRequestId } from '@/lib/correlation-id';

export async function middleware(request: NextRequest) {
  const requestId = request.headers.get('x-request-id') || generateRequestId();

  if (await hasAuthSession(request)) {
    const response = NextResponse.next();
    response.headers.set('x-request-id', requestId);
    return response;
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = '/login';
  loginUrl.searchParams.set(
    'redirectTo',
    `${request.nextUrl.pathname}${request.nextUrl.search}`
  );
  const response = NextResponse.redirect(loginUrl);
  response.headers.set('x-request-id', requestId);
  return response;
}
```

**Step 6: Forward in proxy**

In `admin-ui/lib/server-auth.ts`, add `'x-request-id'` to the `passthroughHeaders` array in `appendProxyHeaders` (line 131):

```typescript
export const appendProxyHeaders = (request: NextRequest, headers: Headers): void => {
  const passthroughHeaders = [
    'accept',
    'content-type',
    'if-none-match',
    'if-modified-since',
    'range',
    'x-request-id',
  ];

  for (const name of passthroughHeaders) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }
};
```

**Step 7: Run all tests**

Run: `cd admin-ui && npx vitest run`
Expected: All tests pass

**Step 8: Commit**

```bash
git add admin-ui/lib/correlation-id.ts admin-ui/lib/__tests__/correlation-id.test.ts admin-ui/middleware.ts admin-ui/lib/server-auth.ts
git commit -m "feat(admin-ui): add X-Request-ID correlation headers for end-to-end tracing"
```

---

## Task 9: Structured Logging

**Files:**
- Create: `admin-ui/lib/logger.ts`
- Test: `admin-ui/lib/__tests__/logger.test.ts` (new)

**Step 1: Write the failing test**

Create `admin-ui/lib/__tests__/logger.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('logger', () => {
  const originalEnv = process.env.NODE_ENV;

  afterEach(() => {
    Object.defineProperty(process.env, 'NODE_ENV', { value: originalEnv, writable: true });
    vi.restoreAllMocks();
  });

  it('exports info, warn, error, debug methods', async () => {
    vi.resetModules();
    const { logger } = await import('../logger');
    expect(typeof logger.info).toBe('function');
    expect(typeof logger.warn).toBe('function');
    expect(typeof logger.error).toBe('function');
    expect(typeof logger.debug).toBe('function');
  });

  it('outputs JSON in production', async () => {
    vi.resetModules();
    Object.defineProperty(process.env, 'NODE_ENV', { value: 'production', writable: true });
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    const { logger } = await import('../logger');

    logger.info('test message', { component: 'test' });

    expect(consoleSpy).toHaveBeenCalledTimes(1);
    const output = consoleSpy.mock.calls[0][0];
    const parsed = JSON.parse(output);
    expect(parsed).toMatchObject({
      level: 'info',
      message: 'test message',
      component: 'test',
    });
    expect(parsed).toHaveProperty('timestamp');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd admin-ui && npx vitest run lib/__tests__/logger.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

Create `admin-ui/lib/logger.ts`:

```typescript
type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  component?: string;
  requestId?: string;
  [key: string]: unknown;
}

const isProduction = process.env.NODE_ENV === 'production';

function formatLog(level: LogLevel, message: string, context?: LogContext): string {
  if (isProduction) {
    return JSON.stringify({
      timestamp: new Date().toISOString(),
      level,
      message,
      ...context,
    });
  }
  const prefix = `[${level.toUpperCase()}]`;
  const ctx = context ? ` ${JSON.stringify(context)}` : '';
  return `${prefix} ${message}${ctx}`;
}

function log(level: LogLevel, message: string, context?: LogContext): void {
  const formatted = formatLog(level, message, context);
  switch (level) {
    case 'error':
      console.error(formatted);
      break;
    case 'warn':
      console.warn(formatted);
      break;
    case 'debug':
      if (!isProduction) console.debug(formatted);
      break;
    default:
      console.log(formatted);
  }
}

export const logger = {
  debug: (message: string, context?: LogContext) => log('debug', message, context),
  info: (message: string, context?: LogContext) => log('info', message, context),
  warn: (message: string, context?: LogContext) => log('warn', message, context),
  error: (message: string, context?: LogContext) => log('error', message, context),
};
```

**Step 4: Run test to verify it passes**

Run: `cd admin-ui && npx vitest run lib/__tests__/logger.test.ts`
Expected: PASS

**Step 5: Replace console.warn in logout route as an example**

In `admin-ui/app/api/auth/logout/route.ts`, replace:
```typescript
console.warn('Admin UI backend logout failed', { ... });
```
with:
```typescript
import { logger } from '@/lib/logger';
// ...
logger.warn('Backend logout failed', {
  component: 'auth/logout',
  error: error instanceof Error ? error.message : String(error),
});
```

> **Note:** The remaining ~93 console.* replacements should be done in a follow-up sweep (one file at a time, grepping for `console.log|console.warn|console.error`). Each file replacement can be a sub-commit.

**Step 6: Run all tests**

Run: `cd admin-ui && npx vitest run`
Expected: All tests pass

**Step 7: Commit**

```bash
git add admin-ui/lib/logger.ts admin-ui/lib/__tests__/logger.test.ts admin-ui/app/api/auth/logout/route.ts
git commit -m "feat(admin-ui): add structured JSON logger for production observability"
```

---

## Task 10: Replace Remaining console.* Calls with Logger

**Files:**
- Modify: ~30 files across `admin-ui/app/` and `admin-ui/lib/`

**Step 1: Find all console.* calls**

Run: `cd admin-ui && grep -rn 'console\.\(log\|warn\|error\|debug\)' app/ lib/ --include='*.ts' --include='*.tsx' | grep -v '__tests__' | grep -v 'node_modules'`

This will produce the list of files to update.

**Step 2: Replace each file**

For each file, import the logger and replace:
- `console.error('message', ...)` → `logger.error('message', { component: '<route-name>', ... })`
- `console.warn('message', ...)` → `logger.warn('message', { component: '<route-name>', ... })`
- `console.log('message', ...)` → `logger.info('message', { component: '<route-name>', ... })`

**Step 3: Run all tests after each batch**

Run: `cd admin-ui && npx vitest run`
Expected: All tests pass

**Step 4: Commit in batches**

```bash
git add -u admin-ui/
git commit -m "refactor(admin-ui): replace console.* with structured logger across all routes"
```

---

## Phase 2 Tasks (Weeks 3-4) — Summary

These tasks follow the same TDD pattern. Key implementation details:

### Task 11: Plan Deletion Subscriber Check (REVIEW.md 7.1)

**File:** `admin-ui/app/plans/page.tsx`
- Before `handleDelete`, call existing `api.getSubscriptions({ plan_id })` from `lib/api-client.ts`
- If result has items, show warning dialog instead of confirm
- Test: Mock API response with active subscriptions, verify delete is blocked

### Task 12: PrivilegedActionDialog Rollout (REVIEW.md 9.6)

**Files:** 5 page files (plans, organizations, byok, subscriptions, resource-governor)
- Replace `useConfirm()` calls for destructive ops with `usePrivilegedActionDialog()`
- Provider already exists in `app/providers.tsx` line 21
- Test: Render page, trigger delete, verify password dialog appears

### Task 13: Dashboard Auto-Refresh (REVIEW.md 1.13)

**File:** `admin-ui/app/page.tsx`
- Add a `useEffect` with `setInterval(loadDashboardData, 60_000)`
- Add "Last updated X ago" text using `date-fns/formatDistanceToNow`
- Add pause/resume toggle
- Test: Verify interval fires, verify "Last updated" text updates

### Task 14: Quick Wins Batch (REVIEW.md 3.2, 3.3, 5.14, 9.5, 9.8)

5 independent sub-tasks, each with their own commit:
- **3.2:** Make API key hygiene cards clickable → add `onClick` to filter table
- **3.3:** Hide N/A columns → conditionally render based on data availability
- **5.14:** Add `aria-label` to icon-only alert buttons
- **9.5:** Replace bare "Loading..." with skeleton components
- **9.8:** Add `ExportMenu` to remaining list pages (grep for pages missing it)

---

## Phase 3 Tasks (Weeks 5-6) — Summary

### Task 15: ACP Agent Runtime Metrics (REVIEW.md 4.4)
- Requires backend endpoint: `GET /api/v1/admin/acp/agents/usage`
- Frontend: Add columns to agent table (requests, tokens, cost, error rate)

### Task 16: ACP Session Auto-Refresh + Cost (REVIEW.md 4.7, 4.8)
- Add 15-second `setInterval` in `app/acp-sessions/page.tsx`
- Add cost estimation column based on model pricing lookup

### Task 17: Monitoring Auto-Refresh (REVIEW.md 5.1)
- Same pattern as Task 13 dashboard auto-refresh
- Apply to `app/monitoring/page.tsx`

### Task 18: Bundle Size Monitoring
- `bun add -D @next/bundle-analyzer`
- Add `analyze` script to package.json: `ANALYZE=true next build`
- Document bundle size baselines

---

## Phase 4 Tasks (Weeks 7-8) — Summary

### Task 19: Budget Forecasting (REVIEW.md 6.3)
- Add sparkline/progress bar to budget table
- Compute projected exhaustion from recent burn rate

### Task 20: Tenant Context Visibility
- Modify `components/OrgContextSwitcher.tsx`
- Show read-only badge for non-super-admins

### Task 21: Subscription At-Risk Identification (REVIEW.md 7.4)
- Add "Needs Attention" section to subscriptions page
- Filter for `past_due` and high-usage subscriptions

---

## Verification Checklist

After completing all phases, verify:

- [ ] `docker build -f Dockerfiles/Dockerfile.admin-ui -t tldw-admin:prod .` succeeds
- [ ] `curl -I http://localhost:3001/` shows all 7 security headers
- [ ] `curl http://localhost:3001/api/health` returns 200 with JSON body
- [ ] Removing `NEXT_PUBLIC_API_URL` produces a clear startup error
- [ ] Logging out immediately invalidates cached auth (no 30s window)
- [ ] 11th rapid login attempt returns HTTP 429
- [ ] Response headers include `X-Request-ID`
- [ ] `docker logs` output is valid JSON (one object per line)
- [ ] `cd admin-ui && npx vitest run` — all tests pass
- [ ] `cd admin-ui && npx next build` — build succeeds with no errors
