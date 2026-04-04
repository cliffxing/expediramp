import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

function useIsMobile(breakpoint = 640) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  );
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [breakpoint]);
  return isMobile;
}

export default function ChatInput({ onSend, disabled, placeholder, placeholderMobile }) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px';
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="bg-ramp-surface border border-ramp-border shadow-ramp-md focus-within:border-ramp-border-strong transition-colors">
      <div className="flex items-end gap-2 p-3">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={isMobile && placeholderMobile ? placeholderMobile : (placeholder || "Describe your dream trip…")}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm text-ramp-text
                     placeholder:text-ramp-text-tertiary outline-none py-1
                     min-h-[40px] max-h-[160px] leading-relaxed"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="flex-shrink-0 h-9 w-9 sm:h-10 sm:w-auto sm:px-4 flex items-center justify-center gap-1.5
                     bg-ramp-yellow text-ramp-text text-xs font-semibold
                     hover:bg-ramp-yellow-hover active:scale-95 transition-all
                     disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Send message"
        >
          {disabled ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <>
              <Send size={13} />
              <span className="hidden sm:inline">Send</span>
            </>
          )}
        </button>
      </div>
      {/* Desktop hint only — on mobile this row is hidden entirely to avoid the "jank" extra strip */}
      <div className="hidden sm:block px-4 pb-2.5">
        <p className="text-2xs text-ramp-text-tertiary">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}