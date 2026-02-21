/**
 * Font style controls for field editing.
 * Provides controls for font size, family, color, and alignment.
 * Includes "Fit Text" feature to auto-calculate optimal font size.
 */

import { useCallback, useState, useMemo, type CSSProperties } from 'react';
import type { FontStyle } from '../../api/editClient';
import {
  DEFAULT_FONT_STYLE,
  FONT_SIZE_PRESETS,
  FONT_FAMILY_OPTIONS,
  FONT_COLOR_PRESETS,
} from '../../api/editClient';

/** Bounding box dimensions for fit text calculation */
export interface BoundingBox {
  /** Width in pixels */
  width: number;
  /** Height in pixels */
  height: number;
}

/** Fit text calculation constraints */
const FIT_TEXT_CONFIG = {
  /** Minimum readable font size */
  MIN_FONT_SIZE: 6,
  /** Maximum font size */
  MAX_FONT_SIZE: 72,
  /**
   * Horizontal padding per side: must match FieldHighlight rendering.
   * FieldHighlight uses border-box with 2px border + left/right 4px = 6px per side.
   * Add 1px buffer for canvas/CSS measurement differences.
   */
  HORIZONTAL_PADDING: 7,
  /**
   * Vertical padding per side: must match FieldHighlight rendering.
   * FieldHighlight uses border-box with 2px border + text is vertically centered.
   * Add 1px buffer for canvas/CSS measurement differences.
   */
  VERTICAL_PADDING: 3,
  /** Line height multiplier for height calculation */
  LINE_HEIGHT: 1.2,
};

/**
 * Calculate optimal font size to fit text within bounding box.
 * Uses canvas measureText for accurate text width measurement.
 */
function calculateFitFontSize(
  text: string,
  bbox: BoundingBox,
  fontFamily: string
): number {
  if (!text || text.length === 0 || bbox.width <= 0 || bbox.height <= 0) {
    return DEFAULT_FONT_STYLE.fontSize;
  }

  // Create offscreen canvas for text measurement
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return DEFAULT_FONT_STYLE.fontSize;
  }

  // Map font family to web-safe equivalent
  const fontFamilyMap: Record<string, string> = {
    'Helvetica': 'Helvetica, Arial, sans-serif',
    'Times': 'Times New Roman, Times, serif',
    'Courier': 'Courier New, Courier, monospace',
  };
  const mappedFont = fontFamilyMap[fontFamily] || fontFamily;

  // Available space inside the field
  const availableWidth = bbox.width - FIT_TEXT_CONFIG.HORIZONTAL_PADDING * 2;
  const availableHeight = bbox.height - FIT_TEXT_CONFIG.VERTICAL_PADDING * 2;

  // Binary search for optimal font size
  let low = FIT_TEXT_CONFIG.MIN_FONT_SIZE;
  let high = FIT_TEXT_CONFIG.MAX_FONT_SIZE;
  let optimalSize = low;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    ctx.font = `${mid}px ${mappedFont}`;
    const metrics = ctx.measureText(text);
    // Use actualBoundingBox for more accurate width when available,
    // falling back to advance width
    const textWidth = (
      typeof metrics.actualBoundingBoxLeft === 'number' &&
      typeof metrics.actualBoundingBoxRight === 'number'
    )
      ? metrics.actualBoundingBoxLeft + metrics.actualBoundingBoxRight
      : metrics.width;
    const textHeight = mid * FIT_TEXT_CONFIG.LINE_HEIGHT;

    if (textWidth <= availableWidth && textHeight <= availableHeight) {
      optimalSize = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return optimalSize;
}

export interface FontStyleControlsProps {
  /** Current font style */
  fontStyle: FontStyle;
  /** Called when font style changes */
  onChange: (fontStyle: FontStyle) => void;
  /** Whether controls are disabled */
  disabled?: boolean;
  /** Compact mode - single row */
  compact?: boolean;
  /** Bounding box for fit text calculation (optional) */
  bbox?: BoundingBox;
  /** Current text value for fit text calculation (optional) */
  textValue?: string;
}

