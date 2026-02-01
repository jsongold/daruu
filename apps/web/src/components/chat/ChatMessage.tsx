/**
 * Single chat message component.
 * Renders user, agent, or system messages with appropriate styling.
 * Supports inline rendering of template picker for ask_user_input pattern.
 */

import type { CSSProperties } from 'react';
import type { Message, MessageRole, ApprovalStatus, TemplateMatch } from '../../lib/api-types';
import { Button } from '../ui/Button';
import { TemplatePicker } from '../template/TemplatePicker';

export interface ChatMessageProps {
  message: Message;
  onApprove?: (messageId: string) => void;
  onEdit?: (messageId: string) => void;
  isApproving?: boolean;
  /** Handler for template selection (for ask_user_input messages) */
  onTemplateSelect?: (templateId: string, messageId: string) => void;
  /** Handler for skipping template selection */
  onTemplateSkip?: (messageId: string) => void;
  /** Whether template matching is in progress */
  isMatchingTemplates?: boolean;
}

const roleStyles: Record<MessageRole, CSSProperties> = {
  user: {
    alignSelf: 'flex-end',
    backgroundColor: '#3b82f6',
    color: 'white',
    borderRadius: '16px 16px 4px 16px',
  },
  agent: {
    alignSelf: 'flex-start',
    backgroundColor: '#f3f4f6',
    color: '#1f2937',
    borderRadius: '16px 16px 16px 4px',
  },
  system: {
    alignSelf: 'center',
    backgroundColor: '#fef3c7',
    color: '#92400e',
    borderRadius: '8px',
    fontSize: '13px',
    fontStyle: 'italic',
  },
};

const roleLabels: Record<MessageRole, string> = {
  user: 'You',
  agent: 'Assistant',
  system: 'System',
};

function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function AttachmentList({ attachments }: { attachments: Message['attachments'] }) {
  if (!attachments || attachments.length === 0) {
    return null;
  }

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    marginTop: '8px',
  };

  const attachmentStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 10px',
    backgroundColor: 'rgba(0, 0, 0, 0.1)',
    borderRadius: '6px',
    fontSize: '12px',
  };

  const iconStyle: CSSProperties = {
    width: '14px',
    height: '14px',
  };

  return (
    <div style={containerStyle}>
      {attachments.map((attachment) => (
        <div key={attachment.id} style={attachmentStyle}>
          <svg style={iconStyle} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
            />
          </svg>
          <span>{attachment.filename}</span>
        </div>
      ))}
    </div>
  );
}

function ApprovalStatusBadge({ status }: { status: ApprovalStatus }) {
  const badgeStyles: Record<ApprovalStatus, CSSProperties> = {
    pending: {
      backgroundColor: '#fef3c7',
      color: '#92400e',
    },
    approved: {
      backgroundColor: '#d1fae5',
      color: '#065f46',
    },
    rejected: {
      backgroundColor: '#fee2e2',
      color: '#991b1b',
    },
    edited: {
      backgroundColor: '#dbeafe',
      color: '#1e40af',
    },
  };

  const labels: Record<ApprovalStatus, string> = {
    pending: 'Pending approval',
    approved: 'Approved',
    rejected: 'Rejected',
    edited: 'Edited',
  };

  const style: CSSProperties = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 500,
    ...badgeStyles[status],
  };

  return <span style={style}>{labels[status]}</span>;
}

function PreviewImage({ previewRef }: { previewRef: string }) {
  const containerStyle: CSSProperties = {
    marginTop: '12px',
    borderRadius: '8px',
    overflow: 'hidden',
    border: '1px solid #e5e7eb',
  };

  const imageStyle: CSSProperties = {
    width: '100%',
    maxWidth: '300px',
    height: 'auto',
    display: 'block',
  };

  return (
    <div style={containerStyle}>
      <img src={previewRef} alt="Preview" style={imageStyle} />
    </div>
  );
}

