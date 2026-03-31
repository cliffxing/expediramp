import React from 'react';
import { User, Sparkles } from 'lucide-react';

export default function ChatMessage({ role, content, isStreaming }) {
  const isUser = role === 'user';

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${isUser ? 'bg-ramp-surface-alt border border-ramp-border' : 'bg-ramp-accent'}`}
      >
        {isUser ? (
          <User size={14} className="text-ramp-text-secondary" />
        ) : (
          <Sparkles size={14} className="text-white" />
        )}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${isUser ? 'text-right' : ''}`}>
        <p className="text-2xs font-medium text-ramp-text-tertiary mb-1">
          {isUser ? 'You' : 'ExpediRamp'}
        </p>
        <div
          className={`rounded-ramp px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? 'bg-ramp-accent text-white rounded-tr-sm'
              : 'bg-ramp-surface border border-ramp-border rounded-tl-sm'
            }`}
        >
          <div className="whitespace-pre-wrap">{content}</div>
          {isStreaming && (
            <span className="inline-flex gap-1 ml-1 align-middle">
              <span className="typing-dot" style={{ animationDelay: '0ms' }} />
              <span className="typing-dot" style={{ animationDelay: '200ms' }} />
              <span className="typing-dot" style={{ animationDelay: '400ms' }} />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
