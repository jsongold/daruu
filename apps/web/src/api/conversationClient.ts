/**
 * Type-safe API client for conversation endpoints.
 * Provides functions for chat-based form filling interactions.
 */

import type {
  Conversation,
  ConversationSummary,
  ConversationWithMessages,
  ConversationListResponse,
  MessageListResponse,
  Message,
  CreateConversationRequest,
  SendMessageRequest,
  ApprovePreviewRequest,
  SSEEvent,
  SSEEventType,
  SSEConnectedData,
  SSEThinkingData,
  SSEMessageData,
  SSEPreviewData,
  SSEApprovalData,
  SSEStageChangeData,
  SSEErrorData,
  ApiResponse,
} from '../lib/api-types';

import { apiBaseUrl, ApiError } from './client';

// ============================================================================
// Configuration
// ============================================================================

const API_PREFIX = '/api/v2';

// ============================================================================
// HTTP Client Helper
// ============================================================================

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${apiBaseUrl}${endpoint}`;

  const defaultHeaders: Record<string, string> = {};
  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      try {
        errorBody = await response.text();
      } catch {
        errorBody = null;
      }
    }
    throw ApiError.fromResponse(response.status, errorBody);
  }

  const contentType = response.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return {} as T;
  }

  return response.json();
}

async function requestBlob(endpoint: string): Promise<Blob> {
  const url = `${apiBaseUrl}${endpoint}`;
  const response = await fetch(url);

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      try {
        errorBody = await response.text();
      } catch {
        errorBody = null;
      }
    }
    throw ApiError.fromResponse(response.status, errorBody);
  }

  return response.blob();
}

// ============================================================================
// Conversations API
// ============================================================================

/**
 * Create a new conversation.
 */
export async function createConversation(
  data?: CreateConversationRequest
): Promise<Conversation> {
  const response = await request<ApiResponse<Conversation>>(
    `${API_PREFIX}/conversations`,
    {
      method: 'POST',
      body: JSON.stringify(data ?? {}),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to create conversation',
      'CREATE_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * List all conversations for the current user.
 */
export async function listConversations(
  cursor?: string | null,
  limit?: number
): Promise<ConversationListResponse> {
  const params = new URLSearchParams();
  if (cursor) {
    params.set('cursor', cursor);
  }
  if (limit) {
    params.set('limit', String(limit));
  }

  const queryString = params.toString();
  const endpoint = `${API_PREFIX}/conversations${queryString ? `?${queryString}` : ''}`;

  const response = await request<ApiResponse<ConversationListResponse>>(endpoint);

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to list conversations',
      'LIST_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Get a conversation with its recent messages.
 */
export async function getConversation(
  conversationId: string
): Promise<ConversationWithMessages> {
  const response = await request<ApiResponse<ConversationWithMessages>>(
    `${API_PREFIX}/conversations/${conversationId}`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      'Conversation not found',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

/**
 * Get messages for a conversation with pagination.
 */
export async function getMessages(
  conversationId: string,
  before?: string | null,
  limit?: number
): Promise<MessageListResponse> {
  const params = new URLSearchParams();
  if (before) {
    params.set('before', before);
  }
  if (limit) {
    params.set('limit', String(limit));
  }

  const queryString = params.toString();
  const endpoint = `${API_PREFIX}/conversations/${conversationId}/messages${queryString ? `?${queryString}` : ''}`;

  const response = await request<ApiResponse<MessageListResponse>>(endpoint);

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to get messages',
      'MESSAGE_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Send a text message to a conversation.
 */
export async function sendMessage(
  conversationId: string,
  content: string
): Promise<Message> {
  const body: SendMessageRequest = { content };

  const response = await request<ApiResponse<Message>>(
    `${API_PREFIX}/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to send message',
      'SEND_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Upload files to a conversation as attachments.
 */
