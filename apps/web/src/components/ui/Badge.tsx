/**
 * Badge component for status indicators.
 */

import type { ReactNode, CSSProperties } from 'react';
import { getStatusColor, getStatusBgColor } from '../../utils/format';

export type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'status';
export type BadgeSize = 'sm' | 'md';

export interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  /** For status variant, pass the status string */
  status?: string;
  style?: CSSProperties;
}

const variantColors: Record<BadgeVariant, { bg: string; text: string }> = {
  default: { bg: '#f3f4f6', text: '#374151' },
  success: { bg: '#dcfce7', text: '#166534' },
  warning: { bg: '#fef3c7', text: '#92400e' },
  danger: { bg: '#fee2e2', text: '#991b1b' },
  info: { bg: '#dbeafe', text: '#1e40af' },
  status: { bg: '#f3f4f6', text: '#374151' }, // Will be overridden
};

const sizeStyles: Record<BadgeSize, CSSProperties> = {
  sm: {
    padding: '2px 6px',
    fontSize: '11px',
    borderRadius: '4px',
  },
  md: {
    padding: '4px 10px',
    fontSize: '12px',
    borderRadius: '6px',
  },
};

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  status,
  style,
}: BadgeProps) {
  let colors = variantColors[variant];

  // Override for status variant
  if (variant === 'status' && status) {
    colors = {
      bg: getStatusBgColor(status),
      text: getStatusColor(status),
    };
  }

  const baseStyles: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    fontWeight: 500,
    textTransform: 'uppercase',
    letterSpacing: '0.025em',
    whiteSpace: 'nowrap',
    backgroundColor: colors.bg,
    color: colors.text,
    ...sizeStyles[size],
    ...style,
  };

  return <span style={baseStyles}>{children}</span>;
}

/**
 * Status badge with automatic coloring.
 */
export function StatusBadge({
  status,
  size = 'md',
  style,
}: {
  status: string;
  size?: BadgeSize;
  style?: CSSProperties;
}) {
  const displayStatus = status.replace(/_/g, ' ');

  return (
    <Badge variant="status" status={status} size={size} style={style}>
      {displayStatus}
    </Badge>
  );
}

/**
 * Confidence badge with color coding.
 */
export function ConfidenceBadge({
  confidence,
  size = 'md',
  showPercent = true,
  style,
}: {
  confidence: number | null;
  size?: BadgeSize;
  showPercent?: boolean;
  style?: CSSProperties;
}) {
  if (confidence === null) {
    return (
      <Badge variant="default" size={size} style={style}>
        N/A
      </Badge>
    );
  }

  let variant: BadgeVariant;
  if (confidence >= 0.8) {
    variant = 'success';
  } else if (confidence >= 0.5) {
    variant = 'warning';
  } else {
    variant = 'danger';
  }

  const display = showPercent
    ? `${(confidence * 100).toFixed(0)}%`
    : confidence.toFixed(2);

  return (
    <Badge variant={variant} size={size} style={style}>
      {display}
    </Badge>
  );
}
