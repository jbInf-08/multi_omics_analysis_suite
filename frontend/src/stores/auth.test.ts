import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { User } from '../lib/api';

const login = vi.fn();
const register = vi.fn();
const logout = vi.fn();
const me = vi.fn();

vi.mock('../lib/api', () => ({
  endpoints: {
    auth: {
      login: (...args: unknown[]) => login(...args),
      register: (...args: unknown[]) => register(...args),
      logout: (...args: unknown[]) => logout(...args),
      me: (...args: unknown[]) => me(...args),
    },
  },
}));

const { useAuthStore } = await import('./auth');

const alice: User = { id: 'u1', email: 'alice@example.com', full_name: 'Alice' };

/** Reset both the store and its persisted copy between tests. */
function resetStore() {
  localStorage.clear();
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });
}

describe('useAuthStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    logout.mockResolvedValue(undefined);
    resetStore();
  });

  it('stores the user and tokens on a successful login', async () => {
    login.mockResolvedValue({
      user: alice,
      access_token: 'access-1',
      refresh_token: 'refresh-1',
    });

    await useAuthStore.getState().login('alice@example.com', 'pw');

    const state = useAuthStore.getState();
    expect(state.user).toEqual(alice);
    expect(state.accessToken).toBe('access-1');
    expect(state.refreshToken).toBe('refresh-1');
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('fetches the user separately when login omits one', async () => {
    login.mockResolvedValue({ access_token: 'access-1', refresh_token: 'refresh-1' });
    me.mockResolvedValue(alice);

    await useAuthStore.getState().login('alice@example.com', 'pw');
    // fetchUser is fired without being awaited by login, so let it settle.
    await vi.waitFor(() => expect(me).toHaveBeenCalledTimes(1));

    expect(useAuthStore.getState().user).toEqual(alice);
  });

  it('records the error and rethrows when login fails', async () => {
    login.mockRejectedValue(new Error('Invalid credentials'));

    await expect(useAuthStore.getState().login('alice@example.com', 'bad')).rejects.toThrow(
      'Invalid credentials'
    );

    const state = useAuthStore.getState();
    expect(state.error).toBe('Invalid credentials');
    expect(state.isLoading).toBe(false);
    expect(state.isAuthenticated).toBe(false);
  });

  it('falls back to a generic message when a non-Error is thrown', async () => {
    login.mockRejectedValue('nope');

    await expect(useAuthStore.getState().login('alice@example.com', 'bad')).rejects.toBeTruthy();
    expect(useAuthStore.getState().error).toBe('Login failed');
  });

  it('clears state on logout', () => {
    useAuthStore.setState({
      user: alice,
      accessToken: 'access-1',
      refreshToken: 'refresh-1',
      isAuthenticated: true,
      error: 'stale',
    });

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.error).toBeNull();
  });

  it('does not reject when the logout endpoint fails', () => {
    logout.mockRejectedValue(new Error('offline'));
    expect(() => useAuthStore.getState().logout()).not.toThrow();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('marks the session authenticated when tokens are set directly', () => {
    useAuthStore.getState().setTokens('access-2', 'refresh-2');

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe('access-2');
    expect(state.refreshToken).toBe('refresh-2');
    expect(state.isAuthenticated).toBe(true);
  });

  it('skips fetchUser entirely when there is no access token', async () => {
    await useAuthStore.getState().fetchUser();
    expect(me).not.toHaveBeenCalled();
  });

  it('logs out when fetchUser rejects', async () => {
    useAuthStore.setState({ accessToken: 'expired', isAuthenticated: true });
    me.mockRejectedValue(new Error('401'));

    await useAuthStore.getState().fetchUser();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.isLoading).toBe(false);
  });

  it('clears a recorded error', () => {
    useAuthStore.setState({ error: 'something failed' });
    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });
});
