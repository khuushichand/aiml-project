import React from "react"

type PromptPageErrorBoundaryProps = {
  children: React.ReactNode
  onReload?: () => void
  onNavigateToChat?: () => void
}

type PromptPageErrorBoundaryState = {
  hasError: boolean
  error: Error | null
  resetKey: number
}

export class PromptPageErrorBoundary extends React.Component<
  PromptPageErrorBoundaryProps,
  PromptPageErrorBoundaryState
> {
  state: PromptPageErrorBoundaryState = {
    hasError: false,
    error: null,
    resetKey: 0
  }

  static getDerivedStateFromError(error: Error): PromptPageErrorBoundaryState {
    return {
      hasError: true,
      error,
      resetKey: 0
    }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("PromptPageErrorBoundary caught error:", error, errorInfo.componentStack)
  }

  private handleRetry = () => {
    this.setState((prev) => ({
      hasError: false,
      error: null,
      resetKey: prev.resetKey + 1
    }))
  }

  private handleReload = () => {
    if (typeof this.props.onReload === "function") {
      this.props.onReload()
      return
    }
    if (typeof window !== "undefined") {
      window.location.reload()
    }
  }

  private handleGoToChat = () => {
    if (typeof this.props.onNavigateToChat === "function") {
      this.props.onNavigateToChat()
      return
    }
    if (typeof window !== "undefined") {
      window.location.assign("/chat")
    }
  }

  render(): React.ReactNode {
    if (!this.state.hasError) {
      return (
        <React.Fragment key={this.state.resetKey}>
          {this.props.children}
        </React.Fragment>
      )
    }

    return (
      <div
        className="flex min-h-[50vh] w-full items-center justify-center px-4 py-8"
        data-testid="prompts-error-boundary"
      >
        <div className="w-full max-w-xl rounded-lg border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold text-text">Something went wrong</h2>
          <p className="mt-2 text-sm text-text-muted">
            The Prompts page hit an unexpected error. You can try again or reload.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primaryStrong"
              onClick={this.handleRetry}
              data-testid="prompts-error-retry"
            >
              Try again
            </button>
            <button
              type="button"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              onClick={this.handleReload}
              data-testid="prompts-error-reload"
            >
              Reload page
            </button>
            <button
              type="button"
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              onClick={this.handleGoToChat}
              data-testid="prompts-error-go-chat"
            >
              Go to Chat
            </button>
          </div>
          {process.env.NODE_ENV !== "production" && this.state.error ? (
            <details className="mt-4 text-xs text-text-subtle" data-testid="prompts-error-details">
              <summary className="cursor-pointer">View error details</summary>
              <pre className="mt-2 whitespace-pre-wrap rounded-md bg-surface2 p-2">
                {this.state.error.message}
              </pre>
            </details>
          ) : null}
        </div>
      </div>
    )
  }
}

export default PromptPageErrorBoundary
