import { AxiosError, AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it } from 'vitest';

import { apiClient, getApiErrorMessage } from './api';

/** Build an AxiosError carrying the given response body. */
function axiosErrorWith(data: unknown, message = 'Request failed'): AxiosError {
  const error = new AxiosError(message);
  error.response = {
    data,
    status: 400,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return error;
}

describe('getApiErrorMessage', () => {
  it('prefers a string `detail` from the response body', () => {
    expect(getApiErrorMessage(axiosErrorWith({ detail: 'Dataset is still processing' }))).toBe(
      'Dataset is still processing'
    );
  });

  it('falls back to `message` when `detail` is absent', () => {
    expect(getApiErrorMessage(axiosErrorWith({ message: 'Project not found' }))).toBe(
      'Project not found'
    );
  });

  it('unwraps the first entry of a FastAPI validation `detail` array', () => {
    const error = axiosErrorWith({
      detail: [
        { loc: ['body', 'email'], msg: 'value is not a valid email address' },
        { loc: ['body', 'password'], msg: 'field required' },
      ],
    });
    expect(getApiErrorMessage(error)).toBe('value is not a valid email address');
  });

  it('uses the axios message when the body carries no usable detail', () => {
    expect(getApiErrorMessage(axiosErrorWith({}, 'Network Error'))).toBe('Network Error');
  });

  it('ignores a non-string, non-array `detail`', () => {
    // A dict detail has no msg to surface, so the axios message is used.
    expect(getApiErrorMessage(axiosErrorWith({ detail: { code: 500 } }, 'Server Error'))).toBe(
      'Server Error'
    );
  });

  it('reads the message off a plain Error', () => {
    expect(getApiErrorMessage(new Error('boom'))).toBe('boom');
  });

  it('returns a generic message for values that are not errors', () => {
    expect(getApiErrorMessage('a bare string')).toBe('An unexpected error occurred');
    expect(getApiErrorMessage(undefined)).toBe('An unexpected error occurred');
  });
});

describe('apiClient auth interceptor', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  /** Run the registered request interceptors over a bare config. */
  async function runRequestInterceptors() {
    const handlers = (
      apiClient.interceptors.request as unknown as {
        handlers: Array<{ fulfilled?: (c: unknown) => unknown } | null>;
      }
    ).handlers;
    let config: unknown = { headers: new AxiosHeaders() };
    for (const handler of handlers) {
      if (handler?.fulfilled) config = await handler.fulfilled(config);
    }
    return config as { headers: AxiosHeaders };
  }

  it('attaches a bearer token from the persisted auth store', async () => {
    localStorage.setItem(
      'auth-storage',
      JSON.stringify({ state: { accessToken: 'token-abc' }, version: 0 })
    );
    const config = await runRequestInterceptors();
    expect(config.headers.Authorization).toBe('Bearer token-abc');
  });

  it('sends no Authorization header when nothing is stored', async () => {
    const config = await runRequestInterceptors();
    expect(config.headers.Authorization).toBeUndefined();
  });

  it('does not throw when the stored value is not valid JSON', async () => {
    localStorage.setItem('auth-storage', 'not-json{');
    const config = await runRequestInterceptors();
    expect(config.headers.Authorization).toBeUndefined();
  });

  it('does not throw when the stored value has no accessToken', async () => {
    localStorage.setItem('auth-storage', JSON.stringify({ state: {} }));
    const config = await runRequestInterceptors();
    expect(config.headers.Authorization).toBeUndefined();
  });
});
