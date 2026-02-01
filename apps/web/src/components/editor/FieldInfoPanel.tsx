/**
 * Side panel showing details about the selected field.
 * Displays field info, edit input, and validation status.
 */

import {
  useState,
  useCallback,
  useEffect,
  type CSSProperties,
  type ChangeEvent,
  type KeyboardEvent,
} from 'react';
import { Button } from '../ui/Button';

export interface FieldInfo {
  /** Field ID */
  id: string;
  /** Field label/name */
  label: string;
  /** Current value */
  value: string;
  /** Field type */
  type: 'text' | 'checkbox' | 'date' | 'number';
  /** Bounding box on the form */
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
    page?: number;
  } | null;
  /** Whether field is required */
  required?: boolean;
  /** Validation status */
  validationStatus?: 'valid' | 'invalid' | 'warning' | null;
  /** Validation message */
  validationMessage?: string | null;
  /** Whether field has been edited */
  isEdited?: boolean;
}

export interface FieldInfoPanelProps {
  /** Selected field (null when nothing selected) */
  field: FieldInfo | null;
  /** Called when field value changes */
  onValueChange: (fieldId: string, value: string) => void;
  /** Called when panel should close */
  onClose?: () => void;
  /** Whether the save is in progress */
  isLoading?: boolean;
  /** Error message if any */
  error?: string | null;
}

