/**
 * Custom hook for conversation state management.
 * Handles messages, SSE updates, and conversation lifecycle.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  Conversation,
  ConversationSummary,
  Message,
  AgentStage,
} from '../lib/api-types';
import {
  createConversation,
  listConversations,
  getConversation,
  sendMessageWithFiles,
  approvePreview,
  downloadPdf,
  subscribeToUpdates,
  type SSEEventHandler,
} from '../api/conversationClient';
import { ApiError } from '../api/client';

export interface UseConversationOptions {
  /** Whether to auto-load conversation list on mount */
  autoLoadList?: boolean;
  /** Whether to use SSE for real-time updates */
  useSSE?: boolean;
}

export interface UseConversationReturn {
  // Conversation list
  conversations: ConversationSummary[];
  isLoadingConversations: boolean;
  refreshConversations: () => Promise<void>;

  // Active conversation
  activeConversation: Conversation | null;
  activeConversationId: string | null;
  messages: Message[];
  isLoadingMessages: boolean;

  // Agent state
  agentStage: AgentStage;
  thinkingMessage: string | null;

  // Actions
  selectConversation: (id: string) => Promise<void>;
  startNewConversation: () => Promise<string>;
  sendMessage: (content: string, files?: File[], conversationId?: string) => Promise<void>;
  approve: (messageId: string) => Promise<void>;
  download: () => Promise<Blob | null>;

  // State
  isCreating: boolean;
  isSending: boolean;
  isApproving: boolean;
  approvingMessageId: string | null;
  error: string | null;
  clearError: () => void;
}

export function useConversation(
  options: UseConversationOptions = {}
): UseConversationReturn {
  const { autoLoadList = true, useSSE = true } = options;

  // Conversation list state
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);

  // Active conversation state
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // Agent state
  const [agentStage, setAgentStage] = useState<AgentStage>('idle');
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null);

  // Action states
  const [isCreating, setIsCreating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [approvingMessageId, setApprovingMessageId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // SSE cleanup ref
  const sseCleanupRef = useRef<(() => void) | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Load conversation list
  const refreshConversations = useCallback(async () => {
    setIsLoadingConversations(true);
    setError(null);

    try {
      const response = await listConversations();
      setConversations(response.items);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load conversations';
      setError(message);
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  // Select and load a conversation
  const selectConversation = useCallback(async (id: string) => {
    // Clean up previous SSE connection
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
      sseCleanupRef.current = null;
    }

    setActiveConversationId(id);
    setIsLoadingMessages(true);
    setError(null);
    setAgentStage('idle');
    setThinkingMessage(null);

    try {
      const response = await getConversation(id);
      setActiveConversation(response.conversation);
      setMessages(response.messages);

      // Set up SSE if enabled
      if (useSSE) {
        const handlers: SSEEventHandler = {
          onThinking: (data) => {
            setAgentStage(data.stage);
            setThinkingMessage(data.message);
          },
          onMessage: (data) => {
            setMessages((prev) => {
              // Check if message already exists
              const exists = prev.some((m) => m.id === data.id);
              if (exists) {
                return prev;
              }
              return [
                ...prev,
                {
                  id: data.id,
                  role: data.role,
                  content: data.content,
                  attachments: [],
                  metadata: {},
                  approval_required: false,
                  created_at: new Date().toISOString(),
                },
              ];
            });
          },
          onPreview: (data) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === data.message_id
                  ? { ...m, preview_ref: data.preview_ref }
                  : m
              )
            );
          },
          onApproval: (data) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === data.message_id
                  ? { ...m, approval_required: true, approval_status: 'pending' }
                  : m
              )
            );
          },
          onStageChange: (data) => {
            setAgentStage(data.new_stage);
            if (data.new_stage === 'idle' || data.new_stage === 'complete') {
              setThinkingMessage(null);
            }
          },
          onError: (data) => {
            setError(data.message);
            setAgentStage('error');
          },
          onComplete: () => {
            setAgentStage('complete');
            setThinkingMessage(null);
          },
          onConnectionError: () => {
            // SSE connection errors are not critical - the basic flow works without SSE
            // Only log to console, don't show to user
            console.debug('SSE connection closed');
          },
        };

        sseCleanupRef.current = subscribeToUpdates(id, handlers);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load conversation';
      setError(message);
      setActiveConversation(null);
      setMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [useSSE]);

  // Start a new conversation
  const startNewConversation = useCallback(async (): Promise<string> => {
    setIsCreating(true);
    setError(null);

    try {
      const conversation = await createConversation();

      // Refresh the list to include the new conversation
      await refreshConversations();

      // Select the new conversation
      await selectConversation(conversation.id);

      return conversation.id;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to create conversation';
      setError(message);
      throw err;
    } finally {
      setIsCreating(false);
    }
  }, [refreshConversations, selectConversation]);

  // Send a message
  // optionalConversationId allows bypassing the race condition when creating + sending
  const sendMessage = useCallback(async (content: string, files?: File[], optionalConversationId?: string) => {
    const conversationId = optionalConversationId || activeConversationId;
    if (!conversationId) {
      setError('No active conversation');
      return;
    }

    setIsSending(true);
    setError(null);

    try {
      const message = await sendMessageWithFiles(conversationId, content, files);

      // Add the user message to the list immediately
      setMessages((prev) => {
        const exists = prev.some((m) => m.id === message.id);
        if (exists) {
          return prev;
        }
        return [...prev, message];
      });

      // The agent response will come through SSE
      setAgentStage('analyzing');
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to send message';
      setError(message);
    } finally {
      setIsSending(false);
    }
  }, [activeConversationId]);

  // Approve a preview
  const approve = useCallback(async (messageId: string) => {
    if (!activeConversationId) {
      setError('No active conversation');
      return;
    }

    setIsApproving(true);
    setApprovingMessageId(messageId);
    setError(null);

    try {
      const message = await approvePreview(activeConversationId, messageId);

      // Update the message with approval status
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, approval_status: 'approved' }
            : m
        )
      );

      // Add the approval confirmation message
      setMessages((prev) => {
        const exists = prev.some((m) => m.id === message.id);
        if (exists) {
          return prev;
        }
        return [...prev, message];
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to approve';
      setError(message);
    } finally {
      setIsApproving(false);
      setApprovingMessageId(null);
    }
  }, [activeConversationId]);

  // Download the filled PDF
  const download = useCallback(async (): Promise<Blob | null> => {
    if (!activeConversationId) {
      setError('No active conversation');
      return null;
    }

    try {
      const blob = await downloadPdf(activeConversationId);
      return blob;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to download';
      setError(message);
      return null;
    }
  }, [activeConversationId]);

  // Auto-load conversation list on mount
  useEffect(() => {
    if (autoLoadList) {
      refreshConversations();
    }
  }, [autoLoadList, refreshConversations]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, []);

  return {
    // Conversation list
    conversations,
    isLoadingConversations,
    refreshConversations,

    // Active conversation
    activeConversation,
    activeConversationId,
    messages,
    isLoadingMessages,

    // Agent state
    agentStage,
    thinkingMessage,

    // Actions
    selectConversation,
    startNewConversation,
    sendMessage,
    approve,
    download,

    // State
    isCreating,
    isSending,
    isApproving,
    approvingMessageId,
    error,
    clearError,
  };
}
