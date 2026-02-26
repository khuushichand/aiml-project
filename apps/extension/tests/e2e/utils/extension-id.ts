import fs from 'node:fs'
import path from 'node:path'
import type { BrowserContext } from '@playwright/test'

type ResolveExtensionIdOptions = {
  userDataDir?: string
}

function resolveExtensionIdFromUserDataDir(userDataDir?: string): string | null {
  if (!userDataDir) {
    return null
  }

  const extensionsRoot = path.join(userDataDir, 'Default', 'Extensions')
  if (!fs.existsSync(extensionsRoot)) {
    return null
  }

  try {
    const candidates = fs
      .readdirSync(extensionsRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && /^[a-p]{32}$/.test(entry.name))
      .map((entry) => entry.name)

    return candidates[0] || null
  } catch {
    return null
  }
}

export async function resolveExtensionId(
  context: BrowserContext,
  options: ResolveExtensionIdOptions = {}
): Promise<string> {
  let targetUrl =
    context.backgroundPages()[0]?.url() ||
    context.serviceWorkers()[0]?.url() ||
    ''

  if (!targetUrl) {
    try {
      const page =
        context.backgroundPages()[0] ||
        context.pages()[0] ||
        (await context.newPage())
      const session = await context.newCDPSession(page)
      const { targetInfos } = await session.send('Target.getTargets')
      const extTarget =
        targetInfos.find(
          (t: any) =>
            typeof t.url === 'string' &&
            t.url.startsWith('chrome-extension://') &&
            (t.type === 'background_page' || t.type === 'service_worker')
        ) ||
        targetInfos.find(
          (t: any) =>
            typeof t.url === 'string' &&
            t.url.startsWith('chrome-extension://')
        )

      if (extTarget?.url) {
        targetUrl = extTarget.url
      }
    } catch {
      // Best-effort only; fall through to error below if we still
      // cannot determine the extension id.
    }
  }

  const match = targetUrl.match(/chrome-extension:\/\/([a-p]{32})/)
  if (match) {
    return match[1]
  }

  const extensionIdFromProfile = resolveExtensionIdFromUserDataDir(
    options.userDataDir
  )
  if (extensionIdFromProfile) {
    return extensionIdFromProfile
  }

  const activeTargets = context
    .backgroundPages()
    .concat(context.serviceWorkers())
    .map((target) => target.url())
    .filter(Boolean)

  const targetSummary = activeTargets.length
    ? activeTargets.join(', ')
    : '[no extension targets]'
  throw new Error(
    `Could not determine extension id from ${targetUrl || targetSummary}`
  )
}
