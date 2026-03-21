import React from "react"
import type { ErrorInfo, ReactNode } from "react"
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate
} from "react-router-dom"
import { useDarkMode } from "~/hooks/useDarkmode"
import { PageAssistLoader } from "@/components/Common/PageAssistLoader"
import { useAutoButtonTitles } from "@/hooks/useAutoButtonTitles"
import { ensureI18nNamespaces } from "@/i18n"
import { registerUiDiagnostics } from "@/utils/ui-diagnostics"
import { useLayoutUiStore } from "@/store/layout-ui"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import {
  platformConfig,
  type PlatformTarget
} from "@/config/platform"
import {
  optionRoutes,
  sidepanelRoutes,
  type RouteDefinition,
  type RouteKind
} from "@/routes/route-registry"
import { isRouteEnabledForCapabilities } from "@/routes/route-capabilities"
import {
  COMPANION_CAPTURE_MESSAGE_TYPE,
  normalizePendingCompanionCapture,
  writePendingCompanionCapture
} from "@/services/companion-capture"
import { HEADER_SHORTCUTS_EXPANDED_SETTING } from "@/services/settings/ui-settings"
import { setSetting } from "@/services/settings/registry"
import OptionLayout from "~/components/Layouts/Layout"

const getRoutesForTarget = (
  routes: RouteDefinition[],
  target: PlatformTarget
) => routes.filter((route) => !route.targets || route.targets.includes(target))

const ROUTE_FALLBACKS: Record<
  RouteKind,
  { label: string; description: string }
> = {
  options: {
    label: "Loading tldw Assistant...",
    description: "Setting up your workspace"
  },
  sidepanel: {
    label: "Loading chat...",
    description: "Preparing your assistant"
  }
}

const RouteNotFoundState = ({
  routeLabel,
  kind
}: {
  routeLabel: string
  kind: RouteKind
}) => {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-[70vh] w-full items-center justify-center px-6 py-12">
      <div
        className="w-full max-w-xl rounded-lg border border-border bg-surface p-6 shadow-sm"
        data-testid="not-found-recovery-panel"
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">404</p>
        <h1 className="mt-2 text-2xl font-semibold text-text">
          We could not find that route
        </h1>
        <p className="mt-3 text-sm text-text-muted">
          The link may be out of date, moved, or typed incorrectly. Choose a route below to
          continue.
        </p>
        <p className="mt-2 text-xs text-text-muted">
          Route not found: <code className="rounded bg-surface2 px-1 py-0.5">{routeLabel}</code>
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <Link
            to="/"
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primaryStrong"
            data-testid="not-found-go-home"
          >
            Go to Home
          </Link>
          {kind === "options" && (
            <Link
              to="/research"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              data-testid="not-found-open-research"
            >
              Open Research
            </Link>
          )}
          {kind === "options" && (
            <Link
              to="/media"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              data-testid="not-found-open-media"
            >
              Open Media
            </Link>
          )}
          <Link
            to="/settings"
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
            data-testid="not-found-open-settings"
          >
            Open Settings
          </Link>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-surface2"
            data-testid="not-found-go-back"
          >
            Go back
          </button>
        </div>
      </div>
    </div>
  )
}

type RouteErrorBoundaryProps = {
  children: ReactNode
  onReset?: () => void
}

