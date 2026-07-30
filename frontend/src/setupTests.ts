// jest-dom adds the DOM matchers (toBeInTheDocument, toBeDisabled, ...).
// Version 6+ ships a dedicated Vitest entry that registers them on Vitest's
// expect rather than Jest's.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Vitest does not unmount rendered trees between tests, so do it explicitly to
// keep them isolated.
afterEach(() => {
  cleanup();
});
