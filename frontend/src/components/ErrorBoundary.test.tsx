/**
 * ErrorBoundary tests
 * ===================
 *
 * react-error-boundary 6 changed FallbackProps.error from `Error` to
 * `unknown`, because `throw` accepts any value. These cover the non-Error
 * cases, which is where the old `error.message` access would have rendered
 * nothing at all.
 */

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from './ErrorBoundary';

function Boom({ value }: { value: unknown }): React.ReactElement {
  throw value;
}

describe('ErrorBoundary', () => {
  // The boundary logs via console.error; keep the test output readable.
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
  });

  it('shows the message of a thrown Error', () => {
    render(
      <ErrorBoundary>
        <Boom value={new Error('boundary caught this')} />
      </ErrorBoundary>
    );
    expect(screen.getByText('boundary caught this')).toBeInTheDocument();
  });

  it('shows a thrown string rather than blank', () => {
    render(
      <ErrorBoundary>
        <Boom value="just a string" />
      </ErrorBoundary>
    );
    expect(screen.getByText('just a string')).toBeInTheDocument();
  });

  it('serialises a thrown plain object rather than blank', () => {
    render(
      <ErrorBoundary>
        <Boom value={{ code: 418, reason: 'teapot' }} />
      </ErrorBoundary>
    );
    expect(screen.getByText(/teapot/)).toBeInTheDocument();
  });

  it('still renders the fallback for a thrown null', () => {
    render(
      <ErrorBoundary>
        <Boom value={null} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });
});
