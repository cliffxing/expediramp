import React from 'react';
import { Plus, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Header({ onNewChat, onShowAuth }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-ramp-border h-14 flex items-center">
      <div className="w-full px-5 flex items-center justify-between">
        {/* Logo only — no wordmark */}
        <img src="/favicon.svg" alt="ExpediRamp" className="w-5 h-5" />

        {/* Right side */}
        <div className="flex items-center gap-2">
          {user ? (
            <div className="flex items-center gap-3">
              <span className="text-xs text-ramp-text-secondary hidden sm:inline">{user.email}</span>
              <div className="h-4 w-px bg-ramp-border" />
              <button
                onClick={logout}
                className="w-8 h-8 flex items-center justify-center
                           border border-ramp-border hover:bg-ramp-surface-alt transition-colors"
                title="Sign out"
              >
                <LogOut size={13} className="text-ramp-text-secondary" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={onNewChat}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                           bg-transparent border border-ramp-border text-ramp-text
                           hover:bg-ramp-surface-alt transition-colors"
              >
                <Plus size={13} />
                New Trip
              </button>
              <button
                onClick={onShowAuth}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold
                           bg-ramp-yellow text-ramp-text border border-transparent
                           hover:bg-ramp-yellow-hover transition-colors"
              >
                Sign In
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}