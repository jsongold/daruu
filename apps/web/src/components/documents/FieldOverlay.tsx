/**
 * Field overlay component for highlighting AcroForm fields on PDF preview.
 *
 * Supports bidirectional field selection:
 * - Clicking a field on the PDF notifies parent via onFieldClick
 * - Parent can externally highlight a field via highlightedFieldId
 * - Different highlight styles for selected, anchor, and related fields
 *
 * Supports bbox editing when editable=true:
 * - Drag to move bbox
 * - Resize handles to adjust size
 * - onBboxChange callback for persisting changes
 */

import { useState, useCallback, type CSSProperties } from 'react';
import type { AcroFormFieldInfo, BBox } from '../../types/api';

export type HighlightStyle = 'default' | 'selected' | 'anchor' | 'related';
export type FieldSaveStatus = 'pending' | 'saving' | 'success' | 'error';

export interface BBoxUpdate {
  fieldName: string;
  bbox: BBox;
  value?: string;
}

export interface FieldOverlayProps {
  fields: AcroFormFieldInfo[];
  currentPage: number;
  previewScale: number;
  zoom: number;
  pageDimensions?: { width: number; height: number };
  imageDimensions?: { width: number; height: number };
  onFieldClick?: (field: AcroFormFieldInfo) => void;
  onFieldHover?: (field: AcroFormFieldInfo | null) => void;
  /** Externally controlled field highlight by field name */
  highlightedFieldName?: string | null;
  /** Externally controlled highlight style */
  highlightStyle?: HighlightStyle;
  /** Additional bbox to highlight (e.g., anchor/label bbox) */
  highlightedAnchorBbox?: BBox | null;
  /** Enable bbox editing (drag/resize) */
  editable?: boolean;
  /** Callback when bbox is changed (after drag/resize ends) */
  onBboxChange?: (update: BBoxUpdate) => void;
  /** External field values to display (field name -> value) - overrides AcroForm values */
  fieldValues?: Map<string, string>;
  /** Save status for each field (field name -> status) */
  fieldSaveStatus?: Map<string, FieldSaveStatus>;
  /** Error messages for fields with save errors (field name -> error message) */
  fieldSaveErrors?: Map<string, string>;
}

interface TooltipPosition {
  x: number;
  y: number;
}

/** Style configurations for different highlight modes */
const HIGHLIGHT_STYLES: Record<HighlightStyle, { bg: string; bgHover: string; border: string; borderHover: string; borderStyle: string }> = {
  default: {
    bg: 'rgba(59, 130, 246, 0.15)',
    bgHover: 'rgba(59, 130, 246, 0.3)',
    border: 'rgba(59, 130, 246, 0.5)',
    borderHover: 'rgba(59, 130, 246, 0.8)',
    borderStyle: 'solid',
  },
  selected: {
    bg: 'rgba(59, 130, 246, 0.25)',
    bgHover: 'rgba(59, 130, 246, 0.35)',
    border: 'rgba(37, 99, 235, 0.9)',
    borderHover: 'rgba(37, 99, 235, 1)',
    borderStyle: 'solid',
  },
  anchor: {
    bg: 'rgba(34, 197, 94, 0.15)',
    bgHover: 'rgba(34, 197, 94, 0.25)',
    border: 'rgba(22, 163, 74, 0.7)',
    borderHover: 'rgba(22, 163, 74, 0.9)',
    borderStyle: 'dashed',
  },
  related: {
    bg: 'rgba(251, 191, 36, 0.15)',
    bgHover: 'rgba(251, 191, 36, 0.25)',
    border: 'rgba(245, 158, 11, 0.5)',
    borderHover: 'rgba(245, 158, 11, 0.7)',
    borderStyle: 'dotted',
  },
};

/** Get styles for save status indicator */
function getSaveStatusIndicatorStyles(status: FieldSaveStatus): CSSProperties {
  switch (status) {
    case 'pending':
      return {
        backgroundColor: '#fef3c7',
        border: '1px solid #fcd34d',
        color: '#92400e',
      };
    case 'saving':
      return {
        backgroundColor: '#dbeafe',
        border: '1px solid #60a5fa',
        color: '#1d4ed8',
      };
    case 'success':
      return {
        backgroundColor: '#dcfce7',
        border: '1px solid #4ade80',
        color: '#166534',
      };
    case 'error':
      return {
        backgroundColor: '#fee2e2',
        border: '1px solid #f87171',
        color: '#991b1b',
      };
  }
}

/** Get icon for save status */
function getSaveStatusIcon(status: FieldSaveStatus): string {
  switch (status) {
    case 'pending':
      return '...';
    case 'saving':
      return 'O'; // Simple spinner placeholder - in a real app, use an animated spinner
    case 'success':
      return 'V'; // Checkmark
    case 'error':
      return '!';
  }
}

/** Get title text for save status tooltip */
function getSaveStatusTitle(status: FieldSaveStatus, errorMessage?: string): string {
  switch (status) {
    case 'pending':
      return 'Waiting to save...';
    case 'saving':
      return 'Saving...';
    case 'success':
      return 'Saved';
    case 'error':
      return errorMessage ? `Save failed: ${errorMessage}` : 'Save failed';
  }
}

