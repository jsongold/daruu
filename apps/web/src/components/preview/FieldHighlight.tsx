/**
 * Overlay component for showing clickable field regions on document preview.
 * Highlights fields with different colors based on their status.
 */

import {
  useState,
  useCallback,
  type CSSProperties,
  type MouseEvent,
} from 'react';
import type { FontStyle } from '../../api/editClient';

export interface FieldRegion {
  /** Field ID */
  id: string;
  /** Field label */
  label: string;
  /** Current value */
  value: string;
  /** Bounding box (normalized 0-1 coordinates) */
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  /** Field type */
  type?: 'text' | 'checkbox' | 'date' | 'number';
  /** Status for coloring */
  status?: 'empty' | 'filled' | 'selected' | 'error';
  /** Whether field is required */
  required?: boolean;
  /** Font style for rendering the value */
  fontStyle?: FontStyle;
}

export interface FieldHighlightProps {
  /** Fields to highlight */
  fields: FieldRegion[];
  /** Currently selected field ID */
  selectedFieldId?: string | null;
  /** Called when a field is clicked */
  onFieldClick: (
    fieldId: string,
    position: { x: number; y: number }
  ) => void;
  /** Called when a field is hovered */
  onFieldHover?: (fieldId: string | null) => void;
  /** Whether highlighting is enabled */
  enabled?: boolean;
  /** Show labels on hover */
  showLabels?: boolean;
  /** Container width in pixels */
  containerWidth: number;
  /** Container height in pixels */
  containerHeight: number;
}

// Colors for different field states
const COLORS = {
  empty: {
    fill: 'rgba(251, 191, 36, 0.2)',
    stroke: 'rgba(251, 191, 36, 0.8)',
    hoverFill: 'rgba(251, 191, 36, 0.35)',
  },
  filled: {
    fill: 'rgba(34, 197, 94, 0.15)',
    stroke: 'rgba(34, 197, 94, 0.7)',
    hoverFill: 'rgba(34, 197, 94, 0.3)',
  },
  selected: {
    fill: 'rgba(59, 130, 246, 0.25)',
    stroke: 'rgba(59, 130, 246, 1)',
    hoverFill: 'rgba(59, 130, 246, 0.35)',
  },
  error: {
    fill: 'rgba(239, 68, 68, 0.15)',
    stroke: 'rgba(239, 68, 68, 0.7)',
    hoverFill: 'rgba(239, 68, 68, 0.3)',
  },
};

