import { emitSplashAfterLoginSuccess } from "@/services/splash-events"

/**
 * Single-user auth doesn't use the multi-user login endpoint, so trigger
 * the same splash event after explicit single-user auth+connection success.
 */
export function emitSplashAfterSingleUserAuthSuccess(
  authMode: string | undefined,
  isConnected: boolean
): void {
  if (authMode === "single-user" && isConnected) {
    emitSplashAfterLoginSuccess()
  }
}