export function FieldOverlay({
  fields,
  currentPage,
  previewScale,
  zoom: _zoom, // Reserved for future zoom-dependent calculations - prefixed with _ to indicate intentionally unused
  pageDimensions,
  imageDimensions,
  onFieldClick,
  onFieldHover,
  highlightedFieldName,
  highlightStyle = 'selected',
  highlightedAnchorBbox,
  editable = false,
  onBboxChange,
  fieldValues,
  fieldSaveStatus,
  fieldSaveErrors,
}: FieldOverlayProps) {
  const [hoveredField, setHoveredField] = useState<AcroFormFieldInfo | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition>({ x: 0, y: 0 });
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');

  // Filter fields for current page
  const pageFields = fields.filter((field) => field.bbox.page === currentPage);

  // Check if anchor bbox is on current page
  const showAnchorBbox = highlightedAnchorBbox && highlightedAnchorBbox.page === currentPage;

  const handleMouseEnter = (
    field: AcroFormFieldInfo,
    event: React.MouseEvent<HTMLDivElement>
  ) => {
    setHoveredField(field);
    setTooltipPosition({
      x: event.clientX,
      y: event.clientY,
    });
    onFieldHover?.(field);
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (hoveredField) {
      setTooltipPosition({
        x: event.clientX,
        y: event.clientY,
      });
    }
  };

  const handleMouseLeave = () => {
    setHoveredField(null);
    onFieldHover?.(null);
  };

  /** Get the effective value for a field (external value takes precedence) */
  const getEffectiveValue = (field: AcroFormFieldInfo): string => {
    return fieldValues?.get(field.field_name) ?? field.value ?? '';
  };

  const handleClick = (field: AcroFormFieldInfo) => {
    if (editable && !field.readonly) {
      // Enter edit mode with the effective value
      setEditingField(field.field_name);
      setEditValue(getEffectiveValue(field));
    }
    onFieldClick?.(field);
  };

  const handleEditBlur = useCallback((field: AcroFormFieldInfo) => {
    if (editingField === field.field_name && onBboxChange) {
      // Notify parent of value change
      onBboxChange({
        fieldName: field.field_name,
        bbox: field.bbox,
        value: editValue,
      });
    }
    setEditingField(null);
    setEditValue('');
  }, [editingField, editValue, onBboxChange]);

  const handleEditKeyDown = useCallback((e: React.KeyboardEvent, field: AcroFormFieldInfo) => {
    if (e.key === 'Enter') {
      handleEditBlur(field);
    } else if (e.key === 'Escape') {
      setEditingField(null);
      setEditValue('');
    }
  }, [handleEditBlur]);

  const containerStyles: CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    pointerEvents: 'none',
  };

  // Calculate the scale ratio for positioning overlays
  const getScaleRatio = (): number => {
    if (pageDimensions && imageDimensions) {
      const expectedWidth = pageDimensions.width * previewScale;
      return imageDimensions.width / expectedWidth;
    }
    return 1;
  };

  const scaleRatio = getScaleRatio();

  const getFieldStyles = (field: AcroFormFieldInfo, isHovered: boolean): CSSProperties => {
    // Calculate position considering preview scale and display scale
    const x = field.bbox.x * previewScale * scaleRatio;
    const y = field.bbox.y * previewScale * scaleRatio;
    const width = field.bbox.width * previewScale * scaleRatio;
    const height = field.bbox.height * previewScale * scaleRatio;

    // Determine highlight state
    const isExternallyHighlighted = highlightedFieldName === field.field_name;
    const effectiveStyle = isExternallyHighlighted ? highlightStyle : 'default';
    const styleConfig = HIGHLIGHT_STYLES[effectiveStyle];

    // Use highlighted styles if externally highlighted, otherwise use hover state
    const isHighlighted = isHovered || isExternallyHighlighted;

    return {
      position: 'absolute',
      left: `${x}px`,
      top: `${y}px`,
      width: `${width}px`,
      height: `${height}px`,
      backgroundColor: isHighlighted ? styleConfig.bgHover : styleConfig.bg,
      border: isHighlighted
        ? `2px ${styleConfig.borderStyle} ${styleConfig.borderHover}`
        : `1px ${styleConfig.borderStyle} ${styleConfig.border}`,
      borderRadius: '2px',
      cursor: 'pointer',
      pointerEvents: 'auto',
      transition: 'background-color 0.15s ease, border 0.15s ease, box-shadow 0.15s ease',
      boxSizing: 'border-box',
      // Add subtle glow effect for externally highlighted fields
      boxShadow: isExternallyHighlighted
        ? `0 0 8px ${styleConfig.borderHover}`
        : 'none',
    };
  };

  const getAnchorBboxStyles = (bbox: BBox): CSSProperties => {
    const x = bbox.x * previewScale * scaleRatio;
    const y = bbox.y * previewScale * scaleRatio;
    const width = bbox.width * previewScale * scaleRatio;
    const height = bbox.height * previewScale * scaleRatio;
    const styleConfig = HIGHLIGHT_STYLES.anchor;

    return {
      position: 'absolute',
      left: `${x}px`,
      top: `${y}px`,
      width: `${width}px`,
      height: `${height}px`,
      backgroundColor: styleConfig.bgHover,
      border: `2px ${styleConfig.borderStyle} ${styleConfig.borderHover}`,
      borderRadius: '2px',
      pointerEvents: 'none', // Anchor is for display only
      boxShadow: `0 0 6px ${styleConfig.borderHover}`,
    };
  };

  const tooltipStyles: CSSProperties = {
    position: 'fixed',
    left: `${tooltipPosition.x + 12}px`,
    top: `${tooltipPosition.y + 12}px`,
    backgroundColor: 'rgba(17, 24, 39, 0.95)',
    color: 'white',
    padding: '6px 10px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 500,
    whiteSpace: 'nowrap',
    zIndex: 1000,
    pointerEvents: 'none',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
  };

  const tooltipTypeStyles: CSSProperties = {
    fontSize: '10px',
    color: 'rgba(255, 255, 255, 0.7)',
    marginTop: '2px',
  };

  if (pageFields.length === 0) {
    return null;
  }

  return (
    <div style={containerStyles}>
      {/* Render anchor bbox if provided and on current page */}
      {showAnchorBbox && highlightedAnchorBbox && (
        <div
          style={getAnchorBboxStyles(highlightedAnchorBbox)}
          title="Label/Anchor"
        />
      )}

      {/* Render field overlays */}
      {pageFields.map((field, index) => {
        const isEditing = editingField === field.field_name;
        const fieldStyles = getFieldStyles(field, hoveredField === field);
        const saveStatus = fieldSaveStatus?.get(field.field_name);
        const saveError = fieldSaveErrors?.get(field.field_name);
        const isCheckbox = field.field_type === 'checkbox';

        return (
          <div
            key={`${field.field_name}-${index}`}
            style={fieldStyles}
            onMouseEnter={(e) => handleMouseEnter(field, e)}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            onClick={() => {
              if (isCheckbox && editable && !field.readonly) {
                // Toggle checkbox value
                const currentValue = getEffectiveValue(field);
                const newValue = currentValue === 'true' || currentValue === 'Yes' || currentValue === '1' ? 'false' : 'true';
                if (onBboxChange) {
                  onBboxChange({
                    fieldName: field.field_name,
                    bbox: field.bbox,
                    value: newValue,
                  });
                }
                onFieldClick?.(field);
              } else if (!isEditing) {
                handleClick(field);
              }
            }}
            title={saveError ? `Error: ${saveError}` : field.field_name}
          >
            {/* Save status indicator */}
            {saveStatus && (
              <div
                style={{
                  position: 'absolute',
                  top: '-6px',
                  right: '-6px',
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '9px',
                  fontWeight: 700,
                  zIndex: 10,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  ...getSaveStatusIndicatorStyles(saveStatus),
                }}
                title={getSaveStatusTitle(saveStatus, saveError)}
              >
                {getSaveStatusIcon(saveStatus)}
              </div>
            )}

            {/* Field content */}
            {(() => {
              const effectiveValue = getEffectiveValue(field);

              // Checkbox rendering
              if (isCheckbox) {
                const isChecked = effectiveValue === 'true' || effectiveValue === 'Yes' || effectiveValue === '1';
                return (
                  <div
                    style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <div
                      style={{
                        width: '14px',
                        height: '14px',
                        border: '2px solid #374151',
                        borderRadius: '2px',
                        backgroundColor: isChecked ? '#3b82f6' : 'white',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '10px',
                        fontWeight: 700,
                      }}
                    >
                      {isChecked ? 'X' : ''}
                    </div>
                  </div>
                );
              }

              // Text field editing
              if (isEditing) {
                return (
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={() => handleEditBlur(field)}
                    onKeyDown={(e) => handleEditKeyDown(e, field)}
                    autoFocus
                    style={{
                      width: '100%',
                      height: '100%',
                      border: 'none',
                      outline: 'none',
                      background: 'rgba(255, 255, 255, 0.9)',
                      padding: '2px 4px',
                      fontSize: '12px',
                      boxSizing: 'border-box',
                    }}
                  />
                );
              }

              // Text field display
              if (effectiveValue) {
                return (
                  <span style={{
                    fontSize: '10px',
                    color: '#374151',
                    padding: '1px 3px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    display: 'block',
                  }}>
                    {effectiveValue}
                  </span>
                );
              }
              return null;
            })()}
          </div>
        );
      })}

      {/* Tooltip for hovered field */}
      {hoveredField && (
        <div style={tooltipStyles}>
          <div>{hoveredField.field_name || '(unnamed field)'}</div>
          <div style={tooltipTypeStyles}>
            {hoveredField.field_type}
            {hoveredField.readonly && ' (readonly)'}
            {getEffectiveValue(hoveredField) && `: ${getEffectiveValue(hoveredField)}`}
          </div>
        </div>
      )}
    </div>
  );
}
