/**
 * Card component for content containers.
 */

import type { ReactNode, CSSProperties } from 'react';

export interface CardProps {
  children: ReactNode;
  title?: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  style?: CSSProperties;
  headerStyle?: CSSProperties;
  bodyStyle?: CSSProperties;
}

const paddingStyles: Record<string, CSSProperties> = {
  none: { padding: 0 },
  sm: { padding: '12px' },
  md: { padding: '16px' },
  lg: { padding: '24px' },
};

export function Card({
  children,
  title,
  subtitle,
  actions,
  padding = 'md',
  style,
  headerStyle,
  bodyStyle,
}: CardProps) {
  const hasHeader = title || subtitle || actions;

  const cardStyles: CSSProperties = {
    backgroundColor: 'white',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
    overflow: 'hidden',
    ...style,
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '12px',
    padding: '16px',
    borderBottom: hasHeader ? '1px solid #e5e7eb' : 'none',
    ...headerStyle,
  };

  const bodyStyles: CSSProperties = {
    ...paddingStyles[padding],
    ...bodyStyle,
  };

  return (
    <div style={cardStyles}>
      {hasHeader && (
        <div style={headerStyles}>
          <div>
            {title && (
              <h3
                style={{
                  margin: 0,
                  fontSize: '16px',
                  fontWeight: 600,
                  color: '#111827',
                }}
              >
                {title}
              </h3>
            )}
            {subtitle && (
              <p
                style={{
                  margin: title ? '4px 0 0 0' : 0,
                  fontSize: '13px',
                  color: '#6b7280',
                }}
              >
                {subtitle}
              </p>
            )}
          </div>
          {actions && <div style={{ display: 'flex', gap: '8px' }}>{actions}</div>}
        </div>
      )}
      <div style={bodyStyles}>{children}</div>
    </div>
  );
}

/**
 * Simple section divider for cards.
 */
export function CardDivider() {
  return (
    <div
      style={{
        height: '1px',
        backgroundColor: '#e5e7eb',
        margin: '16px 0',
      }}
    />
  );
}
