/**
 * Custom hook using Vercel AI SDK's useChat for agent-driven form filling.
 * Adapts the useChat interface to work with our FastAPI backend.
 *
 * Based on PRD: docs/prd/agent-chat-ui.md
 * Uses: Vercel AI SDK v2.x (ai package)
 */

import { useChat, type Message as AIMessage } from 'ai/react';
import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import type {
  Conversation,
  ConversationSummary,
  Message,
  AgentStage,
  MessageRole,
} from '../lib/api-types';
import {
  createConversation,
  listConversations,
  getConversation,
  approvePreview,
  downloadPdf,
  subscribeToUpdates,
  type SSEEventHandler,
} from '../api/conversationClient';
import { apiBaseUrl, ApiError } from '../api/client';

const API_PREFIX = '/api/v2';

export interface UseAgentChatOptions {
  /** Whether to auto-load conversation list on mount */
  autoLoadList?: boolean;
  /** Whether to use SSE for real-time updates */
  useSSE?: boolean;
  /** Initial conversation ID to load */
  initialConversationId?: string | null;
}

export interface UseAgentChatReturn {
  // From Vercel AI SDK useChat
  input: string;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement> | React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleSubmit: (e?: React.FormEvent<HTMLFormElement>) => void;
  isLoading: boolean;

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
  sendMessageWithFiles: (content: string, files?: File[]) => Promise<void>;
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

/**
 * Convert Vercel AI SDK message to our Message format
 */
function aiMessageToMessage(aiMsg: AIMessage): Message {
  return {
    id: aiMsg.id,
    role: (aiMsg.role === 'assistant' ? 'agent' : aiMsg.role) as MessageRole,
    content: aiMsg.content,
    thinking: null,
    preview_ref: null,
    approval_required: false,
    approval_status: null,
    attachments: [],
    metadata: {},
    created_at: aiMsg.createdAt?.toISOString() ?? new Date().toISOString(),
  };
}

/**
 * Custom hook for agent chat using Vercel AI SDK.
 */
export function useAgentChat(
  options: UseAgentChatOptions = {}
): UseAgentChatReturn {
  const { autoLoadList = true, useSSE = true, initialConversationId } = options;

  // Conversation state
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    initialConversationId ?? null
  );
  const [backendMessages, setBackendMessages] = useState<Message[]>([]);
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

  // Vercel AI SDK useChat for input management and potential streaming
  // We use this mainly for the input state management and form handling
  const {
    messages: aiMessages,
    input,
    setInput,
    handleInputChange,
    handleSubmit: aiHandleSubmit,
    isLoading: aiIsLoading,
    setMessages: setAiMessages,
  } = useChat({
    // Use a dummy endpoint - we'll override the actual sending
    api: '/api/chat',
    id: activeConversationId ?? 'default',
    onError: (err: Error) => {
      // Only set error if it's not a network error to our dummy endpoint
      if (!err.message.includes('/api/chat')) {
        setError(err.message);
      }
    },
    onFinish: () => {
      setAgentStage('idle');
      setThinkingMessage(null);
    },
  });

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
      setBackendMessages(response.messages);

      // Clear AI messages and sync with backend
      setAiMessages([]);

      // Set up SSE if enabled
      if (useSSE) {
        const handlers: SSEEventHandler = {
          onThinking: (data) => {
            setAgentStage(data.stage);
            setThinkingMessage(data.message);
          },
          onMessage: (data) => {
            setBackendMessages((prev) => {
              const exists = prev.some((m) => m.id === data.id);
              if (exists) return prev;
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
            setBackendMessages((prev) =>
              prev.map((m) =>
                m.id === data.message_id
                  ? { ...m, preview_ref: data.preview_ref }
                  : m
              )
            );
          },
          onApproval: (data) => {
            setBackendMessages((prev) =>
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
            console.debug('SSE connection closed');
          },
        };

        sseCleanupRef.current = subscribeToUpdates(id, handlers);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load conversation';
      setError(message);
      setActiveConversation(null);
      setBackendMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [useSSE, setAiMessages]);

  // Start a new conversation
  const startNewConversation = useCallback(async (): Promise<string> => {
    setIsCreating(true);
    setError(null);

    try {
      const conversation = await createConversation();
      await refreshConversations();
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

  // Send a message with optional files (uses our API directly)
  const sendMessageWithFiles = useCallback(async (content: string, files?: File[]) => {
    let conversationId = activeConversationId;

    // Auto-create conversation if none exists
    if (!conversationId) {
      try {
        conversationId = await startNewConversation();
      } catch {
        return;
      }
    }

    setIsSending(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('content', content);
      files?.forEach((file) => {
        formData.append('files', file);
      });

      const response = await fetch(
        `${apiBaseUrl}${API_PREFIX}/conversations/${conversationId}/messages`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({})) as { error?: { message?: string } };
        throw new Error(errorData.error?.message ?? 'Failed to send message');
      }

      const message = await response.json() as Message;

      // Add user message to the list
      setBackendMessages((prev) => {
        const exists = prev.some((m) => m.id === message.id);
        if (exists) return prev;
        return [...prev, message];
      });

      // Clear the input
      setInput('');
      setAgentStage('analyzing');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to send message';
      setError(msg);
    } finally {
      setIsSending(false);
    }
  }, [activeConversationId, startNewConversation, setInput]);

  // Custom handleSubmit that uses our API
  const handleSubmit = useCallback((e?: React.FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    if (!input.trim()) return;
    sendMessageWithFiles(input);
  }, [input, sendMessageWithFiles]);

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

      setBackendMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, approval_status: 'approved' } : m
        )
      );

      setBackendMessages((prev) => {
        const exists = prev.some((m) => m.id === message.id);
        if (exists) return prev;
        return [...prev, message];
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to approve';
      setError(msg);
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
      const msg = err instanceof ApiError ? err.message : 'Failed to download';
      setError(msg);
      return null;
    }
  }, [activeConversationId]);

  // Combine AI SDK messages with backend messages
  const messages = useMemo(() => {
    // Use backend messages as the source of truth
    // AI SDK messages are just for the current typing session
    const aiMsgsConverted = aiMessages.map(aiMessageToMessage);

    // Merge, preferring backend messages
    const msgMap = new Map<string, Message>();
    backendMessages.forEach((m) => msgMap.set(m.id, m));
    aiMsgsConverted.forEach((m) => {
      if (!msgMap.has(m.id)) {
        msgMap.set(m.id, m);
      }
    });

    return Array.from(msgMap.values()).sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );
  }, [aiMessages, backendMessages]);

  // Auto-load conversation list on mount
  useEffect(() => {
    if (autoLoadList) {
      refreshConversations();
    }
  }, [autoLoadList, refreshConversations]);

  // Load initial conversation if provided
  useEffect(() => {
    if (initialConversationId && !activeConversation) {
      selectConversation(initialConversationId);
    }
  }, [initialConversationId, activeConversation, selectConversation]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, []);

  // Suppress unused variable warning for aiHandleSubmit
  void aiHandleSubmit;

  return {
    // From Vercel AI SDK
    input,
    setInput,
    handleInputChange,
    handleSubmit,
    isLoading: aiIsLoading || isSending,

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
    sendMessageWithFiles,
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
