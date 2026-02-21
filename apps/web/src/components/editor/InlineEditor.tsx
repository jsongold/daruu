/**
 * Inline editor popover for editing field values directly in the preview.
 * Appears when clicking a field and provides text input with save/cancel.
 * Includes font style controls for customizing field appearance.
 */

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type CSSProperties,
  type KeyboardEvent,
  type ChangeEvent,
} from 'react';
import { Button } from '../ui/Button';
import { FontStyleControls } from './FontStyleControls';
import type { FontStyle } from '../../api/editClient';
import { DEFAULT_FONT_STYLE } from '../../api/editClient';

export interface InlineEditorProps {
  /** Field ID being edited */
  fieldId: string;
  /** Field label for display */
  fieldLabel: string;
  /** Current field value */
  currentValue: string;
  /** Field type for input behavior */
  fieldType?: 'text' | 'number' | 'date' | 'checkbox';
  /** Position to display the editor (relative to viewport) */
  position: { x: number; y: number };
  /** Called when user saves the value */
  onSave: (fieldId: string, value: string, fontStyle?: FontStyle) => void;
  /** Called when user cancels editing */
  onCancel: () => void;
  /** Whether the save is in progress */
  isLoading?: boolean;
  /** Container element for positioning bounds */
  containerRef?: React.RefObject<HTMLElement>;
  /** Current font style */
  currentFontStyle?: FontStyle;
  /** Whether to show font style controls */
  showFontControls?: boolean;
  /** Bounding box dimensions in pixels (for fit text feature) */
  bbox?: { width: number; height: number };
  /** Called immediately when font style changes (for live preview) */
  onFontStyleChange?: (fontStyle: FontStyle) => void;
}

const POPOVER_WIDTH = 320;
const POPOVER_MIN_HEIGHT = 120;
const MARGIN = 16;

