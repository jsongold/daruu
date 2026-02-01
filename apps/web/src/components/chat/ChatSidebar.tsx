/**
 * Chat sidebar component showing conversation list.
 * Allows creating new conversations and switching between existing ones.
 */

import type { CSSProperties } from 'react';
import type { ConversationSummary, ConversationStatus } from '../../lib/api-types';
import { Button } from '../ui/Button';
import { LoadingSpinner } from '../ui/LoadingState';

export interface ChatSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId?: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  isLoading?: boolean;
  isCreating?: boolean;
}

const statusColors: Record<ConversationStatus, { bg: string; text: string }> = {
  active: { bg: '#dbeafe', text: '#1e40af' },
  completed: { bg: '#d1fae5', text: '#065f46' },
  abandoned: { bg: '#f3f4f6', text: '#6b7280' },
  error: { bg: '#fee2e2', text: '#991b1b' },
};

const statusLabels: Record<ConversationStatus, string> = {
  active: 'Active',
  completed: 'Done',
  abandoned: 'Closed',
  error: 'Error',
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  if (diffDays === 1) {
    return 'Yesterday';
  }
  if (diffDays < 7) {
    return date.toLocaleDateString([], { weekday: 'short' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function ConversationItem({
  conversation,
  isActive,
  onClick,
}: {
  conversation: ConversationSummary;
  isActive: boolean;
  onClick: () => void;
}) {
  const { title, status, last_message_preview, updated_at } = conversation;
  const colors = statusColors[status];

  const itemStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    padding: '12px',
    borderRadius: '8px',
    backgroundColor: isActive ? '#eff6ff' : 'transparent',
    border: isActive ? '1px solid #bfdbfe' : '1px solid transparent',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
  };

  const titleStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 500,
    color: '#1f2937',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1,
  };

  const timeStyle: CSSProperties = {
    fontSize: '11px',
    color: '#9ca3af',
    flexShrink: 0,
  };

  const previewStyle: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const statusStyle: CSSProperties = {
    display: 'inline-block',
    padding: '2px 6px',
    borderRadius: '4px',
    fontSize: '10px',
    fontWeight: 500,
    backgroundColor: colors.bg,
    color: colors.text,
  };

  return (
    <div
      style={itemStyle}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div style={headerStyle}>
        <span style={titleStyle}>{title || 'Untitled conversation'}</span>
        <span style={timeStyle}>{formatDate(updated_at)}</span>
      </div>

      {last_message_preview && (
        <span style={previewStyle}>{last_message_preview}</span>
      )}

      <div>
        <span style={statusStyle}>{statusLabels[status]}</span>
      </div>
    </div>
  );
}

function ConversationGroup({
  title,
  conversations,
  activeId,
  onSelect,
}: {
  title: string;
  conversations: ConversationSummary[];
  activeId?: string | null;
  onSelect: (id: string) => void;
}) {
  if (conversations.length === 0) {
    return null;
  }

  const groupStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  };

  const titleStyle: CSSProperties = {
    fontSize: '11px',
    fontWeight: 600,
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    padding: '8px 12px 4px',
  };

  return (
    <div style={groupStyle}>
      <span style={titleStyle}>{title}</span>
      {conversations.map((conv) => (
        <ConversationItem
          key={conv.id}
          conversation={conv}
          isActive={conv.id === activeId}
          onClick={() => onSelect(conv.id)}
        />
      ))}
    </div>
  );
}

export function ChatSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  isLoading = false,
  isCreating = false,
}: ChatSidebarProps) {
  const sidebarStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    width: '280px',
    height: '100%',
    borderRight: '1px solid #e5e7eb',
    backgroundColor: '#f9fafb',
  };

  const headerStyle: CSSProperties = {
    padding: '16px',
    borderBottom: '1px solid #e5e7eb',
  };

  const listStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  };

  const emptyStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '32px 16px',
    textAlign: 'center',
    color: '#6b7280',
    fontSize: '13px',
  };

  // Group conversations by date
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const grouped = {
    today: [] as ConversationSummary[],
    yesterday: [] as ConversationSummary[],
    thisWeek: [] as ConversationSummary[],
    older: [] as ConversationSummary[],
  };

  conversations.forEach((conv) => {
    const date = new Date(conv.updated_at);
    if (date >= today) {
      grouped.today.push(conv);
    } else if (date >= yesterday) {
      grouped.yesterday.push(conv);
    } else if (date >= weekAgo) {
      grouped.thisWeek.push(conv);
    } else {
      grouped.older.push(conv);
    }
  });

  return (
    <div style={sidebarStyle}>
      <div style={headerStyle}>
        <Button
          variant="primary"
          fullWidth
          onClick={onNewConversation}
          disabled={isCreating}
          loading={isCreating}
          leftIcon={
            !isCreating && (
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            )
          }
        >
          New Chat
        </Button>
      </div>

      <div style={listStyle}>
        {isLoading ? (
          <div style={emptyStyle}>
            <LoadingSpinner size={24} />
            <span style={{ marginTop: '8px' }}>Loading conversations...</span>
          </div>
        ) : conversations.length === 0 ? (
          <div style={emptyStyle}>
            <svg width="32" height="32" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ marginBottom: '8px', opacity: 0.5 }}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <span>No conversations yet</span>
            <span style={{ marginTop: '4px', fontSize: '12px', opacity: 0.8 }}>
              Start a new chat to begin
            </span>
          </div>
        ) : (
          <>
            <ConversationGroup
              title="Today"
              conversations={grouped.today}
              activeId={activeConversationId}
              onSelect={onSelectConversation}
            />
            <ConversationGroup
              title="Yesterday"
              conversations={grouped.yesterday}
              activeId={activeConversationId}
              onSelect={onSelectConversation}
            />
            <ConversationGroup
              title="This Week"
              conversations={grouped.thisWeek}
              activeId={activeConversationId}
              onSelect={onSelectConversation}
            />
            <ConversationGroup
              title="Older"
              conversations={grouped.older}
              activeId={activeConversationId}
              onSelect={onSelectConversation}
            />
          </>
        )}
      </div>
    </div>
  );
}
