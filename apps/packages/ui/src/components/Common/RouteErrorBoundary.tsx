import React, { type ErrorInfo, type ReactNode } from "react"
import { useLocation, useNavigate } from "react-router-dom"

type RouteErrorBoundaryProps = {
  children: ReactNode
  routeId: string
  routeLabel: string
  chatPath?: string
  settingsPath?: string
}

type RouteErrorBoundaryInnerProps = RouteErrorBoundaryProps & {
  onNavigate: (path: string) => void
}

type RouteErrorBoundaryState = {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  resetKey: number
}

const DEFAULT_CHAT_PATH = "/"
const DEFAULT_SETTINGS_PATH = "/settings"
export const ROUTE_ERROR_FIXTURE_QUERY_KEY = "__forceRouteError"

const ForcedRouteErrorProbe: React.FC<{ routeId: string }> = ({ routeId }) => {
  throw new Error(`Forced route boundary error for ${routeId}`)
}

function shouldForceRouteError(search: string, routeId: string): boolean {
  if (process.env.NODE_ENV === "production") {
    return false
  }

  if (!search) {
    return false
  }

  const params = new URLSearchParams(search)
  const forceValue = params.get(ROUTE_ERROR_FIXTURE_QUERY_KEY)?.trim().toLowerCase()

  if (!forceValue) {
    return false
  }

  const normalizedRouteId = routeId.trim().toLowerCase()
  return forceValue === "1" || forceValue === "all" || forceValue === normalizedRouteId
}

class RouteErrorBoundaryInner extends React.Component<
  RouteErrorBoundaryInnerProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
    resetKey: 0
  }

  static getDerivedStateFromError(error: Error): Partial<RouteErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo })
    console.error(`[RouteErrorBoundary:${this.props.routeId}]`, error, errorInfo.componentStack)
  }

  handleRetry = (): void => {
    this.setState((prev) => ({
      hasError: false,
      error: null,
      errorInfo: null,
      resetKey: prev.resetKey + 1
    }))
  }

  handleReload = (): void => {
    if (typeof window !== "undefined") {
      window.location.reload()
    }
  }

  handleNavigate = (path: string): void => {
    this.props.onNavigate(path)
  }

  render(): ReactNode {
    if (!this.state.hasError) {
      return <React.Fragment key={this.state.resetKey}>{this.props.children}</React.Fragment>
    }

    const chatPath = this.props.chatPath ?? DEFAULT_CHAT_PATH
    const settingsPath = this.props.settingsPath ?? DEFAULT_SETTINGS_PATH
    const showErrorDetails = process.env.NODE_ENV !== "production"
    const routeScopeId = `route-error-boundary-${this.props.routeId}`

    return (
      <div className="flex min-h-[70vh] w-full items-center justify-center px-6 py-12" data-testid="error-boundary">
        <div className="w-full max-w-xl rounded-xl border border-border bg-surface p-8 shadow-sm" data-testid={routeScopeId}>
          <h1 className="text-2xl font-semibold text-text" data-testid="route-error-title">
            This page hit an unexpected error
          </h1>
          <p className="mt-3 text-sm text-text-muted" data-testid="route-error-message">
            Try loading the route again. If the issue continues, continue in Chat or Settings.
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Affected route:{" "}
            <code className="rounded bg-surface2 px-1 py-0.5" data-testid="route-error-route-label">
              {this.props.routeLabel}
            </code>
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primaryStrong"
              onClick={this.handleRetry}
              data-testid="route-error-retry"
            >
              Try again
            </button>
            <button
              type="button"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              onClick={() => this.handleNavigate(chatPath)}
              data-testid="route-error-go-chat"
            >
              Go to Chat
            </button>
            <button
              type="button"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              onClick={() => this.handleNavigate(settingsPath)}
              data-testid="route-error-open-settings"
            >
              Open Settings
            </button>
            <button
              type="button"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              onClick={this.handleReload}
              data-testid="route-error-reload"
            >
              Reload page
            </button>
          </div>

          {showErrorDetails && this.state.error ? (
            <details className="mt-4 text-left text-xs text-text-subtle" data-testid="route-error-details">
              <summary className="cursor-pointer">View error details</summary>
              <pre className="mt-2 whitespace-pre-wrap rounded-md bg-surface2 p-3 text-[11px] text-danger">
                {this.state.error.message}
                {this.state.errorInfo?.componentStack ? `\n${this.state.errorInfo.componentStack}` : ""}
              </pre>
            </details>
          ) : null}
        </div>
      </div>
    )
  }
}

export const RouteErrorBoundary: React.FC<RouteErrorBoundaryProps> = ({
  chatPath = DEFAULT_CHAT_PATH,
  settingsPath = DEFAULT_SETTINGS_PATH,
  ...props
}) => {
  const navigate = useNavigate()
  const location = useLocation()
  const forceError = React.useMemo(
    () => shouldForceRouteError(location.search, props.routeId),
    [location.search, props.routeId]
  )
  const onNavigate = React.useCallback(
    (path: string) => {
      try {
        navigate(path)
      } catch {
        if (typeof window !== "undefined") {
          window.location.assign(path)
        }
      }
    },
    [navigate]
  )

  return (
    <RouteErrorBoundaryInner
      {...props}
      chatPath={chatPath}
      settingsPath={settingsPath}
      onNavigate={onNavigate}
    >
      {forceError ? <ForcedRouteErrorProbe routeId={props.routeId} /> : props.children}
    </RouteErrorBoundaryInner>
  )
}

export default RouteErrorBoundary
