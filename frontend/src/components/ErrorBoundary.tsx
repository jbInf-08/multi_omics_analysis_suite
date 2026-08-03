/**
 * Error Boundary Components
 * =========================
 *
 * Error boundaries for graceful error handling with fallback UIs.
 */

import React, { type ErrorInfo } from 'react';
import { ErrorBoundary as ReactErrorBoundary, FallbackProps } from 'react-error-boundary';

/**
 * react-error-boundary 6 types FallbackProps.error as `unknown` rather than
 * `Error`, which is accurate -- `throw` accepts any value, so a rejected
 * promise carrying a string or a plain object reaches a boundary just as an
 * Error does. Narrow once here instead of asserting `as Error` at each use,
 * so a thrown non-Error renders its value rather than `undefined`.
 */
function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  if (typeof error === 'string') return new Error(error);
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error(String(error));
  }
}

// Error fallback component
function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const err = toError(error);
  return (
    <div className="min-h-[400px] flex items-center justify-center p-8">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center">
          <svg
            className="w-8 h-8 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Something went wrong
        </h2>
        <p className="text-gray-600 mb-4">
          {err.message || 'An unexpected error occurred'}
        </p>
        <div className="space-y-2">
          <button
            onClick={resetErrorBoundary}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
          >
            Try again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="w-full px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors"
          >
            Reload page
          </button>
        </div>
        {process.env.NODE_ENV === 'development' && (
          <details className="mt-4 text-left">
            <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
              Error details
            </summary>
            <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-h-32">
              {err.stack}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

// Page-level error fallback
function PageErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const err = toError(error);
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-8">
      <div className="max-w-lg w-full bg-white rounded-lg shadow-xl p-8 text-center">
        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-red-100 flex items-center justify-center">
          <svg
            className="w-10 h-10 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-3">
          Oops! Something went wrong
        </h1>
        <p className="text-gray-600 mb-6">
          We're sorry, but something unexpected happened. Please try again or contact support if the problem persists.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={resetErrorBoundary}
            className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
          >
            Try again
          </button>
          <button
            onClick={() => window.location.href = '/'}
            className="px-6 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors"
          >
            Go to Dashboard
          </button>
        </div>
        {process.env.NODE_ENV === 'development' && (
          <div className="mt-6 p-4 bg-gray-100 rounded-lg text-left">
            <p className="text-sm font-medium text-gray-700 mb-2">Error message:</p>
            <p className="text-sm text-red-600">{err.message}</p>
            <details className="mt-2">
              <summary className="text-sm text-gray-500 cursor-pointer">
                Stack trace
              </summary>
              <pre className="mt-2 text-xs overflow-auto max-h-40 p-2 bg-white rounded">
                {err.stack}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

// Error logging function
function logError(error: unknown, info: ErrorInfo) {
  // Log to console in development
  console.error('Error caught by boundary:', error);
  console.error('Component stack:', info.componentStack);

  // In production, send to error tracking service
  if (process.env.NODE_ENV === 'production') {
    // Example: Send to Sentry
    // Sentry.captureException(error, { extra: info });
  }
}

// Component error boundary
interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<FallbackProps>;
  onReset?: () => void;
}

export function ErrorBoundary({
  children,
  fallback = ErrorFallback,
  onReset,
}: ErrorBoundaryProps) {
  return (
    <ReactErrorBoundary
      FallbackComponent={fallback}
      onError={logError}
      onReset={onReset}
    >
      {children}
    </ReactErrorBoundary>
  );
}

// Page-level error boundary
export function PageErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ReactErrorBoundary
      FallbackComponent={PageErrorFallback}
      onError={logError}
      onReset={() => window.location.reload()}
    >
      {children}
    </ReactErrorBoundary>
  );
}

// withErrorBoundary lives in ./withErrorBoundary so this module exports only
// components -- see the note there.

export default ErrorBoundary;
