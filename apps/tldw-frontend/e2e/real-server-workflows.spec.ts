import { registerRealServerWorkflows, type CreateWorkflowDriver } from "../../test-utils/real-server-workflows"

const rawBaseUrl = process.env.TLDW_WEB_URL || "http://localhost:3000"
const baseUrl = rawBaseUrl.replace("127.0.0.1", "localhost").replace(/\/$/, "")

const normalizeRoute = (route: string) => {
  const trimmed = String(route || "").trim()
  if (!trimmed) return "/"
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`
}

const resolveRouteUrl = (route: string) => {
  if (/^https?:/i.test(route)) return route
  const normalized = normalizeRoute(route)
  const mapped = normalized === "/playground" ? "/" : normalized
  return `${baseUrl}${mapped}`
}

const createWebDriver: CreateWorkflowDriver = async ({
  serverUrl,
  apiKey,
  page,
  context,
  featureFlags
}) => {
  const payload = {
    serverUrl,
    apiKey,
    featureFlags: featureFlags || {}
  }

  const initScript = (cfg: typeof payload) => {
    let alreadySeeded = false
    try {
      alreadySeeded = localStorage.getItem("__e2eSeeded") === "true"
    } catch {
      alreadySeeded = false
    }
    if (!alreadySeeded) {
      try {
        localStorage.clear()
      } catch {
        // ignore localStorage errors
      }
    }
    try {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: cfg.serverUrl,
          apiKey: cfg.apiKey,
          authMode: "single-user"
        })
      )
    } catch {
      // ignore localStorage errors
    }
    try {
      localStorage.setItem("__tldw_first_run_complete", "true")
    } catch {
      // ignore localStorage errors
    }
    try {
      localStorage.setItem("__e2eSeeded", "true")
    } catch {
      // ignore localStorage errors
    }
    for (const [key, value] of Object.entries(cfg.featureFlags || {})) {
      try {
        localStorage.setItem(key, JSON.stringify(value))
      } catch {
        // ignore localStorage errors
      }
    }
  }

  await context.addInitScript(initScript, payload)
  await page.addInitScript(initScript, payload)

  await page.goto(resolveRouteUrl("/"), { waitUntil: "domcontentloaded" })

  const extraPages = new Set<typeof page>()

  return {
    kind: "web",
    serverUrl,
    apiKey,
    context,
    page,
    optionsUrl: baseUrl,
    sidepanelUrl: `${baseUrl}/chat`,
    openSidepanel: async () => {
      const chatPage = await context.newPage()
      extraPages.add(chatPage)
      await chatPage.goto(resolveRouteUrl("/chat"), {
        waitUntil: "domcontentloaded"
      })
      return chatPage
    },
    goto: async (targetPage, route, options) => {
      await targetPage.goto(resolveRouteUrl(route), options)
    },
    ensureHostPermission: async () => true,
    close: async () => {
      for (const p of extraPages) {
        if (!p.isClosed()) {
          await p.close()
        }
      }
    }
  }
}

registerRealServerWorkflows(createWebDriver)
