import React, { useEffect, useMemo, useState } from 'react';
import { MapPin, Plus, Loader2, Clock, Search } from 'lucide-react';
import { getConversations } from '../../api/client';

function SidebarToggleGlyph({ collapsed }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 13 13"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="overflow-visible"
    >
      <rect x="1.25" y="1.25" width="10.5" height="10.5" rx="1.6" stroke="currentColor" strokeWidth="1.2" />
      <line x1="4.35" y1="1.85" x2="4.35" y2="11.15" stroke="currentColor" strokeWidth="1.2" />
      {collapsed ? (
        <path
          d="M7.1 6.5L5.7 5.15M7.1 6.5L5.7 7.85M7.1 6.5H10"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <path
          d="M7.6 6.5L9 5.15M7.6 6.5L9 7.85M7.6 6.5H4.9"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}

export default function Sidebar({ token, activeConversationId, refreshKey, onSelect, onNewChat }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!token) {
      setConversations([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    getConversations(token)
      .then((data) => setConversations(data.conversations || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token, refreshKey]);

  const filteredConversations = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    if (!normalized) return conversations;

    const keywords = normalized.split(/\s+/).filter(Boolean);
    return conversations.filter((conversation) => {
      const title = (conversation.title || '').toLowerCase();
      return keywords.every((keyword) => title.includes(keyword));
    });
  }, [conversations, searchQuery]);

  return (
    <aside
      className={`flex-shrink-0 bg-ramp-bg border-r border-ramp-border flex flex-col h-full transition-all duration-200
        ${collapsed ? 'w-12' : 'w-52'}`}
    >
      {/* Top: collapse toggle + New Trip */}
      <div className={`flex items-center border-b border-ramp-border h-12 px-2 gap-2`}>
        {!collapsed && (
          <button
            onClick={onNewChat}
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5
                       bg-transparent border border-ramp-border text-ramp-text text-xs font-medium
                       hover:bg-ramp-surface-alt transition-colors"
          >
            <Plus size={13} />
            New Trip
          </button>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="w-7 h-7 flex items-center justify-center
                     border border-ramp-border text-ramp-text-tertiary
                     hover:bg-ramp-surface-alt hover:text-ramp-text transition-colors flex-shrink-0"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <SidebarToggleGlyph collapsed={collapsed} />
        </button>
      </div>

      {/* Nav section label */}
      {!collapsed && (
        <div className="px-3 pt-3 pb-1 space-y-3">
          <p className="text-[10px] uppercase tracking-widest text-ramp-text-tertiary font-semibold">My Trips</p>
          <label className="relative block">
            <Search
              size={12}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ramp-text-tertiary pointer-events-none"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search through my trips"
              className="w-full border border-ramp-border bg-ramp-surface pl-8 pr-3 py-2 text-xs text-ramp-text placeholder:text-ramp-text-tertiary focus:outline-none focus:border-ramp-text"
            />
          </label>
        </div>
      )}

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto pb-4">
        {loading ? (
          <div className="flex justify-center mt-6">
            <Loader2 size={15} className="animate-spin text-ramp-text-tertiary" />
          </div>
        ) : conversations.length === 0 && !collapsed ? (
          <div className="px-3 mt-3">
            <p className="text-xs text-ramp-text-tertiary">No trips yet. Start planning!</p>
          </div>
        ) : filteredConversations.length === 0 && !collapsed ? (
          <div className="px-3 mt-3">
            <p className="text-xs text-ramp-text-tertiary">No trips match those first-prompt keywords.</p>
          </div>
        ) : (
          filteredConversations.map((c) => {
            const isActive = activeConversationId === c.id;
            return (
              <button
                key={c.id}
                onClick={() => onSelect(c)}
                title={collapsed ? (c.title || 'Untitled Trip') : undefined}
                className={`w-full text-left flex items-center gap-2.5 transition-colors
                  ${collapsed ? 'justify-center px-0 py-3' : 'px-3 py-2'}
                  ${isActive
                    ? 'bg-ramp-yellow/20 text-ramp-text font-medium border-r-2 border-ramp-yellow'
                    : 'text-ramp-text-secondary hover:bg-ramp-surface-alt hover:text-ramp-text'
                  }`}
              >
                <MapPin
                  size={13}
                  className={`flex-shrink-0 ${isActive ? 'text-ramp-text' : 'text-ramp-text-tertiary'}`}
                />
                {!collapsed && (
                  <span className="truncate text-xs leading-relaxed">{c.title || 'Untitled Trip'}</span>
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      {!collapsed && (
        <div className="border-t border-ramp-border px-3 py-2.5">
          <div className="flex items-center gap-2 text-[10px] text-ramp-text-tertiary">
            <Clock size={11} />
            <span>Recent activity</span>
          </div>
        </div>
      )}
    </aside>
  );
}
