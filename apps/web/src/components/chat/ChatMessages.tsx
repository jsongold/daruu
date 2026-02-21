/**
 * Chat messages list component using AI Elements.
 * Displays the conversation history and thinking indicator.
 *
 * Uses AI Elements: https://github.com/vercel/ai-elements
 */

import type { Message as AppMessage, AgentStage } from '../../lib/api-types';
import { AgentThinking } from './AgentThinking';
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
  Message,
  MessageContent,
  MessageResponse,
  MessageAvatar,
  MessageTimestamp,
  MessageActions,
} from '@/components/ai-elements';
import { CheckIcon, PencilIcon, BotIcon, UserIcon, FileTextIcon, Loader2Icon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ChatMessagesProps {
  messages: AppMessage[];
  agentStage?: AgentStage;
  thinkingMessage?: string;
  onApprove?: (messageId: string) => void;
  onEdit?: (messageId: string) => void;
  approvingMessageId?: string | null;
  isLoading?: boolean;
  onTemplateSelect?: (templateId: string, messageId: string) => void;
  onTemplateSkip?: (messageId: string) => void;
  isMatchingTemplates?: boolean;
}

function WelcomeState() {
  return (
    <ConversationEmptyState
      icon={<FileTextIcon className="h-12 w-12" />}
      title="Welcome to Form Assistant"
      description="Upload your PDF documents and I'll help you fill them out quickly and accurately."
    >
      <div className="mt-4 space-y-3 text-left">
        <div className="flex items-start gap-3 rounded-lg bg-muted/50 p-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            1
          </span>
          <span className="text-sm text-muted-foreground">
            Drop your form PDF and any source documents
          </span>
        </div>
        <div className="flex items-start gap-3 rounded-lg bg-muted/50 p-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            2
          </span>
          <span className="text-sm text-muted-foreground">
            I'll analyze and auto-fill what I can
          </span>
        </div>
        <div className="flex items-start gap-3 rounded-lg bg-muted/50 p-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            3
          </span>
          <span className="text-sm text-muted-foreground">
            Review, edit, and approve the filled form
          </span>
        </div>
      </div>
    </ConversationEmptyState>
  );
}

interface ChatMessageItemProps {
  message: AppMessage;
  onApprove?: (messageId: string) => void;
  onEdit?: (messageId: string) => void;
  isApproving?: boolean;
}

function ChatMessageItem({
  message,
  onApprove,
  onEdit,
  isApproving,
}: ChatMessageItemProps) {
  const isUser = message.role === 'user';
  const isAgent = message.role === 'agent';
  const showApprovalActions = message.approval_required && message.approval_status === 'pending';

  return (
    <Message from={isUser ? 'user' : 'assistant'}>
      {/* Avatar for assistant messages */}
      {isAgent && (
        <div className="flex items-center gap-2">
          <MessageAvatar fallback={<BotIcon className="h-4 w-4" />} />
          <span className="text-xs font-medium text-muted-foreground">Assistant</span>
          <MessageTimestamp date={message.created_at} />
        </div>
      )}

      {/* User avatar and timestamp */}
      {isUser && (
        <div className="flex items-center gap-2 justify-end">
          <MessageTimestamp date={message.created_at} />
          <span className="text-xs font-medium text-muted-foreground">You</span>
          <MessageAvatar fallback={<UserIcon className="h-4 w-4" />} />
        </div>
      )}

      <MessageContent>
        <MessageResponse>{message.content}</MessageResponse>

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.attachments.map((attachment, index) => (
              <div
                key={index}
                className="flex items-center gap-2 rounded-md bg-muted px-3 py-1.5 text-xs"
              >
                <FileTextIcon className="h-3.5 w-3.5" />
                <span>{attachment.filename}</span>
              </div>
            ))}
          </div>
        )}
      </MessageContent>

      {/* Approval actions */}
      {showApprovalActions && (
        <MessageActions className="mt-2">
          <button
            onClick={() => onApprove?.(message.id)}
            disabled={isApproving}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium",
              "bg-primary text-primary-foreground hover:bg-primary/90",
              "disabled:opacity-50 disabled:pointer-events-none",
              "transition-colors"
            )}
          >
            {isApproving ? (
              <Loader2Icon className="h-4 w-4 animate-spin" />
            ) : (
              <CheckIcon className="h-4 w-4" />
            )}
            {isApproving ? 'Approving...' : 'Approve'}
          </button>
          <button
            onClick={() => onEdit?.(message.id)}
            disabled={isApproving}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium",
              "bg-secondary text-secondary-foreground hover:bg-secondary/80",
              "disabled:opacity-50 disabled:pointer-events-none",
              "transition-colors"
            )}
          >
            <PencilIcon className="h-4 w-4" />
            Edit
          </button>
        </MessageActions>
      )}

      {/* Approval status badge */}
      {message.approval_status === 'approved' && (
        <div className="flex items-center gap-1.5 text-xs text-green-600 mt-2">
          <CheckIcon className="h-3.5 w-3.5" />
          <span>Approved</span>
        </div>
      )}
    </Message>
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
  const hasMessages = messages.length > 0;
  const showThinking = agentStage !== 'idle' && agentStage !== 'complete';

  if (!hasMessages && !showThinking && !isLoading) {
    return (
      <Conversation className="flex-1">
        <WelcomeState />
      </Conversation>
    );
  }

  return (
    <Conversation className="flex-1">
      <ConversationContent>
        {messages.map((message) => (
          <ChatMessageItem
            key={message.id}
            message={message}
            onApprove={onApprove}
            onEdit={onEdit}
            isApproving={approvingMessageId === message.id}
          />
        ))}

        {showThinking && (
          <Message from="assistant">
            <div className="flex items-center gap-2">
              <MessageAvatar fallback={<BotIcon className="h-4 w-4" />} />
              <span className="text-xs font-medium text-muted-foreground">Assistant</span>
            </div>
            <MessageContent>
              <AgentThinking stage={agentStage} message={thinkingMessage} />
            </MessageContent>
          </Message>
        )}
      </ConversationContent>

      <ConversationScrollButton />
    </Conversation>
  );
}