export function FontStyleControls({
  fontStyle,
  onChange,
  disabled = false,
  compact = false,
  bbox,
  textValue,
}: FontStyleControlsProps) {
  const [showColorPicker, setShowColorPicker] = useState(false);

  // Check if fit text is available
  const canFitText = useMemo(() => {
    return Boolean(bbox && bbox.width > 0 && bbox.height > 0 && textValue && textValue.length > 0);
  }, [bbox, textValue]);

  const currentStyle: Required<FontStyle> = {
    ...DEFAULT_FONT_STYLE,
    ...fontStyle,
  };

  const handleFontSizeChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ ...fontStyle, fontSize: parseInt(e.target.value, 10) });
    },
    [fontStyle, onChange]
  );

  const handleFontFamilyChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ ...fontStyle, fontFamily: e.target.value as FontStyle['fontFamily'] });
    },
    [fontStyle, onChange]
  );

  const handleFontColorChange = useCallback(
    (color: string) => {
      onChange({ ...fontStyle, fontColor: color });
      setShowColorPicker(false);
    },
    [fontStyle, onChange]
  );

  const handleAlignmentChange = useCallback(
    (alignment: FontStyle['alignment']) => {
      onChange({ ...fontStyle, alignment });
    },
    [fontStyle, onChange]
  );

  const handleFitText = useCallback(() => {
    if (!bbox || !textValue) {
      return;
    }
    const optimalFontSize = calculateFitFontSize(
      textValue,
      bbox,
      currentStyle.fontFamily
    );
    onChange({ ...fontStyle, fontSize: optimalFontSize });
  }, [bbox, textValue, currentStyle.fontFamily, fontStyle, onChange]);

  // Styles
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: compact ? 'row' : 'column',
    gap: compact ? '8px' : '12px',
    flexWrap: 'wrap',
  };

  const rowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexWrap: 'wrap',
  };

  const labelStyle: CSSProperties = {
    fontSize: '11px',
    fontWeight: 500,
    color: '#6b7280',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    minWidth: compact ? 'auto' : '60px',
  };

  const selectStyle: CSSProperties = {
    padding: '6px 8px',
    fontSize: '13px',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    backgroundColor: 'white',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    outline: 'none',
  };

  const colorButtonStyle = (color: string, isSelected: boolean): CSSProperties => ({
    width: '24px',
    height: '24px',
    borderRadius: '4px',
    border: isSelected ? '2px solid #3b82f6' : '1px solid #d1d5db',
    backgroundColor: color,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    padding: 0,
    boxShadow: isSelected ? '0 0 0 2px rgba(59, 130, 246, 0.3)' : 'none',
  });

  const alignButtonStyle = (isSelected: boolean): CSSProperties => ({
    width: '28px',
    height: '28px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '4px',
    border: '1px solid',
    borderColor: isSelected ? '#3b82f6' : '#d1d5db',
    backgroundColor: isSelected ? '#eff6ff' : 'white',
    color: isSelected ? '#3b82f6' : '#6b7280',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    padding: 0,
  });

  const colorPickerContainerStyle: CSSProperties = {
    position: 'relative',
  };

  const fitTextButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 500,
    color: canFitText ? '#3b82f6' : '#9ca3af',
    backgroundColor: canFitText ? '#eff6ff' : '#f3f4f6',
    border: '1px solid',
    borderColor: canFitText ? '#3b82f6' : '#d1d5db',
    borderRadius: '4px',
    cursor: canFitText && !disabled ? 'pointer' : 'not-allowed',
    opacity: disabled ? 0.6 : 1,
    transition: 'all 0.15s ease',
  };

  const colorDropdownStyle: CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: 0,
    marginTop: '4px',
    display: 'flex',
    flexWrap: 'wrap',
    gap: '4px',
    padding: '8px',
    backgroundColor: 'white',
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
    zIndex: 10,
    width: '140px',
  };

  return (
    <div style={containerStyle}>
      {/* Font Size */}
      <div style={rowStyle}>
        {!compact && <span style={labelStyle}>Size</span>}
        <select
          value={currentStyle.fontSize}
          onChange={handleFontSizeChange}
          disabled={disabled}
          style={selectStyle}
          title="Font size"
        >
          {/* Include current font size if not in presets (e.g. from fit calculation) */}
          {!FONT_SIZE_PRESETS.includes(currentStyle.fontSize as typeof FONT_SIZE_PRESETS[number]) && (
            <option key={currentStyle.fontSize} value={currentStyle.fontSize}>
              {currentStyle.fontSize}pt (fit)
            </option>
          )}
          {FONT_SIZE_PRESETS.map((size) => (
            <option key={size} value={size}>
              {size}pt
            </option>
          ))}
        </select>
        {/* Fit Text button */}
        <button
          type="button"
          onClick={handleFitText}
          disabled={disabled || !canFitText}
          style={fitTextButtonStyle}
          title={canFitText ? 'Auto-fit text to field size' : 'Enter text and ensure field has dimensions'}
          aria-label="Fit text to field"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16v16H4z" />
            <path d="M9 9h6v6H9z" />
            <path d="M4 12h5M15 12h5M12 4v5M12 15v5" />
          </svg>
          Fit
        </button>
      </div>

      {/* Font Family */}
      <div style={rowStyle}>
        {!compact && <span style={labelStyle}>Font</span>}
        <select
          value={currentStyle.fontFamily}
          onChange={handleFontFamilyChange}
          disabled={disabled}
          style={{ ...selectStyle, minWidth: '120px' }}
          title="Font family"
        >
          {FONT_FAMILY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Font Color */}
      <div style={rowStyle}>
        {!compact && <span style={labelStyle}>Color</span>}
        <div style={colorPickerContainerStyle}>
          <button
            type="button"
            onClick={() => !disabled && setShowColorPicker(!showColorPicker)}
            disabled={disabled}
            style={colorButtonStyle(currentStyle.fontColor, false)}
            title="Font color"
            aria-label="Select font color"
          />
          {showColorPicker && (
            <div style={colorDropdownStyle}>
              {FONT_COLOR_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  onClick={() => handleFontColorChange(preset.value)}
                  style={colorButtonStyle(preset.value, currentStyle.fontColor === preset.value)}
                  title={preset.label}
                  aria-label={preset.label}
                />
              ))}
              <input
                type="color"
                value={currentStyle.fontColor}
                onChange={(e) => handleFontColorChange(e.target.value)}
                style={{
                  width: '24px',
                  height: '24px',
                  padding: 0,
                  border: '1px solid #d1d5db',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
                title="Custom color"
              />
            </div>
          )}
        </div>
      </div>

      {/* Alignment */}
      <div style={rowStyle}>
        {!compact && <span style={labelStyle}>Align</span>}
        <div style={{ display: 'flex', gap: '2px' }}>
          <button
            type="button"
            onClick={() => !disabled && handleAlignmentChange('left')}
            disabled={disabled}
            style={alignButtonStyle(currentStyle.alignment === 'left')}
            title="Align left"
            aria-label="Align left"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="15" y2="12" />
              <line x1="3" y1="18" x2="18" y2="18" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => !disabled && handleAlignmentChange('center')}
            disabled={disabled}
            style={alignButtonStyle(currentStyle.alignment === 'center')}
            title="Align center"
            aria-label="Align center"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="6" y1="12" x2="18" y2="12" />
              <line x1="4" y1="18" x2="20" y2="18" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => !disabled && handleAlignmentChange('right')}
            disabled={disabled}
            style={alignButtonStyle(currentStyle.alignment === 'right')}
            title="Align right"
            aria-label="Align right"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="9" y1="12" x2="21" y2="12" />
              <line x1="6" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
