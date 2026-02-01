/**
 * Main chat page for agent-driven form filling.
 * Combines all chat components into a complete user experience.
 * Phase 3: Added inline editing and field info panel support.
 */

import { useState, useCallback, useMemo, type CSSProperties } from 'react';
import { ChatContainer } from '../components/chat/ChatContainer';
import { EditableDocumentPreview } from '../components/preview/EditableDocumentPreview';
import { FieldInfoPanel, type FieldInfo } from '../components/editor/FieldInfoPanel';
import { useConversation } from '../hooks/useConversation';
import { useEdits } from '../hooks/useEdits';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { getPreviewUrl } from '../api/conversationClient';

export interface ChatPageProps {
  /** Initial conversation ID to load (for future use) */
  initialConversationId?: string | null;
}

/** Parse edit commands from chat messages */
function parseEditCommand(content: string): { fieldName: string; value: string } | null {
  // Match patterns like:
  // - "change [field] to [value]"
  // - "set [field] to [value]"
  // - "update [field] to [value]"
  const patterns = [
    /^(?:change|set|update)\s+(?:the\s+)?["']?([^"']+?)["']?\s+to\s+["']?(.+?)["']?$/i,
    /^(?:change|set|update)\s+["']?([^"']+?)["']?\s*(?:=|:)\s*["']?(.+?)["']?$/i,
  ];

  for (const pattern of patterns) {
    const match = content.trim().match(pattern);
    if (match) {
      return {
        fieldName: match[1].trim(),
        value: match[2].trim(),
      };
    }
  }

  return null;
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
    error: conversationError,
    clearError: clearConversationError,
  } = useConversation({
    autoLoadList: true,
    useSSE: true,
  });

  // Edit state management
  const {
    fieldsArray,
    canUndo,
    canRedo,
    isLoading: isEditLoading,
    error: editError,
    updateField,
    undo,
    redo,
    getField,
    isFieldEdited,
    clearError: clearEditError,
  } = useEdits(activeConversationId, {
    autoLoad: true,
  });

  // UI state
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [showFieldPanel, setShowFieldPanel] = useState(true);
  const [isPreviewLoading] = useState(false);

  // Combine errors
  const error = conversationError || editError;
  const clearError = useCallback(() => {
    clearConversationError();
    clearEditError();
  }, [clearConversationError, clearEditError]);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onUndo: () => {
      if (canUndo) {
        undo();
      }
    },
    onRedo: () => {
      if (canRedo) {
        redo();
      }
    },
    onEscape: () => {
      setSelectedFieldId(null);
    },
  });

  // Determine if we should show the preview panel
  const showPreview = useMemo(() => {
    if (activeConversation?.form_document_id) {
      return true;
    }
    const hasPreview = messages.some((m) => m.preview_ref);
    return hasPreview;
  }, [activeConversation, messages]);

  // Handle selecting a conversation
  const handleSelectConversation = useCallback(async (id: string) => {
    await selectConversation(id);
    setSelectedFieldId(null);
  }, [selectConversation]);

  // Handle creating a new conversation
  const handleNewConversation = useCallback(async () => {
    try {
      await startNewConversation();
      setSelectedFieldId(null);
    } catch {
      // Error is handled by the hook
    }
  }, [startNewConversation]);

  // Handle sending a message - check for edit commands first
  const handleSendMessage = useCallback(async (content: string, files?: File[]) => {
    // Auto-create conversation if none exists
    if (!activeConversationId) {
      try {
        await startNewConversation();
        // After creating, wait for state update then send
        // The sendMessage will be called with the new conversation
      } catch {
        // Error handled by hook
        return;
      }
    }

    // Check if this is an edit command
    const editCommand = parseEditCommand(content);
    if (editCommand && !files?.length) {
      // Find the field by name (case-insensitive)
      const field = fieldsArray.find(
        (f) => f.label.toLowerCase() === editCommand.fieldName.toLowerCase() ||
               f.field_id.toLowerCase() === editCommand.fieldName.toLowerCase()
      );

      if (field) {
        // Execute the edit
        await updateField(field.field_id, editCommand.value, 'chat');
        // Still send the message so the agent knows what happened
        await sendMessage(content, files);
        return;
      }
    }

    // Regular message
    await sendMessage(content, files);
  }, [activeConversationId, startNewConversation, fieldsArray, updateField, sendMessage]);

  // Handle approval
  const handleApprove = useCallback(async (messageId: string) => {
    await approve(messageId);
  }, [approve]);

  // Handle edit request from message (opens field panel)
  const handleEdit = useCallback((messageId: string) => {
    // Show field panel when user wants to edit
    setShowFieldPanel(true);
    void messageId;
  }, []);

  // Handle PDF download
  const handleDownload = useCallback(async () => {
    const blob = await download();
    if (blob) {
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

  // Handle field selection in preview
  const handleFieldSelect = useCallback((fieldId: string | null) => {
    setSelectedFieldId(fieldId);
    if (fieldId) {
      setShowFieldPanel(true);
    }
  }, []);

  // Handle field edit from preview or panel
  const handleFieldEdit = useCallback(async (fieldId: string, value: string) => {
    await updateField(fieldId, value, 'inline');
  }, [updateField]);

  // Handle undo/redo from preview
  const handleUndo = useCallback(() => {
    undo();
  }, [undo]);

  const handleRedo = useCallback(() => {
    redo();
  }, [redo]);

  // Close field panel
  const handleCloseFieldPanel = useCallback(() => {
    setShowFieldPanel(false);
    setSelectedFieldId(null);
  }, []);

  // Generate preview URLs based on the active conversation
  const previewUrls = useMemo(() => {
    if (!activeConversationId || !activeConversation?.form_document_id) {
      const previewMessage = messages.find((m) => m.preview_ref);
      if (previewMessage?.preview_ref) {
        return [previewMessage.preview_ref];
      }
      return [];
    }

    const docId = activeConversation.form_document_id;
    return [getPreviewUrl(activeConversationId, docId, 1)];
  }, [activeConversationId, activeConversation, messages]);

  // Determine if download is available
  const canDownload = useMemo(() => {
    return activeConversation?.status === 'completed' && !!activeConversation.filled_pdf_ref;
  }, [activeConversation]);

  // Get selected field info for panel
  const selectedFieldInfo = useMemo((): FieldInfo | null => {
    if (!selectedFieldId) return null;
    const field = getField(selectedFieldId);
    if (!field) return null;

    return {
      id: field.field_id,
      label: field.label,
      value: field.value,
      type: field.type,
      bbox: field.bbox ? {
        x: field.bbox.x,
        y: field.bbox.y,
        width: field.bbox.width,
        height: field.bbox.height,
        page: field.bbox.page,
      } : null,
      required: field.required,
      validationStatus: field.validation_status,
      validationMessage: field.validation_message,
      isEdited: isFieldEdited(selectedFieldId),
    };
  }, [selectedFieldId, getField, isFieldEdited]);

  // Styles for the layout with field panel
  const previewContainerStyle: CSSProperties = {
    display: 'flex',
    height: '100%',
    overflow: 'hidden',
  };

  const previewWrapperStyle: CSSProperties = {
    flex: 1,
    minWidth: 0,
  };

  // Preview component with editing capabilities
  const previewComponent = (
    <div style={previewContainerStyle}>
      <div style={previewWrapperStyle}>
        <EditableDocumentPreview
          pageUrls={previewUrls}
          fields={fieldsArray}
          selectedFieldId={selectedFieldId}
          isLoading={isPreviewLoading}
          isEditLoading={isEditLoading}
          title={activeConversation?.title || 'Document Preview'}
          onDownload={handleDownload}
          canDownload={canDownload}
          onFieldSelect={handleFieldSelect}
          onFieldEdit={handleFieldEdit}
          enableFieldHighlights={fieldsArray.length > 0}
          showUndoRedo={true}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={handleUndo}
          onRedo={handleRedo}
        />
      </div>

      {/* Field Info Panel */}
      {showFieldPanel && (
        <FieldInfoPanel
          field={selectedFieldInfo}
          onValueChange={handleFieldEdit}
          onClose={handleCloseFieldPanel}
          isLoading={isEditLoading}
          error={editError}
        />
      )}
    </div>
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