export function FieldInfoPanel({
  field,
  onValueChange,
  onClose,
  isLoading = false,
  error,
}: FieldInfoPanelProps) {
  const [editValue, setEditValue] = useState('');
  const [isCheckbox, setIsCheckbox] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Sync edit value when field changes
  useEffect(() => {
    if (field) {
      setEditValue(field.value);
      setIsCheckbox(field.type === 'checkbox' && (field.value === 'true' || field.value === 'Yes'));
      setIsDirty(false);
    }
  }, [field]);

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setEditValue(e.target.value);
    setIsDirty(true);
  }, []);

  const handleCheckboxChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setIsCheckbox(e.target.checked);
    setIsDirty(true);
  }, []);

  const handleSave = useCallback(() => {
    if (!field || !isDirty) return;
    const finalValue = field.type === 'checkbox' ? (isCheckbox ? 'Yes' : 'No') : editValue;
    onValueChange(field.id, finalValue);
    setIsDirty(false);
  }, [field, isDirty, isCheckbox, editValue, onValueChange]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && isDirty) {
      e.preventDefault();
      handleSave();
    }
  }, [isDirty, handleSave]);

  const handleReset = useCallback(() => {
    if (field) {
      setEditValue(field.value);
      setIsCheckbox(field.type === 'checkbox' && (field.value === 'true' || field.value === 'Yes'));
      setIsDirty(false);
    }
  }, [field]);

  // Styles
  const panelStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: 'white',
    borderLeft: '1px solid #e5e7eb',
    width: '320px',
    minWidth: '320px',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px',
    borderBottom: '1px solid #e5e7eb',
    backgroundColor: '#f9fafb',
  };

  const titleStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#1f2937',
    margin: 0,
  };

  const closeButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    padding: 0,
    border: 'none',
    borderRadius: '4px',
    backgroundColor: 'transparent',
    color: '#6b7280',
    cursor: 'pointer',
  };

  const contentStyle: CSSProperties = {
    flex: 1,
    overflow: 'auto',
    padding: '16px',
  };

  const sectionStyle: CSSProperties = {
    marginBottom: '20px',
  };

  const sectionTitleStyle: CSSProperties = {
    fontSize: '11px',
    fontWeight: 600,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '8px',
  };

  const fieldIdStyle: CSSProperties = {
    fontSize: '12px',
    fontFamily: 'monospace',
    color: '#6b7280',
    backgroundColor: '#f3f4f6',
    padding: '6px 10px',
    borderRadius: '4px',
    wordBreak: 'break-all',
  };

  const fieldLabelStyle: CSSProperties = {
    fontSize: '14px',
    color: '#1f2937',
    margin: 0,
  };

  const inputStyle: CSSProperties = {
    width: '100%',
    padding: '10px 12px',
    fontSize: '14px',
    lineHeight: '1.5',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    outline: 'none',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  };

  const textareaStyle: CSSProperties = {
    ...inputStyle,
    minHeight: '80px',
    resize: 'vertical',
  };

  const checkboxContainerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '8px 0',
  };

  const checkboxInputStyle: CSSProperties = {
    width: '20px',
    height: '20px',
    cursor: 'pointer',
  };

  const checkboxLabelStyle: CSSProperties = {
    fontSize: '14px',
    color: '#374151',
    cursor: 'pointer',
  };

  const badgeContainerStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  };

  const badgeStyle = (variant: 'default' | 'success' | 'warning' | 'error'): CSSProperties => {
    const colors: Record<string, { bg: string; text: string }> = {
      default: { bg: '#f3f4f6', text: '#374151' },
      success: { bg: '#dcfce7', text: '#166534' },
      warning: { bg: '#fef3c7', text: '#92400e' },
      error: { bg: '#fee2e2', text: '#991b1b' },
    };
    const { bg, text } = colors[variant];
    return {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '4px 8px',
      fontSize: '12px',
      fontWeight: 500,
      backgroundColor: bg,
      color: text,
      borderRadius: '4px',
    };
  };

  const actionsStyle: CSSProperties = {
    display: 'flex',
    gap: '8px',
    marginTop: '12px',
  };

  const errorStyle: CSSProperties = {
    padding: '12px',
    backgroundColor: '#fee2e2',
    color: '#991b1b',
    fontSize: '13px',
    borderRadius: '6px',
    marginBottom: '16px',
  };

  const emptyStateStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    padding: '32px',
    textAlign: 'center',
  };

  const emptyIconStyle: CSSProperties = {
    color: '#d1d5db',
    marginBottom: '16px',
  };

  const emptyTextStyle: CSSProperties = {
    fontSize: '14px',
    color: '#6b7280',
    margin: 0,
  };

  // Empty state when no field selected
  if (!field) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}>
          <h3 style={titleStyle}>Field Details</h3>
        </div>
        <div style={emptyStateStyle}>
          <div style={emptyIconStyle}>
            <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <p style={emptyTextStyle}>
            Click on a field in the preview to see its details and edit its value.
          </p>
        </div>
      </div>
    );
  }

  // Get validation badge variant
  const getValidationVariant = (): 'default' | 'success' | 'warning' | 'error' => {
    if (!field.validationStatus) return 'default';
    switch (field.validationStatus) {
      case 'valid':
        return 'success';
      case 'warning':
        return 'warning';
      case 'invalid':
        return 'error';
      default:
        return 'default';
    }
  };

  // Get type display name
  const getTypeDisplay = (type: string): string => {
    const typeMap: Record<string, string> = {
      text: 'Text',
      number: 'Number',
      date: 'Date',
      checkbox: 'Checkbox',
    };
    return typeMap[type] || type;
  };

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <h3 style={titleStyle}>Field Details</h3>
        {onClose && (
          <button
            style={closeButtonStyle}
            onClick={onClose}
            aria-label="Close panel"
          >
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div style={contentStyle}>
        {error && (
          <div style={errorStyle}>
            {error}
          </div>
        )}

        {/* Field Label */}
        <div style={sectionStyle}>
          <p style={sectionTitleStyle}>Label</p>
          <p style={fieldLabelStyle}>{field.label}</p>
        </div>

        {/* Field ID */}
        <div style={sectionStyle}>
          <p style={sectionTitleStyle}>Field ID</p>
          <p style={fieldIdStyle}>{field.id}</p>
        </div>

        {/* Field Type & Status */}
        <div style={sectionStyle}>
          <p style={sectionTitleStyle}>Properties</p>
          <div style={badgeContainerStyle}>
            <span style={badgeStyle('default')}>
              {getTypeDisplay(field.type)}
            </span>
            {field.required && (
              <span style={badgeStyle('warning')}>
                Required
              </span>
            )}
            {field.isEdited && (
              <span style={badgeStyle('success')}>
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Edited
              </span>
            )}
            {field.validationStatus && (
              <span style={badgeStyle(getValidationVariant())}>
                {field.validationStatus === 'valid' && (
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {field.validationStatus === 'invalid' && (
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                {field.validationStatus === 'warning' && (
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                )}
                {field.validationStatus.charAt(0).toUpperCase() + field.validationStatus.slice(1)}
              </span>
            )}
          </div>
          {field.validationMessage && (
            <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px' }}>
              {field.validationMessage}
            </p>
          )}
        </div>

        {/* Value Editor */}
        <div style={sectionStyle}>
          <p style={sectionTitleStyle}>Value</p>
          {field.type === 'checkbox' ? (
            <div style={checkboxContainerStyle}>
              <input
                type="checkbox"
                checked={isCheckbox}
                onChange={handleCheckboxChange}
                style={checkboxInputStyle}
                id="field-checkbox-value"
                disabled={isLoading}
              />
              <label htmlFor="field-checkbox-value" style={checkboxLabelStyle}>
                {isCheckbox ? 'Checked (Yes)' : 'Unchecked (No)'}
              </label>
            </div>
          ) : field.type === 'date' ? (
            <input
              type="date"
              value={editValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              style={inputStyle}
              disabled={isLoading}
              aria-label="Field value"
            />
          ) : field.type === 'number' ? (
            <input
              type="number"
              value={editValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              style={inputStyle}
              disabled={isLoading}
              aria-label="Field value"
            />
          ) : editValue.length > 50 ? (
            <textarea
              value={editValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              style={textareaStyle}
              disabled={isLoading}
              placeholder="Enter value..."
              aria-label="Field value"
            />
          ) : (
            <input
              type="text"
              value={editValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              style={inputStyle}
              disabled={isLoading}
              placeholder="Enter value..."
              aria-label="Field value"
            />
          )}

          {isDirty && (
            <div style={actionsStyle}>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleReset}
                disabled={isLoading}
              >
                Reset
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSave}
                loading={isLoading}
                disabled={isLoading}
              >
                Save
              </Button>
            </div>
          )}
        </div>

        {/* Position Info */}
        {field.bbox && (
          <div style={sectionStyle}>
            <p style={sectionTitleStyle}>Position</p>
            <p style={{ fontSize: '12px', color: '#6b7280', fontFamily: 'monospace' }}>
              {field.bbox.page && `Page ${field.bbox.page} | `}
              x: {Math.round(field.bbox.x * 100)}%, y: {Math.round(field.bbox.y * 100)}%
              <br />
              w: {Math.round(field.bbox.width * 100)}%, h: {Math.round(field.bbox.height * 100)}%
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