export async function uploadFiles(
  conversationId: string,
  files: File[]
): Promise<Message> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await request<ApiResponse<Message>>(
    `${API_PREFIX}/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to upload files',
      'UPLOAD_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Send a message with optional file attachments.
 */
export async function sendMessageWithFiles(
  conversationId: string,
  content: string,
  files?: File[]
): Promise<Message> {
  if (!files || files.length === 0) {
    return sendMessage(conversationId, content);
  }

  const formData = new FormData();
  formData.append('content', content);
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await request<ApiResponse<Message>>(
    `${API_PREFIX}/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to send message',
      'SEND_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Approve a preview and generate the final PDF.
 */
export async function approvePreview(
  conversationId: string,
  messageId: string
): Promise<Message> {
  const body: ApprovePreviewRequest = { message_id: messageId };

  const response = await request<ApiResponse<Message>>(
    `${API_PREFIX}/conversations/${conversationId}/approve`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      'Failed to approve preview',
      'APPROVE_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Download the filled PDF for a completed conversation.
 */
export async function downloadPdf(conversationId: string): Promise<Blob> {
  return requestBlob(`${API_PREFIX}/conversations/${conversationId}/download`);
}

/**
 * Get a preview image URL for a document page.
 */
export function getPreviewUrl(
  conversationId: string,
  documentId: string,
  page: number
): string {
  return `${apiBaseUrl}${API_PREFIX}/conversations/${conversationId}/documents/${documentId}/pages/${page}/preview`;
}

// ============================================================================
// SSE Subscription
// ============================================================================

export type SSEEventHandler = {
  onConnected?: (data: SSEConnectedData) => void;
  onThinking?: (data: SSEThinkingData) => void;
  onMessage?: (data: SSEMessageData) => void;
  onPreview?: (data: SSEPreviewData) => void;
  onApproval?: (data: SSEApprovalData) => void;
  onStageChange?: (data: SSEStageChangeData) => void;
  onError?: (data: SSEErrorData) => void;
  onComplete?: () => void;
  onConnectionError?: (error: Error) => void;
};

/**
 * Subscribe to real-time updates for a conversation.
 * Returns an unsubscribe function.
 */
export function subscribeToUpdates(
  conversationId: string,
  handlers: SSEEventHandler
): () => void {
  const url = `${apiBaseUrl}${API_PREFIX}/conversations/${conversationId}/events`;
  const eventSource = new EventSource(url);

  const handleEvent = (eventType: SSEEventType, data: unknown) => {
    switch (eventType) {
      case 'connected':
        handlers.onConnected?.(data as SSEConnectedData);
        break;
      case 'thinking':
        handlers.onThinking?.(data as SSEThinkingData);
        break;
      case 'message':
        handlers.onMessage?.(data as SSEMessageData);
        break;
      case 'preview':
        handlers.onPreview?.(data as SSEPreviewData);
        break;
      case 'approval':
        handlers.onApproval?.(data as SSEApprovalData);
        break;
      case 'stage_change':
        handlers.onStageChange?.(data as SSEStageChangeData);
        break;
      case 'error':
        handlers.onError?.(data as SSEErrorData);
        break;
      case 'complete':
        handlers.onComplete?.();
        break;
    }
  };

  const messageHandler = (event: MessageEvent) => {
    try {
      const parsed = JSON.parse(event.data) as SSEEvent;
      handleEvent(parsed.event, parsed.data);
    } catch {
      // Ignore parse errors
    }
  };

  // Listen to specific event types
  const eventTypes: SSEEventType[] = [
    'connected',
    'thinking',
    'message',
    'preview',
    'approval',
    'stage_change',
    'error',
    'complete',
  ];

  eventTypes.forEach((eventType) => {
    eventSource.addEventListener(eventType, (event: Event) => {
      const messageEvent = event as MessageEvent;
      try {
        const data = JSON.parse(messageEvent.data);
        handleEvent(eventType, data);
      } catch {
        // Ignore parse errors
      }
    });
  });

  // Also listen to generic message events
  eventSource.addEventListener('message', messageHandler);

  eventSource.onerror = () => {
    handlers.onConnectionError?.(new Error('SSE connection error'));
  };

  return () => {
    eventSource.close();
  };
}

// ============================================================================
// Utility Types
// ============================================================================

export type {
  Conversation,
  ConversationSummary,
  ConversationWithMessages,
  ConversationListResponse,
  MessageListResponse,
  Message,
  CreateConversationRequest,
  SendMessageRequest,
  ApprovePreviewRequest,
  SSEEvent,
  SSEEventType,
  SSEConnectedData,
  SSEThinkingData,
  SSEMessageData,
  SSEPreviewData,
  SSEApprovalData,
  SSEStageChangeData,
  SSEErrorData,
};