function ApprovalActions({
  messageId,
  onApprove,
  onEdit,
  isApproving,
}: {
  messageId: string;
  onApprove?: (messageId: string) => void;
  onEdit?: (messageId: string) => void;
  isApproving?: boolean;
}) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    gap: '8px',
    marginTop: '12px',
  };

  return (
    <div style={containerStyle}>
      <Button
        variant="primary"
        size="sm"
        onClick={() => onApprove?.(messageId)}
        loading={isApproving}
        disabled={isApproving}
      >
        Approve
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => onEdit?.(messageId)}
        disabled={isApproving}
      >
        Edit
      </Button>
    </div>
  );
}

/**
 * Check if message metadata contains template selection data.
 */
function hasTemplateSelection(metadata: Record<string, unknown>): boolean {
  return metadata?.type === 'template_selection' && Array.isArray(metadata?.matches);
}

/**
 * Get template matches from message metadata.
 */
function getTemplateMatches(metadata: Record<string, unknown>): TemplateMatch[] {
  if (!hasTemplateSelection(metadata)) {
    return [];
  }
  return metadata.matches as TemplateMatch[];
}

/**
 * Check if template selection has been completed (user selected or skipped).
 */
function isTemplateSelectionCompleted(metadata: Record<string, unknown>): boolean {
  return metadata?.selection_completed === true;
}

export function ChatMessage({
  message,
  onApprove,
  onEdit,
  isApproving,
  onTemplateSelect,
  onTemplateSkip,
  isMatchingTemplates = false,
}: ChatMessageProps) {
  const { role, content, attachments, thinking, preview_ref, approval_required, approval_status, created_at, metadata } = message;

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    maxWidth: role === 'system' ? '90%' : '75%',
    ...roleStyles[role],
    padding: '12px 16px',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '4px',
    fontSize: '11px',
    opacity: 0.8,
  };

  const contentStyle: CSSProperties = {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    lineHeight: 1.5,
  };

  const thinkingStyle: CSSProperties = {
    marginTop: '8px',
    padding: '8px 12px',
    backgroundColor: 'rgba(0, 0, 0, 0.05)',
    borderRadius: '6px',
    fontSize: '12px',
    fontStyle: 'italic',
    color: 'inherit',
    opacity: 0.8,
  };

  const showApprovalActions =
    approval_required &&
    (!approval_status || approval_status === 'pending') &&
    (onApprove || onEdit);

  // Check for template selection
  const templateMatches = getTemplateMatches(metadata);
  const showTemplatePicker =
    hasTemplateSelection(metadata) &&
    !isTemplateSelectionCompleted(metadata) &&
    (onTemplateSelect || onTemplateSkip);

  const templatePickerContainerStyle: CSSProperties = {
    marginTop: '12px',
    marginLeft: '-16px',
    marginRight: '-16px',
    marginBottom: '-12px',
    borderTop: '1px solid rgba(0, 0, 0, 0.1)',
    paddingTop: '12px',
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span>{roleLabels[role]}</span>
        <span>{formatTime(created_at)}</span>
      </div>

      <div style={contentStyle}>{content}</div>

      <AttachmentList attachments={attachments} />

      {thinking && (
        <div style={thinkingStyle}>
          <strong>Thinking:</strong> {thinking}
        </div>
      )}

      {preview_ref && <PreviewImage previewRef={preview_ref} />}

      {showTemplatePicker && (
        <div style={templatePickerContainerStyle}>
          <TemplatePicker
            matches={templateMatches}
            isLoading={isMatchingTemplates}
            onSelect={(templateId) => onTemplateSelect?.(templateId, message.id)}
            onSkip={() => onTemplateSkip?.(message.id)}
          />
        </div>
      )}

      {approval_status && approval_status !== 'pending' && (
        <div style={{ marginTop: '8px' }}>
          <ApprovalStatusBadge status={approval_status} />
        </div>
      )}

      {showApprovalActions && (
        <ApprovalActions
          messageId={message.id}
          onApprove={onApprove}
          onEdit={onEdit}
          isApproving={isApproving}
        />
      )}
    </div>
  );
}
