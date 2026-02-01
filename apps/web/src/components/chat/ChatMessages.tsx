/**
 * Chat messages list component with auto-scroll.
 * Displays the conversation history and thinking indicator.
 */

import { useEffect, useRef, useCallback, type CSSProperties } from 'react';
import type { Message, AgentStage } from '../../lib/api-types';
import { ChatMessage } from './ChatMessage';
import { AgentThinking } from './AgentThinking';

export interface ChatMessagesProps {
  messages: Message[];
  agentStage?: AgentStage;
  thinkingMessage?: string;
  onApprove?: (messageId: string) => void;
  onEdit?: (messageId: string) => void;
  approvingMessageId?: string | null;
  isLoading?: boolean;
}

function WelcomeMessage() {
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    padding: '48px 24px',
    textAlign: 'center',
  };

  const iconStyle: CSSProperties = {
    width: '64px',
    height: '64px',
    borderRadius: '16px',
    backgroundColor: '#eff6ff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#3b82f6',
  };

  const titleStyle: CSSProperties = {
    fontSize: '20px',
    fontWeight: 600,
    color: '#1f2937',
    margin: 0,
  };

  const descriptionStyle: CSSProperties = {
    fontSize: '14px',
    color: '#6b7280',
    maxWidth: '400px',
    lineHeight: 1.6,
  };

  const tipStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginTop: '16px',
    padding: '16px',
    backgroundColor: '#f9fafb',
    borderRadius: '12px',
    width: '100%',
    maxWidth: '400px',
  };

  const tipItemStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    fontSize: '13px',
    color: '#374151',
    textAlign: 'left',
  };

  const bulletStyle: CSSProperties = {
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    backgroundColor: '#dbeafe',
    color: '#3b82f6',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '11px',
    fontWeight: 600,
    flexShrink: 0,
  };

  return (
    <div style={containerStyle}>
      <div style={iconStyle}>
        <svg width="32" height="32" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
      </div>

      <h2 style={titleStyle}>Welcome to Form Assistant</h2>

      <p style={descriptionStyle}>
        I can help you fill out forms quickly and accurately. Upload your documents
        and I will guide you through the process.
      </p>

      <div style={tipStyle}>
        <div style={tipItemStyle}>
          <span style={bulletStyle}>1</span>
          <span>Drop your form PDF and any source documents</span>
        </div>
        <div style={tipItemStyle}>
          <span style={bulletStyle}>2</span>
          <span>I will analyze and auto-fill what I can</span>
        </div>
        <div style={tipItemStyle}>
          <span style={bulletStyle}>3</span>
          <span>Review, edit, and approve the filled form</span>
        </div>
      </div>
    </div>
  );
}

export function ChatMessages({
  messages,
  agentStage = 'idle',
  thinkingMessage,
  onApprove,
  onEdit,
  approvingMessageId,
  isLoading = false,
}: ChatMessagesProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const lastMessageRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  const scrollToBottom = useCallback(() => {
    if (shouldAutoScroll.current && lastMessageRef.current) {
      lastMessageRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, []);

  // Auto-scroll when messages change or thinking state changes
  useEffect(() => {
    scrollToBottom();
  }, [messages, agentStage, scrollToBottom]);

  // Detect manual scroll to disable auto-scroll temporarily
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    shouldAutoScroll.current = isNearBottom;
  }, []);

  const containerStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  };

  const hasMessages = messages.length > 0;
  const showThinking = agentStage !== 'idle' && agentStage !== 'complete';

  if (!hasMessages && !showThinking && !isLoading) {
    return (
      <div style={containerStyle} ref={containerRef}>
        <WelcomeMessage />
      </div>
    );
  }

  return (
    <div style={containerStyle} ref={containerRef} onScroll={handleScroll}>
      {messages.map((message) => (
        <ChatMessage
          key={message.id}
          message={message}
          onApprove={onApprove}
          onEdit={onEdit}
          isApproving={approvingMessageId === message.id}
        />
      ))}

      {showThinking && (
        <AgentThinking stage={agentStage} message={thinkingMessage} />
      )}

      {/* Scroll anchor */}
      <div ref={lastMessageRef} style={{ height: '1px' }} />
    </div>
  );
}
