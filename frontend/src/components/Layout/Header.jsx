import React from 'react';
import { Plus, LogOut, User } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Header({ onNewChat, onShowAuth }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 bg-ramp-bg/80 backdrop-blur-xl border-b border-ramp-border">
      <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-ramp-accent rounded-lg flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
              <path d="M4 22V6h12l-4 5H8v11H4z" fill="#FAFAF8"/>
              <path d="M14 6l12 8-12 8V6z" fill="#1B7A4A"/>
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-bold text-ramp-text tracking-tight leading-none">ExpediRamp</h1>
            <p className="text-2xs text-ramp-text-tertiary leading-none mt-0.5">Modern travel</p>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {!user && (
            <button onClick={onNewChat} className="ramp-btn-secondary gap-1.5 text-xs py-2 px-3">
              <Plus size={14} />
              New Trip
            </button>
          )}

          {user ? (
            <div className="flex items-center gap-2">
              <span className="text-2xs text-ramp-text-tertiary hidden sm:inline">
                {user.email}
              </span>
              <button
                onClick={logout}
                className="w-8 h-8 rounded-ramp-sm flex items-center justify-center
                           border border-ramp-border hover:bg-ramp-surface-alt transition-colors"
                title="Sign out"
              >
                <LogOut size={14} className="text-ramp-text-secondary" />
              </button>
            </div>
          ) : (
            <button
              onClick={onShowAuth}
              className="ramp-btn-primary text-xs py-2 px-3"
            >
              Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
