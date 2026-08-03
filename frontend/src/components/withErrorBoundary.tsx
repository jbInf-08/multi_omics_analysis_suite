/**
 * withErrorBoundary
 * =================
 *
 * Lives outside ErrorBoundary.tsx so that module exports only components. React
 * Fast Refresh cannot update a module that mixes component and non-component
 * exports, and react-refresh/only-export-components flags it. A higher-order
 * component is a factory, not a component, so it counts as the latter.
 */

import React from 'react';
import type { FallbackProps } from 'react-error-boundary';
import { ErrorBoundary } from './ErrorBoundary';

// HOC for wrapping components with error boundary
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  fallback?: React.ComponentType<FallbackProps>
) {
  return function WrappedComponent(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}
