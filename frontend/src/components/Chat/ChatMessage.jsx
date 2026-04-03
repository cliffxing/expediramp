import React from 'react';
import { Download, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatMessage({ role, content, isStreaming, canDownloadPdf = false, onDownloadPdf }) {
  const isUser = role === 'user';

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 flex items-center justify-center overflow-hidden
          ${isUser
            ? 'bg-ramp-surface-alt border border-ramp-border'
            : 'bg-ramp-yellow'
          }`}
      >
        {isUser ? (
          <User size={14} className="text-ramp-text-secondary" />
        ) : (
          <img
            src="/favicon.svg"
            alt="Expediramp"
            className="w-8 h-8 p-1.5"
            style={{ transform: 'scale(1.45)', transformOrigin: 'center' }}
          />
        )}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${isUser ? 'text-right' : ''}`}>
        <div className={`mb-1 flex items-center gap-2 ${isUser ? 'justify-end' : 'justify-between'}`}>
          <p className="text-2xs font-medium text-ramp-text-tertiary">
            {isUser ? 'You' : 'Expediramp'}
          </p>
          {!isUser && canDownloadPdf && (
            <button
              type="button"
              onClick={onDownloadPdf}
              className="inline-flex items-center justify-center w-7 h-7 border border-ramp-border bg-ramp-surface-alt text-ramp-text-secondary transition-colors hover:bg-ramp-yellow hover:text-ramp-text"
              aria-label="Download trip as PDF"
              title="Download trip as PDF"
            >
              <Download size={13} />
            </button>
          )}
        </div>
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
