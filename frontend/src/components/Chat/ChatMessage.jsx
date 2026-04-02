import React from 'react';
import { User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatMessage({ role, content, isStreaming }) {
  const isUser = role === 'user';

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-6 h-6 flex items-center justify-center
          ${isUser
            ? 'bg-ramp-surface-alt border border-ramp-border'
            : 'bg-ramp-yellow'
          }`}
      >
        {isUser ? (
          <User size={11} className="text-ramp-text-secondary" />
        ) : (
          <img src="/favicon.svg" alt="ExpediRamp" className="w-4 h-4" />
        )}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${isUser ? 'text-right' : ''}`}>
        <p className="text-2xs font-medium text-ramp-text-tertiary mb-1">
          {isUser ? 'You' : 'ExpediRamp'}
        </p>
        <div
          className={`px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? 'bg-ramp-text text-white'
              : 'bg-ramp-surface border border-ramp-border'
            }`}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">{content}</div>
          ) : (
            <div className="prose prose-sm max-w-none break-words [overflow-wrap:anywhere] prose-p:leading-relaxed prose-a:text-blue-600 prose-ul:my-1 prose-li:my-0 text-ramp-text">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
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