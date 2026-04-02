import React, { useEffect, useState } from 'react';
import { MapPin, Plus, Loader2, Clock, ChevronLeft, ChevronRight } from 'lucide-react';
import { getConversations } from '../../api/client';

export default function Sidebar({ token, activeConversationId, onSelect, onNewChat }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!token) return;
    getConversations(token)
      .then((data) => setConversations(data.conversations || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token, activeConversationId]);

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
          {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
        </button>
      </div>

      {/* Nav section label */}
      {!collapsed && (
        <div className="px-3 pt-3 pb-1">
          <p className="text-[10px] uppercase tracking-widest text-ramp-text-tertiary font-semibold">My Trips</p>
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
        ) : (
          conversations.map((c) => {
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