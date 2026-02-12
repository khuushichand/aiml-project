import "../styles/globals.css"
// react-pdf text/annotation layer styles for Document Workspace
import "react-pdf/dist/esm/Page/AnnotationLayer.css"
import "react-pdf/dist/esm/Page/TextLayer.css"
import "@web/extension/shims/runtime-bootstrap"
// Use web-specific i18n that works with SSR/static generation
import "@web/lib/i18n-web"
import type { AppProps } from "next/app"
import dynamic from "next/dynamic"
import { useRouter } from "next/router"
import React from "react"
import { AppProviders } from "@web/components/AppProviders"

const OptionLayout = dynamic(
  () => import("@web/components/layout/WebLayout"),
  { ssr: false }
)

const hasEnvAuth = () => {
  const envApiKey = (process.env.NEXT_PUBLIC_X_API_KEY || "").trim()
  const envBearer = (process.env.NEXT_PUBLIC_API_BEARER || "").trim()
  return envApiKey.length > 0 || envBearer.length > 0
}

type ConfiguredAuthState = {
  hasConfig: boolean
  authMode?: "single-user" | "multi-user"
  isAuthenticated: boolean
}

const getConfiguredAuthState = async (): Promise<ConfiguredAuthState> => {
  try {
    const { tldwClient } = await import("@/services/tldw/TldwApiClient")
    const config = await tldwClient.getConfig()
    if (!config) {
      return {
        hasConfig: false,
        isAuthenticated: false
      }
    }

    if (config.authMode === "multi-user") {
      const hasAccessToken =
        typeof config.accessToken === "string" &&
        config.accessToken.trim().length > 0
      if (!hasAccessToken) {
        return {
          hasConfig: true,
          authMode: "multi-user",
          isAuthenticated: false
        }
      }

      try {
        const { tldwAuth } = await import("@/services/tldw/TldwAuth")
        await tldwAuth.getCurrentUser()
        return {
          hasConfig: true,
          authMode: "multi-user",
          isAuthenticated: true
        }
      } catch {
        return {
          hasConfig: true,
          authMode: "multi-user",
          isAuthenticated: false
        }
      }
    }

    return {
      hasConfig: true,
      authMode: "single-user",
      isAuthenticated:
        typeof config.apiKey === "string" && config.apiKey.trim().length > 0
    }
  } catch {
    return {
      hasConfig: false,
      isAuthenticated: false
    }
  }
}

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()
  const pathname = router.pathname || ""
  const routePath =
    pathname.length > 1 && pathname.endsWith("/")
      ? pathname.slice(0, -1)
      : pathname

  const isLoginRoute = routePath === "/login"
  const isSettingsRoute =
    routePath === "/settings" || routePath.startsWith("/settings/")
  const [isAuthenticated, setIsAuthenticated] = React.useState(false)
  const [authResolved, setAuthResolved] = React.useState(false)

  React.useEffect(() => {
    if (typeof window === "undefined") return

    let cancelled = false
    const refreshAuthState = async () => {
      const envAuthed = hasEnvAuth()
      const configuredAuth = await getConfiguredAuthState()
      const authed = configuredAuth.hasConfig
        ? configuredAuth.authMode === "multi-user"
          ? configuredAuth.isAuthenticated
          : configuredAuth.isAuthenticated || envAuthed
        : envAuthed

      if (!cancelled) {
        setIsAuthenticated(authed)
        setAuthResolved(true)
      }
    }

    void refreshAuthState()

    const onConfigUpdated = () => {
      void refreshAuthState()
    }
    const onStorage = (event: StorageEvent) => {
      if (!event.key || event.key === "tldwConfig") {
        void refreshAuthState()
      }
    }

    window.addEventListener("tldw:config-updated", onConfigUpdated)
    window.addEventListener("focus", onConfigUpdated)
    window.addEventListener("storage", onStorage)

    return () => {
      cancelled = true
      window.removeEventListener("tldw:config-updated", onConfigUpdated)
      window.removeEventListener("focus", onConfigUpdated)
      window.removeEventListener("storage", onStorage)
    }
  }, [router.asPath])

  const hideShellNav = !authResolved || !isAuthenticated

  return (
    <AppProviders>
      {isLoginRoute ? (
        <Component {...pageProps} />
      ) : (
        <OptionLayout
          hideHeader={hideShellNav}
          hideSidebar={hideShellNav || isSettingsRoute}
          allowNestedHideHeader={!isSettingsRoute}
        >
          <Component {...pageProps} />
        </OptionLayout>
      )}
    </AppProviders>
  )
}
