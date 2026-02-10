export const SPLASH_TRIGGER_EVENT = "tldw:splash:show-after-login-success"

/**
 * Fire a one-shot splash trigger after an explicit successful login action.
 * No-op during SSR or non-browser execution contexts.
 */
export function emitSplashAfterLoginSuccess(): void {
  if (typeof window === "undefined") return
  window.dispatchEvent(new CustomEvent(SPLASH_TRIGGER_EVENT))
}

