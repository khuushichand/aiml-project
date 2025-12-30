import React, { forwardRef, useImperativeHandle, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

export interface ChatMessage {
  type?: string;
  position?: 'left' | 'right' | 'center';
  content?: string | { text?: string; name?: string; [key: string]: unknown };
  user?: { name?: string; avatar?: string };
}

export interface ChatMessageListProps {
  messages: ChatMessage[];
  renderMessageContent?: (msg: ChatMessage) => React.ReactNode;
  className?: string;
}

export interface ChatMessageListHandle {
  scrollToEnd: () => void;
}

export const ChatMessageList = forwardRef<ChatMessageListHandle, ChatMessageListProps>(
  ({ messages, renderMessageContent, className }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useImperativeHandle(ref, () => ({
      scrollToEnd: () => {
        if (containerRef.current) {
          containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
      },
    }));

    useEffect(() => {
      // Auto-scroll to bottom on new messages
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }, [messages]);

    const renderContent = (msg: ChatMessage) => {
      // Allow custom renderer
      if (renderMessageContent) {
        const custom = renderMessageContent(msg);
        if (custom !== undefined) return custom;
      }

      // Default text rendering
      const text = typeof msg.content === 'string'
        ? msg.content
        : msg.content?.text || '';

      return (
        <div className="whitespace-pre-wrap break-words">{text}</div>
      );
    };

    return (
      <div
        ref={containerRef}
        className={cn('flex-1 overflow-y-auto p-4 space-y-3', className)}
      >
        {messages.map((msg, idx) => {
          const isRight = msg.position === 'right';
          const isCenter = msg.position === 'center';

          return (
            <div
              key={idx}
              className={cn(
                'flex',
                isCenter && 'justify-center',
                isRight && 'justify-end',
                !isCenter && !isRight && 'justify-start'
              )}
            >
              <div
                className={cn(
                  'max-w-[80%] rounded-lg px-4 py-2 text-sm',
                  isRight
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-900',
                  isCenter && 'bg-gray-200 text-gray-600 text-xs'
                )}
              >
                {msg.user?.name && !isRight && (
                  <div className="mb-1 text-xs font-medium text-gray-500">
                    {msg.user.name}
                  </div>
                )}
                {renderContent(msg)}
              </div>
            </div>
          );
        })}
      </div>
    );
  }
);

ChatMessageList.displayName = 'ChatMessageList';
