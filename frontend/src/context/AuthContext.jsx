import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

// Single source of truth for auth. Login is optional (anonymous-allowed), so the
// whole app renders whether or not a user is present; this context just adds the
// bearer token to requests and exposes the current user.

const API_BASE = 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'ai_scam_guard_token';

const AuthContext = createContext(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false); // finished the initial /me validation

  // Validate a stored token whenever it changes: load the account, or drop a token
  // the server no longer accepts (expired / unknown).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) { setUser(null); setReady(true); return; }
      try {
        const res = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
        if (cancelled) return;
        if (res.ok) {
          setUser(await res.json());
        } else {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setUser(null);
        }
      } catch {
        // Network error: keep the token (server may just be down) but treat as
        // logged-out for this session.
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const authenticate = useCallback(async (path, email, password) => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Authentication failed. Please try again.');
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const login = useCallback((email, password) => authenticate('/auth/login', email, password), [authenticate]);
  const register = useCallback((email, password) => authenticate('/auth/register', email, password), [authenticate]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Drop-in for fetch() that attaches the bearer token when logged in. Anonymous
  // callers just get a plain fetch, which the backend accepts.
  const authFetch = useCallback((url, opts = {}) => {
    const headers = { ...(opts.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(url, { ...opts, headers });
  }, [token]);

  const value = { token, user, ready, isAuthed: !!user, login, register, logout, authFetch };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
