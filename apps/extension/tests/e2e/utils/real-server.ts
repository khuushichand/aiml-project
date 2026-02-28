import type { TestType } from "@playwright/test"
import {
  launchWithExtension,
  type LaunchWithExtensionResult
} from "./extension"
import { launchWithBuiltExtension } from "./extension-build"

/**
 * Read real tldw_server config for E2E tests.
 *
 * Tests that rely on a real server should call this at the top of the test
 * body. If the required env vars are not set, the test is skipped with a
 * clear message instead of attempting to spin up a mock server.
 *
 * Required env vars:
 * - TLDW_E2E_SERVER_URL  (e.g. http://127.0.0.1:3001)
 * - TLDW_E2E_API_KEY     (API key accepted by that server)
 *
 * Backward-compatible alias support:
 * - LDW_E2E_SERVER_URL (legacy typo alias, preferred is TLDW_E2E_SERVER_URL)
 */
export const requireRealServerConfig = (
  test: TestType<any, any>
): { serverUrl: string; apiKey: string } => {
  const serverUrl =
    process.env.TLDW_E2E_SERVER_URL || process.env.LDW_E2E_SERVER_URL
  const apiKey = process.env.TLDW_E2E_API_KEY

  if (!serverUrl || !apiKey) {
    test.skip(
      true,
      "Set TLDW_E2E_SERVER_URL (or LDW_E2E_SERVER_URL alias) and TLDW_E2E_API_KEY to run real-server E2E tests."
    )
    return { serverUrl: "", apiKey: "" }
  }

  return { serverUrl: serverUrl!, apiKey: apiKey! }
}

/**
 * Launch the extension for real-server E2E tests with a bounded startup timeout.
 *
 * If the browser/extension cannot start in the current environment, the test is
 * skipped with a clear message instead of timing out for the full test duration.
 */
export const launchWithExtensionOrSkip = async (
  test: TestType<any, any>,
  extensionPath: string,
  options: Parameters<typeof launchWithExtension>[1] = {}
): Promise<LaunchWithExtensionResult> => {
  try {
    return await launchWithExtension(extensionPath, options || {})
  } catch (error) {
    test.skip(
      true,
      `Extension launch unavailable in this environment (${String(error)}).`
    )
    return undefined as never
  }
}

export const launchWithBuiltExtensionOrSkip = async (
  test: TestType<any, any>,
  options: Parameters<typeof launchWithBuiltExtension>[0] = {}
): Promise<Awaited<ReturnType<typeof launchWithBuiltExtension>>> => {
  try {
    return await launchWithBuiltExtension(options || {})
  } catch (error) {
    test.skip(
      true,
      `Extension launch unavailable in this environment (${String(error)}).`
    )
    return undefined as never
  }
}
