'use client';

/**
 * Returns true only when local-only admin tools are explicitly enabled.
 * This must stay off by default for production-safe deployments.
 */
export function isUnsafeLocalToolsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS === 'true';
}
