import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('er_token'));
  const [loading, setLoading] = useState(true);

  // Check session on mount
  useEffect(() => {
    if (token) {
      api.getMe(token)
        .then((data) => setUser(data.user))
        .catch(() => { setToken(null); localStorage.removeItem('er_token'); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login(email, password);
    if (data.session) {
      setToken(data.session.access_token);
      localStorage.setItem('er_token', data.session.access_token);
    }
    setUser(data.user);
    return data;
  }, []);

  const signUp = useCallback(async (email, password) => {
    const data = await api.signup(email, password);
    if (data.session) {
      setToken(data.session.access_token);
      localStorage.setItem('er_token', data.session.access_token);
    }
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('er_token');
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signUp, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
