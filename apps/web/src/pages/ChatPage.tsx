/**
 * Main chat page for agent-driven form filling.
 * Combines all chat components into a complete user experience.
 */

import { useState, useCallback, useMemo } from 'react';
import { ChatContainer } from '../components/chat/ChatContainer';
import { DocumentPreview } from '../components/preview/DocumentPreview';
import { useConversation } from '../hooks/useConversation';
import { getPreviewUrl } from '../api/conversationClient';

export interface ChatPageProps {
  /** Initial conversation ID to load (for future use) */
  initialConversationId?: string | null;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ChatPage({ initialConversationId: _initialConversationId }: ChatPageProps) {
  const {
    // Conversation list
    conversations,
    isLoadingConversations,

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
    approvingMessageId,
    error,
    clearError,
  } = useConversation({
    autoLoadList: true,
    useSSE: true,
  });

  // Preview state - reserved for future use with multi-page documents
  const [, setPreviewDocumentId] = useState<string | null>(null);
  const [, setPreviewPageUrls] = useState<string[]>([]);
  const [isPreviewLoading] = useState(false);

  // Determine if we should show the preview panel
  const showPreview = useMemo(() => {
    // Show preview when:
    // 1. There's a form document selected
    // 2. Or when we have a preview ref in a message
    if (activeConversation?.form_document_id) {
      return true;
    }

    // Check if any message has a preview
    const hasPreview = messages.some((m) => m.preview_ref);
    return hasPreview;
  }, [activeConversation, messages]);

  // Handle selecting a conversation
  const handleSelectConversation = useCallback(async (id: string) => {
    await selectConversation(id);
    setPreviewDocumentId(null);
    setPreviewPageUrls([]);
  }, [selectConversation]);

  // Handle creating a new conversation
  const handleNewConversation = useCallback(async () => {
    try {
      await startNewConversation();
      setPreviewDocumentId(null);
      setPreviewPageUrls([]);
    } catch {
      // Error is handled by the hook
    }
  }, [startNewConversation]);

  // Handle sending a message
  const handleSendMessage = useCallback(async (content: string, files?: File[]) => {
    await sendMessage(content, files);
  }, [sendMessage]);

  // Handle approval
  const handleApprove = useCallback(async (messageId: string) => {
    await approve(messageId);
  }, [approve]);

  // Handle edit request (for now, placeholder for future implementation)
  const handleEdit = useCallback((messageId: string) => {
    // This would typically open an edit mode or send an edit request
    // For now, this is a placeholder - messageId will be used in future
    void messageId;
  }, []);

  // Handle PDF download
  const handleDownload = useCallback(async () => {
    const blob = await download();
    if (blob) {
      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = activeConversation?.title
        ? `${activeConversation.title}.pdf`
        : 'filled-form.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }, [download, activeConversation]);

  // Generate preview URLs based on the active conversation
  const previewUrls = useMemo(() => {
    if (!activeConversationId || !activeConversation?.form_document_id) {
      // Check if there's a preview in messages
      const previewMessage = messages.find((m) => m.preview_ref);
      if (previewMessage?.preview_ref) {
        return [previewMessage.preview_ref];
      }
      return [];
    }

    // Generate page preview URLs
    // For now, assume single page - in real implementation, would get page count
    const docId = activeConversation.form_document_id;
    return [getPreviewUrl(activeConversationId, docId, 1)];
  }, [activeConversationId, activeConversation, messages]);

  // Determine if download is available
  const canDownload = useMemo(() => {
    return activeConversation?.status === 'completed' && !!activeConversation.filled_pdf_ref;
  }, [activeConversation]);

  // Preview component
  const previewComponent = (
    <DocumentPreview
      pageUrls={previewUrls}
      isLoading={isPreviewLoading}
      title={activeConversation?.title || 'Document Preview'}
      onDownload={handleDownload}
      canDownload={canDownload}
    />
  );

  return (
    <ChatContainer
      // Sidebar props
      conversations={conversations}
      activeConversationId={activeConversationId}
      onSelectConversation={handleSelectConversation}
      onNewConversation={handleNewConversation}
      isLoadingConversations={isLoadingConversations}
      isCreatingConversation={isCreating}
      // Messages props
      messages={messages}
      agentStage={agentStage}
      thinkingMessage={thinkingMessage ?? undefined}
      isLoadingMessages={isLoadingMessages}
      // Input props
      onSendMessage={handleSendMessage}
      isSending={isSending}
      // Approval props
      onApprove={handleApprove}
      onEdit={handleEdit}
      approvingMessageId={approvingMessageId}
      // Preview props
      previewComponent={previewComponent}
      showPreview={showPreview}
      // Error handling
      error={error}
      onDismissError={clearError}
    />
  );
}
