/**
 * Next.js instrumentation hook — runs once when the server starts.
 * @see https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */
export async function register() {
  // Validate environment variables at startup so misconfiguration fails fast
  // rather than silently at request time.
  if (process.env.NODE_ENV === 'production') {
    const { validateEnv } = await import('@/lib/env');
    validateEnv();
  }
}
