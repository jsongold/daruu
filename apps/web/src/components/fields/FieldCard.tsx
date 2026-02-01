/**
 * Individual field card with editing capabilities.
 */

import { useState, useCallback, type CSSProperties } from 'react';
import type { Field, Issue } from '../../types/api';
import { ConfidenceBadge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { getConfidenceColor, getSeverityColor } from '../../utils/format';

export interface FieldCardProps {
  field: Field;
  issues?: Issue[];
  onEdit?: (fieldId: string, value: string) => void;
  onClick?: (field: Field) => void;
  isSelected?: boolean;
  showEvidence?: boolean;
  onShowEvidence?: (fieldId: string) => void;
  /** Pending edited value (not yet submitted) */
  pendingValue?: string;
}

export function FieldCard({
  field,
  issues = [],
  onEdit,
  onClick,
  isSelected = false,
  showEvidence = true,
  onShowEvidence,
  pendingValue,
}: FieldCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  // Use pending value if available, otherwise field value
  const effectiveValue = pendingValue ?? field.value ?? '';
  const [editValue, setEditValue] = useState(effectiveValue);
  const hasPendingEdit = pendingValue !== undefined;

  const handleStartEdit = useCallback(() => {
    setEditValue(effectiveValue);
    setIsEditing(true);
  }, [effectiveValue]);

  const handleSave = useCallback(() => {
    if (onEdit) {
      onEdit(field.id, editValue);
    }
    setIsEditing(false);
  }, [field.id, editValue, onEdit]);

  const handleCancel = useCallback(() => {
    setEditValue(effectiveValue);
    setIsEditing(false);
  }, [effectiveValue]);

  const hasIssues = issues.length > 0;
  const hasLowConfidence = field.confidence !== null && field.confidence < 0.7;
  const isMissing = !effectiveValue;

  const cardStyles: CSSProperties = {
    padding: '16px',
    borderRadius: '8px',
    border: `1px solid ${isSelected ? '#3b82f6' : hasIssues ? '#fecaca' : '#e5e7eb'}`,
    backgroundColor: isSelected ? '#eff6ff' : hasIssues ? '#fef2f2' : 'white',
    cursor: onClick ? 'pointer' : 'default',
    transition: 'all 0.15s ease',
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '12px',
    marginBottom: '12px',
  };

  const nameStyles: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#111827',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  const typeStyles: CSSProperties = {
    fontSize: '11px',
    fontWeight: 500,
    color: '#6b7280',
    backgroundColor: '#f3f4f6',
    padding: '2px 6px',
    borderRadius: '4px',
    textTransform: 'uppercase',
  };

  const requiredStyles: CSSProperties = {
    fontSize: '10px',
    fontWeight: 600,
    color: '#dc2626',
  };

  const valueStyles: CSSProperties = {
    fontSize: '14px',
    color: isMissing ? '#9ca3af' : '#374151',
    fontStyle: isMissing ? 'italic' : 'normal',
    padding: '8px 12px',
    backgroundColor: '#f9fafb',
    borderRadius: '6px',
    border: '1px solid #e5e7eb',
    minHeight: '40px',
    display: 'flex',
    alignItems: 'center',
  };

  const editContainerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  };

  const inputStyles: CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    outline: 'none',
  };

  const metaStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginTop: '12px',
    fontSize: '12px',
    color: '#6b7280',
  };

  const issueStyles: CSSProperties = {
    marginTop: '12px',
    padding: '8px 12px',
    borderRadius: '6px',
    fontSize: '13px',
  };

  return (
    <div
      style={cardStyles}
      onClick={onClick ? () => onClick(field) : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div style={headerStyles}>
        <div style={nameStyles}>
          <span>{field.name}</span>
          <span style={typeStyles}>{field.field_type}</span>
          {field.is_required && <span style={requiredStyles}>Required</span>}
        </div>
        <ConfidenceBadge confidence={field.confidence} size="sm" />
      </div>

      {isEditing ? (
        <div style={editContainerStyles} onClick={(e) => e.stopPropagation()}>
          <input
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            style={inputStyles}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave();
              if (e.key === 'Escape') handleCancel();
            }}
          />
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <Button variant="ghost" size="sm" onClick={handleCancel}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ ...valueStyles, flex: 1, position: 'relative' }}>
            {effectiveValue || 'No value'}
            {hasPendingEdit && (
              <span
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  fontSize: '9px',
                  fontWeight: 600,
                  color: '#f59e0b',
                  backgroundColor: '#fef3c7',
                  padding: '1px 4px',
                  borderRadius: '3px',
                }}
              >
                PENDING
              </span>
            )}
          </div>
          {field.is_editable && onEdit && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                handleStartEdit();
              }}
            >
              Edit
            </Button>
          )}
        </div>
      )}

      <div style={metaStyles}>
        <span>Page {field.page}</span>
        {field.bbox && (
          <span>
            ({field.bbox.x.toFixed(0)}, {field.bbox.y.toFixed(0)})
          </span>
        )}
        {showEvidence && onShowEvidence && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onShowEvidence(field.id);
            }}
            style={{
              background: 'none',
              border: 'none',
              color: '#3b82f6',
              cursor: 'pointer',
              fontSize: '12px',
              textDecoration: 'underline',
            }}
          >
            View Evidence
          </button>
        )}
      </div>

      {hasLowConfidence && !hasIssues && (
        <div
          style={{
            ...issueStyles,
            backgroundColor: '#fef3c7',
            border: '1px solid #fde68a',
            color: '#92400e',
          }}
        >
          Low confidence extraction - please verify
        </div>
      )}

      {issues.map((issue) => (
        <div
          key={issue.id}
          style={{
            ...issueStyles,
            backgroundColor: getSeverityColor(issue.severity) + '15',
            borderLeft: `3px solid ${getSeverityColor(issue.severity)}`,
          }}
        >
          <div style={{ fontWeight: 500, marginBottom: '4px' }}>{issue.message}</div>
          {issue.suggested_action && (
            <div style={{ fontSize: '12px', opacity: 0.8 }}>{issue.suggested_action}</div>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Confidence indicator bar.
 */
export function ConfidenceBar({
  confidence,
  height = 4,
}: {
  confidence: number | null;
  height?: number;
}) {
  if (confidence === null) {
    return (
      <div
        style={{
          height,
          backgroundColor: '#e5e7eb',
          borderRadius: height / 2,
        }}
      />
    );
  }

  return (
    <div
      style={{
        height,
        backgroundColor: '#e5e7eb',
        borderRadius: height / 2,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${confidence * 100}%`,
          backgroundColor: getConfidenceColor(confidence),
          borderRadius: height / 2,
          transition: 'width 0.3s ease',
        }}
      />
    </div>
  );
}
