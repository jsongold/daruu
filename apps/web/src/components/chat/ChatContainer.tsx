/**
 * Main chat container component.
 * Combines sidebar, message list, input, and preview into a unified layout.
 */

import type { CSSProperties } from 'react';
import type {
  ConversationSummary,
  Message,
  AgentStage,
} from '../../lib/api-types';
import { ChatSidebar } from './ChatSidebar';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';

export interface ChatContainerProps {
  // Sidebar props
  conversations: ConversationSummary[];
  activeConversationId?: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  isLoadingConversations?: boolean;
  isCreatingConversation?: boolean;

  // Messages props
  messages: Message[];
  agentStage?: AgentStage;
  thinkingMessage?: string;
  isLoadingMessages?: boolean;

  // Input props
  onSendMessage: (content: string, files?: File[]) => void;
  isSending?: boolean;

  // Approval props
  onApprove?: (messageId: string) => void;
  onEdit?: (messageId: string) => void;
  approvingMessageId?: string | null;

  // Template selection props
  onTemplateSelect?: (templateId: string, messageId: string) => void;
  onTemplateSkip?: (messageId: string) => void;
  isMatchingTemplates?: boolean;

  // Preview props
  previewComponent?: React.ReactNode;
  showPreview?: boolean;

  // Error handling
  error?: string | null;
  onDismissError?: () => void;
}

export function ChatContainer({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  isLoadingConversations = false,
  isCreatingConversation = false,
  messages,
  agentStage = 'idle',
  thinkingMessage,
  isLoadingMessages = false,
  onSendMessage,
  isSending = false,
  onApprove,
  onEdit,
  approvingMessageId,
  onTemplateSelect,
  onTemplateSkip,
  isMatchingTemplates = false,
  previewComponent,
  showPreview = false,
  error,
  onDismissError,
}: ChatContainerProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    height: '100vh',
    width: '100%',
    overflow: 'hidden',
  };

  const mainStyle: CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'row',
    overflow: 'hidden',
  };

  const chatPanelStyle: CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
    borderRight: showPreview ? '1px solid #e5e7eb' : 'none',
  };

  const previewPanelStyle: CSSProperties = {
    width: showPreview ? '45%' : '0',
    maxWidth: '600px',
    overflow: 'hidden',
    transition: 'width 0.3s ease',
    backgroundColor: '#f9fafb',
    display: 'flex',
    flexDirection: 'column',
  };

  const errorBannerStyle: CSSProperties = {
    padding: '12px 16px',
    backgroundColor: '#fee2e2',
    borderBottom: '1px solid #fecaca',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
  };

  const errorTextStyle: CSSProperties = {
    color: '#991b1b',
    fontSize: '14px',
    flex: 1,
  };

  const dismissButtonStyle: CSSProperties = {
    padding: '4px 8px',
    fontSize: '12px',
    backgroundColor: 'white',
    color: '#991b1b',
    border: '1px solid #fecaca',
    borderRadius: '4px',
    cursor: 'pointer',
  };

  const inputDisabled = isSending || !activeConversationId || agentStage === 'analyzing' || agentStage === 'mapping' || agentStage === 'filling';

  return (
    <div style={containerStyle}>
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={onSelectConversation}
        onNewConversation={onNewConversation}
        isLoading={isLoadingConversations}
        isCreating={isCreatingConversation}
      />

      <div style={mainStyle}>
        <div style={chatPanelStyle}>
          {error && (
            <div style={errorBannerStyle}>
              <span style={errorTextStyle}>{error}</span>
              {onDismissError && (
                <button style={dismissButtonStyle} onClick={onDismissError}>
                  Dismiss
                </button>
              )}
            </div>
          )}

          <ChatMessages
            messages={messages}
            agentStage={agentStage}
            thinkingMessage={thinkingMessage}
            onApprove={onApprove}
            onEdit={onEdit}
            approvingMessageId={approvingMessageId}
            isLoading={isLoadingMessages}
            onTemplateSelect={onTemplateSelect}
            onTemplateSkip={onTemplateSkip}
            isMatchingTemplates={isMatchingTemplates}
          />

          <ChatInput
            onSend={onSendMessage}
            disabled={inputDisabled}
            placeholder={
              !activeConversationId
                ? 'Start a new conversation to begin'
                : isSending
                ? 'Sending...'
                : 'Type a message or drop files here...'
            }
          />
        </div>

        {showPreview && (
          <div style={previewPanelStyle}>
            {previewComponent}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Layout variant with preview on the left instead of right.
 */
export function ChatContainerReversed(props: ChatContainerProps) {
  const {
    showPreview,
    previewComponent,
    onTemplateSelect,
    onTemplateSkip,
    isMatchingTemplates = false,
    ...rest
  } = props;

  const containerStyle: CSSProperties = {
    display: 'flex',
    height: '100vh',
    width: '100%',
    overflow: 'hidden',
  };

  const mainStyle: CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'row',
    overflow: 'hidden',
  };

  const previewPanelStyle: CSSProperties = {
    width: showPreview ? '45%' : '0',
    maxWidth: '600px',
    overflow: 'hidden',
    transition: 'width 0.3s ease',
    backgroundColor: '#f9fafb',
    borderRight: showPreview ? '1px solid #e5e7eb' : 'none',
    display: 'flex',
    flexDirection: 'column',
  };

  const chatPanelStyle: CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  };

  const inputDisabled = rest.isSending || !rest.activeConversationId ||
    rest.agentStage === 'analyzing' || rest.agentStage === 'mapping' || rest.agentStage === 'filling';

  return (
    <div style={containerStyle}>
      <ChatSidebar
        conversations={rest.conversations}
        activeConversationId={rest.activeConversationId}
        onSelectConversation={rest.onSelectConversation}
        onNewConversation={rest.onNewConversation}
        isLoading={rest.isLoadingConversations}
        isCreating={rest.isCreatingConversation}
      />

      <div style={mainStyle}>
        {showPreview && (
          <div style={previewPanelStyle}>
            {previewComponent}
          </div>
        )}

        <div style={chatPanelStyle}>
          {rest.error && (
            <div style={{
              padding: '12px 16px',
              backgroundColor: '#fee2e2',
              borderBottom: '1px solid #fecaca',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
            }}>
              <span style={{ color: '#991b1b', fontSize: '14px', flex: 1 }}>{rest.error}</span>
              {rest.onDismissError && (
                <button
                  style={{
                    padding: '4px 8px',
                    fontSize: '12px',
                    backgroundColor: 'white',
                    color: '#991b1b',
                    border: '1px solid #fecaca',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                  onClick={rest.onDismissError}
                >
                  Dismiss
                </button>
              )}
            </div>
          )}

          <ChatMessages
            messages={rest.messages}
            agentStage={rest.agentStage}
            thinkingMessage={rest.thinkingMessage}
            onApprove={rest.onApprove}
            onEdit={rest.onEdit}
            approvingMessageId={rest.approvingMessageId}
            isLoading={rest.isLoadingMessages}
            onTemplateSelect={onTemplateSelect}
            onTemplateSkip={onTemplateSkip}
            isMatchingTemplates={isMatchingTemplates}
          />

          <ChatInput
            onSend={rest.onSendMessage}
            disabled={inputDisabled}
            placeholder={
              !rest.activeConversationId
                ? 'Start a new conversation to begin'
                : rest.isSending
                ? 'Sending...'
                : 'Type a message or drop files here...'
            }
          />
        </div>
      </div>
    </div>
  );
}
