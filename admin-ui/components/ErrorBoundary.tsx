'use client';

import React, { Component, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  showDetails: boolean;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });

    // Log error to console
    console.error('Error Boundary caught an error:', error, errorInfo);

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  toggleDetails = () => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
          <Card className="max-w-lg w-full">
            <CardHeader className="text-center">
              <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
                <AlertTriangle className="h-6 w-6 text-destructive" />
              </div>
              <CardTitle>Something went wrong</CardTitle>
              <CardDescription>
                An unexpected error occurred. Don&apos;t worry, your data is safe.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Error message */}
              <div className="rounded-lg bg-muted p-3">
                <p className="text-sm font-medium text-destructive">
                  {this.state.error?.message || 'Unknown error'}
                </p>
              </div>

              {/* Action buttons */}
              <div className="flex flex-col sm:flex-row gap-2">
                <Button onClick={this.handleReset} className="flex-1">
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Try Again
                </Button>
                <Button variant="outline" onClick={this.handleGoHome} className="flex-1">
                  <Home className="mr-2 h-4 w-4" />
                  Go to Dashboard
                </Button>
              </div>

              {/* Technical details toggle */}
              <button
                onClick={this.toggleDetails}
                className="flex items-center justify-center w-full text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {this.state.showDetails ? (
                  <>
                    <ChevronUp className="mr-1 h-4 w-4" />
                    Hide technical details
                  </>
                ) : (
                  <>
                    <ChevronDown className="mr-1 h-4 w-4" />
                    Show technical details
                  </>
                )}
              </button>

              {/* Technical details */}
              {this.state.showDetails && (
                <div className="rounded-lg bg-muted p-3 overflow-auto max-h-48">
                  <p className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                    {this.state.error?.stack || 'No stack trace available'}
                  </p>
                  {this.state.errorInfo && (
                    <div className="mt-2 pt-2 border-t border-border">
                      <p className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                        Component Stack:
                        {this.state.errorInfo.componentStack}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Help text */}
              <p className="text-xs text-center text-muted-foreground">
                If this problem persists, please contact your administrator.
              </p>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
) {
  function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    );
  }

  const wrappedName = WrappedComponent.displayName || WrappedComponent.name || 'Component';
  WithErrorBoundary.displayName = `withErrorBoundary(${wrappedName})`;

  return WithErrorBoundary;
}

// Page-level error boundary with simpler UI
export function PageErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      onError={(error) => {
        // Could send to error reporting service here
        console.error('Page error:', error.message);
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

// Card-level error boundary for smaller sections
interface CardErrorBoundaryProps {
  children: ReactNode;
  title?: string;
}

export function CardErrorBoundary({ children, title = 'This section' }: CardErrorBoundaryProps) {
  return (
    <ErrorBoundary
      fallback={
        <Card className="border-destructive/50">
          <CardContent className="py-8 text-center">
            <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              {title} failed to load.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => window.location.reload()}
            >
              <RefreshCw className="mr-2 h-3 w-3" />
              Reload
            </Button>
          </CardContent>
        </Card>
      }
    >
      {children}
    </ErrorBoundary>
  );
}

export default ErrorBoundary;