export function InlineEditor({
  fieldId,
  fieldLabel,
  currentValue,
  fieldType = 'text',
  position,
  onSave,
  onCancel,
  isLoading = false,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  containerRef: _containerRef,
  currentFontStyle,
  showFontControls = true,
  bbox,
  onFontStyleChange,
}: InlineEditorProps) {
  const [value, setValue] = useState(currentValue);
  const [isCheckbox, setIsCheckbox] = useState(
    fieldType === 'checkbox' && (currentValue === 'true' || currentValue === 'Yes')
  );
  const [fontStyle, setFontStyle] = useState<FontStyle>(
    currentFontStyle || DEFAULT_FONT_STYLE
  );
  const [showFontPanel, setShowFontPanel] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Calculate adjusted position to stay in bounds
  const getAdjustedPosition = useCallback((): { x: number; y: number } => {
    let { x, y } = position;

    // Get viewport dimensions
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Adjust horizontal position
    if (x + POPOVER_WIDTH + MARGIN > viewportWidth) {
      x = Math.max(MARGIN, viewportWidth - POPOVER_WIDTH - MARGIN);
    }
    if (x < MARGIN) {
      x = MARGIN;
    }

    // Adjust vertical position
    if (y + POPOVER_MIN_HEIGHT + MARGIN > viewportHeight) {
      y = Math.max(MARGIN, viewportHeight - POPOVER_MIN_HEIGHT - MARGIN);
    }
    if (y < MARGIN) {
      y = MARGIN;
    }

    return { x, y };
  }, [position]);

  const adjustedPosition = getAdjustedPosition();

  // Focus input on mount
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      if ('select' in inputRef.current) {
        inputRef.current.select();
      }
    }
  }, []);

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node)
      ) {
        onCancel();
      }
    };

    // Add listener with a small delay to avoid closing immediately
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onCancel]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const finalValue = fieldType === 'checkbox' ? (isCheckbox ? 'Yes' : 'No') : value;
        onSave(fieldId, finalValue, fontStyle);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
      }
    },
    [fieldId, fieldType, isCheckbox, value, fontStyle, onSave, onCancel]
  );

  const handleSave = useCallback(() => {
    const finalValue = fieldType === 'checkbox' ? (isCheckbox ? 'Yes' : 'No') : value;
    onSave(fieldId, finalValue, fontStyle);
  }, [fieldId, fieldType, isCheckbox, value, fontStyle, onSave]);

  const handleFontStyleChange = useCallback((newFontStyle: FontStyle) => {
    setFontStyle(newFontStyle);
    onFontStyleChange?.(newFontStyle);
  }, [onFontStyleChange]);

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setValue(e.target.value);
  }, []);

  const handleCheckboxChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setIsCheckbox(e.target.checked);
  }, []);

  // Styles
  const popoverStyle: CSSProperties = {
    position: 'fixed',
    left: adjustedPosition.x,
    top: adjustedPosition.y,
    width: POPOVER_WIDTH,
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05)',
    zIndex: 1000,
    overflow: 'hidden',
  };

  const headerStyle: CSSProperties = {
    padding: '12px 16px',
    borderBottom: '1px solid #e5e7eb',
    backgroundColor: '#f9fafb',
  };

  const labelStyle: CSSProperties = {
    fontSize: '13px',
    fontWeight: 600,
    color: '#374151',
    margin: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const fieldIdStyle: CSSProperties = {
    fontSize: '11px',
    color: '#9ca3af',
    marginTop: '2px',
    fontFamily: 'monospace',
  };

  const bodyStyle: CSSProperties = {
    padding: '16px',
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

  const checkboxContainerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '8px 0',
  };

  const checkboxStyle: CSSProperties = {
    width: '20px',
    height: '20px',
    cursor: 'pointer',
  };

  const checkboxLabelStyle: CSSProperties = {
    fontSize: '14px',
    color: '#374151',
    cursor: 'pointer',
  };

  const footerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '8px',
    padding: '12px 16px',
    borderTop: '1px solid #e5e7eb',
    backgroundColor: '#f9fafb',
  };

  const hintStyle: CSSProperties = {
    fontSize: '11px',
    color: '#9ca3af',
    marginTop: '8px',
  };

  return (
    <div
      ref={popoverRef}
      style={popoverStyle}
      role="dialog"
      aria-label={`Edit ${fieldLabel}`}
      onKeyDown={handleKeyDown}
    >
      <div style={headerStyle}>
        <p style={labelStyle} title={fieldLabel}>
          {fieldLabel}
        </p>
        <p style={fieldIdStyle}>{fieldId}</p>
      </div>

      <div style={bodyStyle}>
        {fieldType === 'checkbox' ? (
          <div style={checkboxContainerStyle}>
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type="checkbox"
              checked={isCheckbox}
              onChange={handleCheckboxChange}
              style={checkboxStyle}
              id={`inline-checkbox-${fieldId}`}
              disabled={isLoading}
            />
            <label
              htmlFor={`inline-checkbox-${fieldId}`}
              style={checkboxLabelStyle}
            >
              {isCheckbox ? 'Checked' : 'Unchecked'}
            </label>
          </div>
        ) : fieldType === 'date' ? (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type="date"
            value={value}
            onChange={handleInputChange}
            style={inputStyle}
            disabled={isLoading}
            aria-label="Field value"
          />
        ) : fieldType === 'number' ? (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type="number"
            value={value}
            onChange={handleInputChange}
            style={inputStyle}
            disabled={isLoading}
            aria-label="Field value"
          />
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type="text"
            value={value}
            onChange={handleInputChange}
            style={inputStyle}
            disabled={isLoading}
            placeholder="Enter value..."
            aria-label="Field value"
          />
        )}

        {/* Font style toggle */}
        {showFontControls && fieldType !== 'checkbox' && (
          <div style={{ marginTop: '12px' }}>
            <button
              type="button"
              onClick={() => setShowFontPanel(!showFontPanel)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 10px',
                fontSize: '12px',
                color: '#6b7280',
                backgroundColor: showFontPanel ? '#f3f4f6' : 'transparent',
                border: '1px solid #e5e7eb',
                borderRadius: '4px',
                cursor: 'pointer',
                width: '100%',
                justifyContent: 'center',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 7V4h16v3" />
                <path d="M9 20h6" />
                <path d="M12 4v16" />
              </svg>
              {showFontPanel ? 'Hide' : 'Show'} Font Style
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ transform: showFontPanel ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>

            {showFontPanel && (
              <div style={{ marginTop: '12px', padding: '12px', backgroundColor: '#f9fafb', borderRadius: '6px' }}>
                <FontStyleControls
                  fontStyle={fontStyle}
                  onChange={handleFontStyleChange}
                  disabled={isLoading}
                  compact={false}
                  bbox={bbox}
                  textValue={value}
                />
              </div>
            )}
          </div>
        )}

        <p style={hintStyle}>
          Press Enter to save, Escape to cancel
        </p>
      </div>

      <div style={footerStyle}>
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={isLoading}
        >
          Cancel
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
    </div>
  );
}
