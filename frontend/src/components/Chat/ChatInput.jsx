import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

export default function ChatInput({ onSend, disabled, placeholder }) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
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
          placeholder={placeholder || "Describe your dream trip…"}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm text-ramp-text
                     placeholder:text-ramp-text-tertiary outline-none py-1
                     min-h-[36px] max-h-[200px] leading-relaxed"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="flex-shrink-0 h-9 px-4 flex items-center justify-center gap-1.5
                     bg-ramp-yellow text-ramp-text text-xs font-semibold
                     hover:bg-ramp-yellow-hover transition-colors
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {disabled ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <>
              <Send size={13} />
              <span>Send</span>
            </>
          )}
        </button>
      </div>
      <div className="px-4 pb-2.5">
        <p className="text-2xs text-ramp-text-tertiary">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}