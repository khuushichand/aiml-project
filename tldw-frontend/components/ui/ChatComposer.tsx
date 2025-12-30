import React, { forwardRef, useImperativeHandle, useRef } from 'react';

export interface ChatComposerProps {
  placeholder?: string;
  text?: string;
  onChange?: (value: string) => void;
  onSend?: (type: string, content: string) => void;
  rows?: number;
  showSend?: boolean;
  disabled?: boolean;
  rightActions?: React.ReactNode[];
}

export interface ChatComposerHandle {
  setText: (text: string) => void;
  focus: () => void;
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(
  ({ placeholder, text = '', onChange, onSend, rows = 2, disabled, rightActions }, ref) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      setText: (newText: string) => {
        if (onChange) onChange(newText);
      },
      focus: () => {
        textareaRef.current?.focus();
      },
    }));

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (onSend && text.trim()) {
          onSend('text', text);
        }
      }
    };

    return (
      <div className="flex items-end gap-2 border-t bg-white p-3">
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
          placeholder={placeholder}
          value={text}
          onChange={(e) => onChange?.(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={rows}
          disabled={disabled}
        />
        {rightActions && (
          <div className="flex gap-1">
            {rightActions}
          </div>
        )}
      </div>
    );
  }
);

ChatComposer.displayName = 'ChatComposer';
