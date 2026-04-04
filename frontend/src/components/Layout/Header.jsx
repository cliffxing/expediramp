import React from 'react';
import { Plus, LogOut, Menu } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Header({ onNewChat, onShowAuth, onMobileSidebarOpen }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-ramp-border h-14 flex items-center">
      <div className="w-full px-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Hamburger — only shown on mobile when logged in */}
          {user && (
            <button
              onClick={onMobileSidebarOpen}
              className="md:hidden w-8 h-8 flex items-center justify-center
                         border border-ramp-border text-ramp-text-secondary
                         hover:bg-ramp-surface-alt transition-colors mr-1"
              title="Open trips menu"
              aria-label="Open trips menu"
            >
              <Menu size={15} />
            </button>
          )}

          {/* Logo */}
          <div className="w-[2.7rem] h-[2.7rem] flex items-center justify-center overflow-hidden">
            <img
              src="/favicon.svg"
              alt="Expediramp"
              className="w-[4.15rem] h-[4.15rem]"
              style={{ transform: 'scale(1.38)', transformOrigin: 'center' }}
            />
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {user ? (
            <div className="flex items-center gap-2 sm:gap-3">
              <span className="text-xs text-ramp-text-secondary hidden sm:inline truncate max-w-[160px]">{user.email}</span>
              <div className="h-4 w-px bg-ramp-border hidden sm:block" />
              {/* New Trip — hidden on very small screens, accessible via sidebar */}
              <button
                onClick={onNewChat}
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                           bg-transparent border border-ramp-border text-ramp-text
                           hover:bg-ramp-surface-alt transition-colors"
              >
                <Plus size={13} />
                New Trip
              </button>
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
                <span className="hidden sm:inline">New Trip</span>
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