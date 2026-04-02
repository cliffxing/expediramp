import React, { useState, useEffect, useRef } from 'react';
import { Lock, AlertCircle, Loader2 } from 'lucide-react';

const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD;
const STORAGE_KEY = 'expediramp_demo_unlocked';

export default function DemoGate({ children }) {
  const [unlocked, setUnlocked] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);
  const inputRef = useRef(null);

  // If no password is configured (e.g. local dev without the var set), skip the gate entirely
  const gateEnabled = Boolean(DEMO_PASSWORD);

  useEffect(() => {
    if (!gateEnabled || sessionStorage.getItem(STORAGE_KEY) === '1') {
      setUnlocked(true);
    }
  }, [gateEnabled]);

  useEffect(() => {
    if (!unlocked) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [unlocked]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!password.trim()) return;

    setLoading(true);
    setError('');

    setTimeout(() => {
      if (password === DEMO_PASSWORD) {
        sessionStorage.setItem(STORAGE_KEY, '1');
        setUnlocked(true);
      } else {
        setError('Incorrect password. Please try again.');
        setPassword('');
        setLoading(false);
        setShake(true);
        setTimeout(() => setShake(false), 500);
        inputRef.current?.focus();
      }
    }, 400);
  };

  if (unlocked) return children;

  return (
    <div className="fixed inset-0 bg-ramp-bg flex flex-col items-center justify-center px-4">


      <div
        className="relative bg-ramp-surface border border-ramp-border shadow-ramp-lg w-full max-w-sm animate-slide-up"
        style={shake ? { animation: 'shake 0.45s ease' } : {}}
      >
        <div className="h-0.5 w-full bg-ramp-yellow" />

        <div className="px-7 pt-7 pb-2">
          <div className="w-11 h-11 overflow-hidden mb-5">
            <img
              src="/favicon.svg"
              alt="ExpediRamp"
              className="w-[58px] h-[58px]"
              style={{ transform: 'scale(1.35)', transformOrigin: 'center' }}
            />
          </div>

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-lg font-bold text-ramp-text tracking-tight">Private Demo</h1>
              <p className="text-sm text-ramp-text-secondary mt-1 leading-relaxed">
                Enter the access password to continue.
              </p>
            </div>
            <div className="w-8 h-8 border border-ramp-border bg-ramp-surface-alt flex items-center justify-center flex-shrink-0 ml-3 mt-0.5">
              <Lock size={13} className="text-ramp-text-secondary" />
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-7 pb-7 pt-5 space-y-4">
          {error && (
            <div className="flex items-start gap-2 p-3 bg-ramp-red-light text-ramp-red text-xs border border-ramp-red/20">
              <AlertCircle size={13} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-ramp-text-secondary mb-1.5 tracking-wide uppercase">
              Password
            </label>
            <div className="relative">
              <Lock size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ramp-text-tertiary" />
              <input
                ref={inputRef}
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(''); }}
                className="ramp-input pl-9"
                placeholder="••••••••••••••"
                autoComplete="current-password"
                disabled={loading}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !password.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                       bg-ramp-yellow text-ramp-text text-sm font-semibold
                       hover:bg-ramp-yellow-hover transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <><Loader2 size={13} className="animate-spin" />Verifying…</>
            ) : (
              'Continue to ExpediRamp'
            )}
          </button>
        </form>

        <div className="border-t border-ramp-border px-7 py-3 flex items-center justify-between">
          <span className="text-2xs text-ramp-text-tertiary">ExpediRamp · Private Demo</span>
          <span className="text-2xs font-medium text-ramp-text-tertiary bg-ramp-surface-alt border border-ramp-border px-1.5 py-0.5">
            BETA
          </span>
        </div>
      </div>

      <p className="relative mt-6 text-xs text-ramp-text-tertiary tracking-wide">
        Modern Travel Runs on ExpediRamp
      </p>

      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          15%       { transform: translateX(-6px); }
          30%       { transform: translateX(6px); }
          45%       { transform: translateX(-5px); }
          60%       { transform: translateX(5px); }
          75%       { transform: translateX(-3px); }
          90%       { transform: translateX(3px); }
        }
      `}</style>
    </div>
  );
}