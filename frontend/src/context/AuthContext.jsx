import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import {
  createUserWithEmailAndPassword,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';

import * as api from '../api/client';
import { auth, persistenceReady } from '../lib/firebase';

const AuthContext = createContext(null);

function mapAuthError(error, mode) {
  switch (error?.code) {
    case 'auth/email-already-in-use':
      return 'An account with this email already exists. Sign in instead.';
    case 'auth/invalid-credential':
    case 'auth/invalid-login-credentials':
    case 'auth/user-not-found':
    case 'auth/wrong-password':
      return 'Invalid email or password.';
    case 'auth/weak-password':
      return 'Password should be at least 6 characters.';
    case 'auth/too-many-requests':
      return 'Too many attempts. Please wait a moment and try again.';
    case 'auth/network-request-failed':
      return 'Network error. Please check your connection and try again.';
    default:
      return error?.message || `${mode} failed`;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    let unsubscribe = () => {};

    persistenceReady
      .catch(() => null)
      .then(() => {
        unsubscribe = onIdTokenChanged(auth, async (firebaseUser) => {
          if (!isMounted) return;

          if (!firebaseUser) {
            setUser(null);
            setToken(null);
            setLoading(false);
            return;
          }

          try {
            const idToken = await firebaseUser.getIdToken();
            const data = await api.getMe(idToken);
            if (!isMounted) return;
            setToken(idToken);
            setUser(data.user);
          } catch {
            if (!isMounted) return;
            setToken(await firebaseUser.getIdToken());
            setUser({ id: firebaseUser.uid, email: firebaseUser.email });
          } finally {
            if (isMounted) {
              setLoading(false);
            }
          }
        });
      });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  const login = useCallback(async (email, password) => {
    try {
      await persistenceReady;
      const credential = await signInWithEmailAndPassword(auth, email, password);
      const idToken = await credential.user.getIdToken();
      const nextUser = { id: credential.user.uid, email: credential.user.email };
      setToken(idToken);
      setUser(nextUser);
      return { user: nextUser, session: { access_token: idToken } };
    } catch (error) {
      throw new Error(mapAuthError(error, 'Login'));
    }
  }, []);

  const signUp = useCallback(async (email, password) => {
    try {
      await persistenceReady;
      const credential = await createUserWithEmailAndPassword(auth, email, password);
      const idToken = await credential.user.getIdToken();
      const nextUser = { id: credential.user.uid, email: credential.user.email };
      setToken(idToken);
      setUser(nextUser);
      return { user: nextUser, session: { access_token: idToken } };
    } catch (error) {
      throw new Error(mapAuthError(error, 'Signup'));
    }
  }, []);

  const logout = useCallback(() => {
    signOut(auth).catch(() => null);
    setUser(null);
    setToken(null);
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
