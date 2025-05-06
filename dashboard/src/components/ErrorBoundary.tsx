import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode; // Optional custom fallback UI
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  // Update state so the next render will show the fallback UI.
  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error: error, errorInfo: null }; // Keep errorInfo null here
  }

  // Catch errors in any components below and re-render with error message
  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // You can also log error messages to an error reporting service here
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({
        error: error,
        errorInfo: errorInfo
    });
  }

  public render() {
    if (this.state.hasError) {
      // Render custom fallback UI if provided, otherwise a default one
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="p-4 border border-red-500 bg-red-100 text-red-700 rounded">
          <h2 className="font-bold">Something went wrong rendering this section.</h2>
          <p>Please check the browser console for more details.</p>
          {/* Optionally display error details during development */}
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <details className="mt-2 text-sm">
                <summary>Error Details</summary>
                <pre className="mt-1 p-2 bg-gray-100 rounded whitespace-pre-wrap break-words">
                    {this.state.error.toString()}
                    {this.state.errorInfo?.componentStack}
                </pre>
            </details>
          )}
        </div>
      );
    }

    // Normally, just render children
    return this.props.children;
  }
}

export default ErrorBoundary;