export function FieldHighlight({
  fields,
  selectedFieldId,
  onFieldClick,
  onFieldHover,
  enabled = true,
  showLabels = true,
  containerWidth,
  containerHeight,
}: FieldHighlightProps) {
  const [hoveredFieldId, setHoveredFieldId] = useState<string | null>(null);

  const handleMouseEnter = useCallback((fieldId: string) => {
    setHoveredFieldId(fieldId);
    onFieldHover?.(fieldId);
  }, [onFieldHover]);

  const handleMouseLeave = useCallback(() => {
    setHoveredFieldId(null);
    onFieldHover?.(null);
  }, [onFieldHover]);

  const handleClick = useCallback((
    e: MouseEvent<HTMLDivElement>,
    field: FieldRegion
  ) => {
    e.stopPropagation();
    // Get click position relative to viewport for popover positioning
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.bottom + 8,
    };
    onFieldClick(field.id, position);
  }, [onFieldClick]);

  if (!enabled || fields.length === 0) {
    return null;
  }

  const overlayStyle: CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    pointerEvents: 'none',
    zIndex: 10,
  };

  return (
    <div style={overlayStyle}>
      {fields.map((field) => {
        const isSelected = field.id === selectedFieldId;
        const isHovered = field.id === hoveredFieldId;
        const status = isSelected ? 'selected' : (field.status || 'empty');
        const colors = COLORS[status];

        // Convert normalized coordinates to pixels
        const left = field.bbox.x * containerWidth;
        const top = field.bbox.y * containerHeight;
        const width = field.bbox.width * containerWidth;
        const height = field.bbox.height * containerHeight;

        const fieldStyle: CSSProperties = {
          position: 'absolute',
          left: `${left}px`,
          top: `${top}px`,
          width: `${width}px`,
          height: `${height}px`,
          backgroundColor: isHovered ? colors.hoverFill : colors.fill,
          border: `2px solid ${colors.stroke}`,
          borderRadius: '2px',
          cursor: 'pointer',
          pointerEvents: 'auto',
          transition: 'background-color 0.15s ease, border-color 0.15s ease',
          boxSizing: 'border-box',
        };

        const tooltipStyle: CSSProperties = {
          position: 'absolute',
          bottom: 'calc(100% + 4px)',
          left: '50%',
          transform: 'translateX(-50%)',
          backgroundColor: 'rgba(17, 24, 39, 0.95)',
          color: 'white',
          padding: '6px 10px',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: 500,
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          zIndex: 20,
          maxWidth: '200px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        };

        const arrowStyle: CSSProperties = {
          position: 'absolute',
          top: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: 0,
          height: 0,
          borderLeft: '6px solid transparent',
          borderRight: '6px solid transparent',
          borderTop: '6px solid rgba(17, 24, 39, 0.95)',
        };

        const indicatorStyle: CSSProperties = {
          position: 'absolute',
          top: '-6px',
          right: '-6px',
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          backgroundColor: status === 'empty' ? '#fbbf24' : status === 'error' ? '#ef4444' : '#22c55e',
          border: '2px solid white',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
        };

        // Use custom font style if available, otherwise fallback to dynamic sizing
        const fontStyle = field.fontStyle;
        const defaultFontSize = Math.max(8, Math.min(14, height * 0.7));

        // Map font families to web-safe equivalents
        const fontFamilyMap: Record<string, string> = {
          'Helvetica': 'Helvetica, Arial, sans-serif',
          'Times': 'Times New Roman, Times, serif',
          'Courier': 'Courier New, Courier, monospace',
        };

        // Map alignment to CSS textAlign
        const alignmentMap: Record<string, CSSProperties['textAlign']> = {
          'left': 'left',
          'center': 'center',
          'right': 'right',
        };

        const valueStyle: CSSProperties = {
          position: 'absolute',
          top: '50%',
          left: '4px',
          right: '4px',
          transform: 'translateY(-50%)',
          fontSize: fontStyle?.fontSize ? `${fontStyle.fontSize}px` : `${defaultFontSize}px`,
          fontFamily: fontStyle?.fontFamily
            ? fontFamilyMap[fontStyle.fontFamily] || 'system-ui, -apple-system, sans-serif'
            : 'system-ui, -apple-system, sans-serif',
          color: fontStyle?.fontColor || '#1f2937',
          textAlign: fontStyle?.alignment
            ? alignmentMap[fontStyle.alignment] || 'left'
            : 'left',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          lineHeight: 1.2,
        };

        return (
          <div
            key={field.id}
            style={fieldStyle}
            onClick={(e) => handleClick(e, field)}
            onMouseEnter={() => handleMouseEnter(field.id)}
            onMouseLeave={handleMouseLeave}
            role="button"
            tabIndex={0}
            aria-label={`Edit field: ${field.label}`}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const rect = (e.target as HTMLElement).getBoundingClientRect();
                onFieldClick(field.id, {
                  x: rect.left + rect.width / 2,
                  y: rect.bottom + 8,
                });
              }
            }}
          >
            {/* Display field value inside the box */}
            {field.value && (
              <div style={valueStyle}>{field.value}</div>
            )}

            {/* Status indicator dot */}
            {!isSelected && (field.status === 'empty' || field.status === 'error' || field.required) && (
              <div style={indicatorStyle} />
            )}

            {/* Tooltip on hover */}
            {showLabels && isHovered && !isSelected && (
              <div style={tooltipStyle}>
                <span>{field.label}</span>
                {field.value && (
                  <span style={{ color: '#9ca3af', marginLeft: '4px' }}>
                    : {field.value.length > 20 ? field.value.substring(0, 20) + '...' : field.value}
                  </span>
                )}
                <div style={arrowStyle} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Simple overlay for a single field (for use when editing).
 */
export interface SingleFieldHighlightProps {
  /** Bounding box (normalized 0-1 coordinates) */
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  /** Container width in pixels */
  containerWidth: number;
  /** Container height in pixels */
  containerHeight: number;
  /** Color variant */
  variant?: 'selected' | 'editing';
}

export function SingleFieldHighlight({
  bbox,
  containerWidth,
  containerHeight,
  variant = 'selected',
}: SingleFieldHighlightProps) {
  const colors = variant === 'editing'
    ? { fill: 'rgba(139, 92, 246, 0.25)', stroke: 'rgba(139, 92, 246, 1)' }
    : COLORS.selected;

  const left = bbox.x * containerWidth;
  const top = bbox.y * containerHeight;
  const width = bbox.width * containerWidth;
  const height = bbox.height * containerHeight;

  const style: CSSProperties = {
    position: 'absolute',
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
    backgroundColor: colors.fill,
    border: `2px solid ${colors.stroke}`,
    borderRadius: '2px',
    pointerEvents: 'none',
    zIndex: 15,
    boxSizing: 'border-box',
    animation: variant === 'editing' ? 'pulse 1.5s ease-in-out infinite' : undefined,
  };

  return (
    <>
      {variant === 'editing' && (
        <style>
          {`
            @keyframes pulse {
              0%, 100% { opacity: 1; }
              50% { opacity: 0.6; }
            }
          `}
        </style>
      )}
      <div style={style} />
    </>
  );
}
