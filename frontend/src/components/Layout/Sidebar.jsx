import React, { useEffect, useState } from 'react';
import { MessageSquare, Plus, Loader2 } from 'lucide-react';
import { getConversations } from '../../api/client';

export default function Sidebar({ token, activeConversationId, onSelect, onNewChat }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    getConversations(token)
      .then((data) => setConversations(data.conversations || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token, activeConversationId]); // refresh when a new convo is created

  return (
    <aside className="w-64 flex-shrink-0 bg-ramp-surface border-r border-ramp-border flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-ramp-border">
        <button
          onClick={onNewChat}
          className="w-full ramp-btn-secondary gap-2 text-xs justify-center py-2"
        >
          <Plus size={14} />
          New Trip
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="flex justify-center mt-6">
            <Loader2 size={16} className="animate-spin text-ramp-text-tertiary" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-2xs text-ramp-text-tertiary text-center mt-6 px-4">
            No trips yet. Start planning!
          </p>
        ) : (
          conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c)}
              className={`w-full text-left px-3 py-2.5 text-xs rounded-ramp-sm mx-1 flex items-start gap-2 transition-colors
                ${activeConversationId === c.id
                  ? 'bg-ramp-surface-alt text-ramp-text font-medium'
                  : 'text-ramp-text-secondary hover:bg-ramp-surface-alt hover:text-ramp-text'
                }`}
              style={{ width: 'calc(100% - 8px)' }}
            >
              <MessageSquare size={13} className="flex-shrink-0 mt-0.5 text-ramp-text-tertiary" />
              <span className="truncate">{c.title || 'Untitled Trip'}</span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}