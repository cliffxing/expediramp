import React, { useState } from 'react';
import { X, Loader2, Mail, Lock, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function AuthModal({ onClose }) {
  const { login, signUp } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await signUp(email, password);
      }
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-ramp-text/20 backdrop-blur-sm" onClick={onClose} />

      {/* Modal — sharp corners */}
      <div className="relative bg-ramp-surface shadow-ramp-lg w-full max-w-sm mx-4 animate-slide-up border border-ramp-border">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 w-7 h-7 flex items-center justify-center
                     hover:bg-ramp-surface-alt transition-colors"
        >
          <X size={15} className="text-ramp-text-secondary" />
        </button>

        <div className="px-7 pt-7 pb-2">
          {/* Logo — larger container with overflow hidden to crop SVG whitespace */}
          <div className="w-12 h-12 overflow-hidden mb-4">
            <img
              src="/favicon.svg"
              alt="Expediramp"
              className="w-16 h-16"
              style={{ transform: 'scale(1.35)', transformOrigin: 'center' }}
            />
          </div>
          <h2 className="text-lg font-bold text-ramp-text">
            {mode === 'login' ? 'Welcome back' : 'Create an account'}
          </h2>
          <p className="text-sm text-ramp-text-secondary mt-1">
            {mode === 'login'
              ? 'Sign in to save your trip plans.'
                : 'Start planning trips with Expediramp.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="px-7 pb-7 pt-4 space-y-4">
          {error && (
            <div className="flex items-start gap-2 p-3 bg-ramp-red-light text-ramp-red text-xs">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-ramp-text-secondary mb-1.5">Email</label>
            <div className="relative">
              <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ramp-text-tertiary" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="ramp-input pl-9"
                placeholder="you@example.com"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-ramp-text-secondary mb-1.5">Password</label>
            <div className="relative">
              <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ramp-text-tertiary" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="ramp-input pl-9"
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                       bg-ramp-yellow text-ramp-text text-sm font-semibold
                       hover:bg-ramp-yellow-hover transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>

          <p className="text-center text-xs text-ramp-text-tertiary">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              type="button"
              onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); }}
              className="text-ramp-text font-semibold hover:underline"
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
