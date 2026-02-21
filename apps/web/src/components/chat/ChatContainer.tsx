/**
 * Main chat container component using AI Elements.
 * Layout: Sidebar | Document (Center) | Chat
 * Document view is the main focus in the center.
 *
 * Uses AI Elements: https://github.com/vercel/ai-elements
 */

import type {
  ConversationSummary,
  Message,
  AgentStage,
} from '../../lib/api-types';
import { ChatSidebar } from './ChatSidebar';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { cn } from '@/lib/utils';
import { XCircleIcon } from 'lucide-react';

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
  const inputDisabled = isSending || agentStage === 'analyzing' || agentStage === 'mapping' || agentStage === 'filling';

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Left: Conversation Sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={onSelectConversation}
        onNewConversation={onNewConversation}
        isLoading={isLoadingConversations}
        isCreating={isCreatingConversation}
      />

      {/* Center: Document Preview (main focus) */}
      {showPreview && (
        <div
          className={cn(
            "flex flex-col overflow-hidden bg-card",
            "border-x border-border",
            "flex-[2] min-w-[400px] max-w-[800px]",
            "transition-all duration-300 ease-in-out"
          )}
        >
          {previewComponent}
        </div>
      )}

      {/* Right: Chat Messages & Input */}
      <div
        className={cn(
          "flex flex-1 flex-col overflow-hidden bg-card",
          "min-w-[320px] max-w-[480px]"
        )}
      >
        {/* Error banner */}
        {error && (
          <div className="flex items-center justify-between gap-3 border-b border-destructive/20 bg-destructive/10 px-4 py-3">
            <p className="flex-1 text-sm text-destructive">{error}</p>
            {onDismissError && (
              <button
                onClick={onDismissError}
                className="flex items-center gap-1 rounded-md border border-destructive/20 bg-background px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors"
              >
                <XCircleIcon className="h-3.5 w-3.5" />
                Dismiss
              </button>
            )}
          </div>
        )}

        {/* Messages */}
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

        {/* Input */}
        <ChatInput
          onSend={onSendMessage}
          disabled={inputDisabled}
          loading={isSending}
          placeholder={
            !activeConversationId
              ? 'Upload a PDF to start'
              : isSending
              ? 'Sending...'
              : 'Type a message or drop files here...'
          }
        />
      </div>
    </div>
  );
}

/**
 * Layout variant: Chat | Document | Sidebar
 * Chat on the left, document in center, sidebar on right.
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

  const inputDisabled = rest.isSending ||
    rest.agentStage === 'analyzing' || rest.agentStage === 'mapping' || rest.agentStage === 'filling';

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Left: Chat Messages & Input */}
      <div
        className={cn(
          "flex flex-1 flex-col overflow-hidden bg-card",
          "min-w-[320px] max-w-[480px]",
          "border-r border-border"
        )}
      >
        {/* Error banner */}
        {rest.error && (
          <div className="flex items-center justify-between gap-3 border-b border-destructive/20 bg-destructive/10 px-4 py-3">
            <p className="flex-1 text-sm text-destructive">{rest.error}</p>
            {rest.onDismissError && (
              <button
                onClick={rest.onDismissError}
                className="flex items-center gap-1 rounded-md border border-destructive/20 bg-background px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors"
              >
                <XCircleIcon className="h-3.5 w-3.5" />
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
          loading={rest.isSending}
          placeholder={
            !rest.activeConversationId
              ? 'Upload a PDF to start'
              : rest.isSending
              ? 'Sending...'
              : 'Type a message or drop files here...'
          }
        />
      </div>

      {/* Center: Document Preview (main focus) */}
      {showPreview && (
        <div
          className={cn(
            "flex flex-col overflow-hidden bg-card",
            "flex-[2] min-w-[400px] max-w-[800px]",
            "transition-all duration-300 ease-in-out"
          )}
        >
          {previewComponent}
        </div>
      )}

      {/* Right: Conversation Sidebar */}
      <ChatSidebar
        conversations={rest.conversations}
        activeConversationId={rest.activeConversationId}
        onSelectConversation={rest.onSelectConversation}
        onNewConversation={rest.onNewConversation}
        isLoading={rest.isLoadingConversations}
        isCreating={rest.isCreatingConversation}
      />
    </div>
  );
}
