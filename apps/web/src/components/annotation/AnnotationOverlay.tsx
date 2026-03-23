/**
 * Overlay for annotation tool.
 * Renders labels and fields based on OverlayConfig from the store.
 */

import { useState, useCallback, type CSSProperties, type MouseEvent } from 'react';
import type { OverlayConfig, LabelColorKey, FieldColorKey } from '../../types/annotation';

interface AnnotationOverlayProps {
  config: OverlayConfig;
  onLabelClick: (labelId: string) => void;
  onFieldClick: (fieldId: string) => void;
  containerWidth: number;
  containerHeight: number;
}

const LABEL_COLORS: Record<LabelColorKey, { fill: string; stroke: string; hoverFill: string }> = {
  default: {
    fill: 'rgba(147, 197, 253, 0.25)',
    stroke: 'rgba(147, 197, 253, 0.0)',
    hoverFill: 'rgba(147, 197, 253, 0.45)',
  },
  paired: {
    fill: 'rgba(252, 165, 165, 0.3)',
    stroke: 'rgba(239, 68, 68, 0.5)',
    hoverFill: 'rgba(252, 165, 165, 0.5)',
  },
  focused: {
    fill: 'rgba(251, 191, 36, 0.35)',
    stroke: 'rgba(245, 158, 11, 1)',
    hoverFill: 'rgba(251, 191, 36, 0.5)',
  },
};

const FIELD_COLORS: Record<FieldColorKey, { fill: string; stroke: string; hoverFill: string }> = {
  default: {
    fill: 'rgba(251, 191, 36, 0.15)',
    stroke: 'rgba(251, 191, 36, 0.7)',
    hoverFill: 'rgba(251, 191, 36, 0.3)',
  },
  paired: {
    fill: 'rgba(134, 239, 172, 0.2)',
    stroke: 'rgba(34, 197, 94, 0.7)',
    hoverFill: 'rgba(134, 239, 172, 0.35)',
  },
};

function OverlayRect({
  bbox,
  label,
  colors,
  isHovered,
  isFocused,
  borderWidth,
  containerWidth,
  containerHeight,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: {
  bbox: { x: number; y: number; width: number; height: number };
  label: string;
  colors: { fill: string; stroke: string; hoverFill: string };
  isHovered: boolean;
  isFocused: boolean;
  borderWidth: number;
  containerWidth: number;
  containerHeight: number;
  onClick: (e: MouseEvent<HTMLDivElement>) => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
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
    backgroundColor: isHovered ? colors.hoverFill : colors.fill,
    border: borderWidth > 0 ? `${borderWidth}px solid ${colors.stroke}` : 'none',
    borderRadius: '2px',
    cursor: 'pointer',
    pointerEvents: 'auto',
    transition: 'background-color 0.15s ease',
    boxSizing: 'border-box',
    ...(isFocused ? { boxShadow: '0 0 0 2px rgba(245, 158, 11, 0.6)' } : {}),
  };

  return (
    <div
      style={style}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      role="button"
      tabIndex={0}
      aria-label={label}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(e as unknown as MouseEvent<HTMLDivElement>);
        }
      }}
    >
      {(isHovered || isFocused) && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 4px)',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'rgba(17, 24, 39, 0.95)',
            color: 'white',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 500,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            zIndex: 20,
            maxWidth: '200px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {label}
        </div>
      )}
    </div>
  );
}

export function AnnotationOverlay({
  config,
  onLabelClick,
  onFieldClick,
  containerWidth,
  containerHeight,
}: AnnotationOverlayProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const handleLabelClick = useCallback(
    (e: MouseEvent<HTMLDivElement>, labelId: string) => {
      e.stopPropagation();
      onLabelClick(labelId);
    },
    [onLabelClick]
  );

  const handleFieldClick = useCallback(
    (e: MouseEvent<HTMLDivElement>, fieldId: string) => {
      e.stopPropagation();
      onFieldClick(fieldId);
    },
    [onFieldClick]
  );

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    >
      {config.labels.map(({ overlay, colorKey }) => {
        const colors = LABEL_COLORS[colorKey];
        const isFocused = colorKey === 'focused';
        const isPaired = colorKey === 'paired';

        return (
          <OverlayRect
            key={overlay.id}
            bbox={overlay.bbox}
            label={overlay.text}
            colors={colors}
            isHovered={hoveredId === overlay.id}
            isFocused={isFocused}
            borderWidth={isFocused ? 2 : isPaired ? 1 : 0}
            containerWidth={containerWidth}
            containerHeight={containerHeight}
            onClick={(e) => handleLabelClick(e, overlay.id)}
            onMouseEnter={() => setHoveredId(overlay.id)}
            onMouseLeave={() => setHoveredId(null)}
          />
        );
      })}

      {config.fields.map(({ overlay, colorKey }) => {
        const colors = FIELD_COLORS[colorKey];

        return (
          <OverlayRect
            key={overlay.id}
            bbox={overlay.bbox}
            label={`Field: ${overlay.fieldName}`}
            colors={colors}
            isHovered={hoveredId === overlay.id}
            isFocused={false}
            borderWidth={2}
            containerWidth={containerWidth}
            containerHeight={containerHeight}
            onClick={(e) => handleFieldClick(e, overlay.id)}
            onMouseEnter={() => setHoveredId(overlay.id)}
            onMouseLeave={() => setHoveredId(null)}
          />
        );
      })}
    </div>
  );
}
