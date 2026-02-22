import { Component, Fragment, type ReactNode, type ErrorInfo } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  resetKey: number;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error, errorInfo: undefined };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught error:', error, info.componentStack);
    this.setState({ errorInfo: info });

    if (typeof window === 'undefined') {
      return;
    }

    const sentry = (window as unknown as {
      Sentry?: {
        captureException?: (err: Error, context?: { extra?: Record<string, unknown> }) => void;
      };
    }).Sentry;
    if (sentry?.captureException) {
      sentry.captureException(error, { extra: { componentStack: info.componentStack } });
    }

    const analytics = (window as unknown as {
      analytics?: { track?: (event: string, properties?: Record<string, unknown>) => void };
    }).analytics;
    if (analytics?.track) {
      analytics.track('error_boundary', {
        message: error.message,
        componentStack: info.componentStack,
      });
    }
  }

  handleReset = () => {
    this.setState((prev) => ({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
      resetKey: prev.resetKey + 1,
    }));
  };

  render() {
    if (!this.state.hasError) {
      return <Fragment key={this.state.resetKey}>{this.props.children}</Fragment>;
    }
    const showErrorDetails = process.env.NODE_ENV !== 'production';

    return (
      <div className="min-h-screen bg-bg px-4 py-12" data-testid="error-boundary">
        <div className="mx-auto max-w-lg rounded-lg bg-surface p-6 text-center shadow">
          <h1 className="text-2xl font-semibold text-text">Something went wrong</h1>
          <p className="mt-2 text-sm text-text-muted">
            An unexpected error occurred. Try again or reload the page.
          </p>
          {showErrorDetails && this.state.error?.message && (
            <p className="mt-4 text-sm text-danger">{this.state.error.message}</p>
          )}
          {!showErrorDetails && (
            <p className="mt-4 text-sm text-text-muted">Something went wrong.</p>
          )}
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={this.handleReset}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primaryStrong"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium text-text hover:bg-surface2"
            >
              Reload page
            </button>
          </div>
        </div>
      </div>
    );
  }
}