type RouteErrorBoundaryState = {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

class OptionsErrorBoundary extends React.Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null
  }

  static getDerivedStateFromError(error: Error): Partial<RouteErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo })
    console.error("[OptionsErrorBoundary] Caught error:", error, errorInfo)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    this.props.onReset?.()
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className="flex min-h-screen items-center justify-center bg-surface p-8"
          data-testid="error-boundary"
        >
          <div className="max-w-lg text-center">
            <h2 className="text-lg font-semibold text-text">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              The Options page hit an unexpected error. You can try reloading the page.
            </p>
            <button
              type="button"
              onClick={this.handleReset}
              className="mt-4 inline-flex items-center justify-center rounded-md bg-[color:var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[color:var(--color-primary-strong)]"
            >
              Reload Options
            </button>
            {this.state.error && (
              <details className="mt-4 text-left text-xs text-text-subtle">
                <summary className="cursor-pointer">View error details</summary>
                <pre className="mt-2 whitespace-pre-wrap rounded-md bg-surface2 p-3 text-[11px] text-danger">
                  {this.state.error.message}
                  {this.state.errorInfo?.componentStack
                    ? `\n${this.state.errorInfo.componentStack}`
                    : ""}
                </pre>
              </details>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

class SidepanelErrorBoundary extends React.Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null
  }

  static getDerivedStateFromError(error: Error): Partial<RouteErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo })
    console.error("[SidepanelErrorBoundary] Caught error:", error, errorInfo)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    this.props.onReset?.()
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className="flex min-h-screen items-center justify-center bg-surface p-8"
          data-testid="error-boundary"
        >
          <div className="max-w-lg text-center">
            <h2 className="text-lg font-semibold text-text">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              The sidepanel hit an unexpected error. You can try reloading the panel.
            </p>
            <button
              type="button"
              onClick={this.handleReset}
              className="mt-4 inline-flex items-center justify-center rounded-md bg-[color:var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[color:var(--color-primary-strong)]"
            >
              Reload Sidepanel
            </button>
            {this.state.error && (
              <details className="mt-4 text-left text-xs text-text-subtle">
                <summary className="cursor-pointer">View error details</summary>
                <pre className="mt-2 whitespace-pre-wrap rounded-md bg-surface2 p-3 text-[11px] text-danger">
                  {this.state.error.message}
                  {this.state.errorInfo?.componentStack
                    ? `\n${this.state.errorInfo.componentStack}`
                    : ""}
                </pre>
              </details>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export const RouteShell = ({ kind }: { kind: RouteKind }) => {
  const { mode } = useDarkMode()
  const navigate = useNavigate()
  const { capabilities, loading: capabilitiesLoading } = useServerCapabilities()
  useAutoButtonTitles()
  const location = useLocation()
  const setChatSidebarCollapsed = useLayoutUiStore(
    (state) => state.setChatSidebarCollapsed
  )
  React.useEffect(() => {
    if (typeof window === "undefined") return
    const targetWindow = window as Window & {
      __tldwNavigate?: (path: string) => void
    }
    const navigateFn = (path: string) => {
      navigate(path)
    }
    targetWindow.__tldwNavigate = navigateFn
    return () => {
      if (targetWindow.__tldwNavigate === navigateFn) {
        delete targetWindow.__tldwNavigate
      }
    }
  }, [navigate])
  React.useEffect(() => {
    if (kind !== "sidepanel") return
    const runtime =
      (globalThis as any)?.browser?.runtime ||
      (globalThis as any)?.chrome?.runtime
    const onMessage = runtime?.onMessage
    if (!onMessage || typeof onMessage.addListener !== "function") {
      return
    }

    const listener = (message: {
      from?: string
      type?: string
      text?: string
      payload?: unknown
    }) => {
      if (message?.from !== "background") return
      if (message?.type !== COMPANION_CAPTURE_MESSAGE_TYPE) return
      const payload =
        normalizePendingCompanionCapture({
          ...(typeof message?.payload === "object" && message.payload !== null
            ? (message.payload as Record<string, unknown>)
            : {}),
          selectionText:
            (message?.text || "").trim() ||
            String(
              (message?.payload as { selectionText?: string } | undefined)
                ?.selectionText || ""
            ).trim()
        }) || null
      if (!payload) return
      writePendingCompanionCapture(payload)
      navigate("/companion")
    }

    onMessage.addListener(listener)
    return () => {
      if (typeof onMessage.removeListener === "function") {
        onMessage.removeListener(listener)
      }
    }
  }, [kind, navigate])
  React.useEffect(() => {
    registerUiDiagnostics(kind === "options" ? "options" : "sidepanel")
  }, [kind])
  React.useEffect(() => {
    if (kind === "options") {
      void ensureI18nNamespaces([
        "option",
        "settings",
        "dataTables",
        "evaluations",
        "audiobook"
      ])
      const path = location.pathname
      const needsReview =
        path === "/review" ||
        path === "/media" ||
        path === "/media-multi"
      const needsCompanionConversation = path === "/companion/conversation"
      if (needsReview) {
        void ensureI18nNamespaces(["review"])
      }
      if (needsCompanionConversation) {
        void ensureI18nNamespaces(["sidepanel", "common"])
      }
    } else {
      void ensureI18nNamespaces(["sidepanel", "common", "settings", "playground"])
      void ensureI18nNamespaces(["dataTables"])
      // Sidepanel uses some "option" strings; keep loaded for now to avoid missing labels.
      void ensureI18nNamespaces(["option"])
    }
  }, [kind, location.pathname])
  React.useEffect(() => {
    setChatSidebarCollapsed(true)
    void setSetting(HEADER_SHORTCUTS_EXPANDED_SETTING, false).catch(() => {
      // ignore storage write failures
    })
  }, [location.pathname, setChatSidebarCollapsed])
  const { label, description } = ROUTE_FALLBACKS[kind]
  const routes = kind === "options" ? optionRoutes : sidepanelRoutes
  const visibleRoutes = getRoutesForTarget(routes, platformConfig.target)
  const attemptedRoute = `${location.pathname}${location.search}${location.hash}` || "/"
  const handleOptionsReset = () => {
    if (typeof window !== "undefined") {
      window.location.reload()
    }
  }
  const handleSidepanelReset = () => {
    if (typeof window !== "undefined") {
      window.location.reload()
    }
  }
  const routesContent = (
    <Routes>
      {visibleRoutes.map((route) => {
        const routeEnabled =
          capabilitiesLoading ||
          isRouteEnabledForCapabilities(route.path, capabilities)

        return (
          <Route
            key={route.path}
            path={route.path}
            element={
              routeEnabled
                ? route.element
                : <Navigate to="/settings" replace />
            }
          />
        )
      })}
      <Route
        path="*"
        element={<RouteNotFoundState routeLabel={attemptedRoute} kind={kind} />}
      />
    </Routes>
  )

  // For options routes, wrap in persistent OptionLayout so the header/sidebar
  // stay mounted across route navigation. Child routes that render their own
  // OptionLayout will become nested pass-through wrappers that can communicate
  // overrides (like hideHeader) up to this root shell.
  const wrappedContent = kind === "options"
    ? <OptionLayout>{routesContent}</OptionLayout>
    : routesContent  // sidepanel has its own layout

  return (
    <div className={`${mode === "dark" ? "dark" : "light"} arimo`}>
      <React.Suspense
        fallback={<PageAssistLoader label={label} description={description} />}
      >
        {kind === "options" ? (
          <OptionsErrorBoundary onReset={handleOptionsReset}>
            {wrappedContent}
          </OptionsErrorBoundary>
        ) : (
          <SidepanelErrorBoundary onReset={handleSidepanelReset}>
            {wrappedContent}
          </SidepanelErrorBoundary>
        )}
      </React.Suspense>
    </div>
  )
}
