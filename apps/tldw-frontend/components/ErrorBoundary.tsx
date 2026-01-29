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
      <div className="min-h-screen bg-gray-50 px-4 py-12" data-testid="error-boundary">
        <div className="mx-auto max-w-lg rounded-lg bg-white p-6 text-center shadow">
          <h1 className="text-2xl font-semibold text-gray-900">Something went wrong</h1>
          <p className="mt-2 text-sm text-gray-600">
            An unexpected error occurred. Try again or reload the page.
          </p>
          {showErrorDetails && this.state.error?.message && (
            <p className="mt-4 text-sm text-red-600">{this.state.error.message}</p>
          )}
          {!showErrorDetails && (
            <p className="mt-4 text-sm text-gray-500">Something went wrong.</p>
          )}
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={this.handleReset}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Reload page
            </button>
          </div>
        </div>
      </div>
    );
  }
}
