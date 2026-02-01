/**
 * Loading and empty state components.
 */

import type { ReactNode, CSSProperties } from 'react';

export interface LoadingSpinnerProps {
  size?: number;
  color?: string;
  style?: CSSProperties;
}

export function LoadingSpinner({
  size = 24,
  color = '#3b82f6',
  style,
}: LoadingSpinnerProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      style={{
        animation: 'spin 1s linear infinite',
        ...style,
      }}
    >
      <style>
        {`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}
      </style>
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="31.4 31.4"
        strokeDashoffset="0"
        opacity="0.25"
      />
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="31.4 31.4"
        strokeDashoffset="23.55"
      />
    </svg>
  );
}

export interface LoadingOverlayProps {
  message?: string;
}

export function LoadingOverlay({ message = 'Loading...' }: LoadingOverlayProps) {
  const overlayStyles: CSSProperties = {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    zIndex: 1000,
  };

  return (
    <div style={overlayStyles}>
      <LoadingSpinner size={40} />
      <p style={{ margin: 0, color: '#374151', fontSize: '14px' }}>{message}</p>
    </div>
  );
}

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  style?: CSSProperties;
}

export function Skeleton({
  width = '100%',
  height = '20px',
  borderRadius = '4px',
  style,
}: SkeletonProps) {
  const skeletonStyles: CSSProperties = {
    width,
    height,
    borderRadius,
    backgroundColor: '#e5e7eb',
    animation: 'pulse 1.5s ease-in-out infinite',
    ...style,
  };

  return (
    <>
      <style>
        {`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }`}
      </style>
      <div style={skeletonStyles} />
    </>
  );
}

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  style?: CSSProperties;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  style,
}: EmptyStateProps) {
  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px 24px',
    textAlign: 'center',
    ...style,
  };

  return (
    <div style={containerStyles}>
      {icon && (
        <div
          style={{
            marginBottom: '16px',
            color: '#9ca3af',
            fontSize: '48px',
          }}
        >
          {icon}
        </div>
      )}
      <h3
        style={{
          margin: 0,
          fontSize: '18px',
          fontWeight: 600,
          color: '#374151',
        }}
      >
        {title}
      </h3>
      {description && (
        <p
          style={{
            margin: '8px 0 0 0',
            fontSize: '14px',
            color: '#6b7280',
            maxWidth: '400px',
          }}
        >
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: '24px' }}>{action}</div>}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  style?: CSSProperties;
}

export function ErrorState({
  title = 'Error',
  message,
  onRetry,
  style,
}: ErrorStateProps) {
  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    textAlign: 'center',
    backgroundColor: '#fee2e2',
    borderRadius: '8px',
    border: '1px solid #fecaca',
    ...style,
  };

  return (
    <div style={containerStyles}>
      <div
        style={{
          marginBottom: '12px',
          fontSize: '32px',
        }}
      >
        !!
      </div>
      <h3
        style={{
          margin: 0,
          fontSize: '16px',
          fontWeight: 600,
          color: '#991b1b',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          margin: '8px 0 0 0',
          fontSize: '14px',
          color: '#b91c1c',
        }}
      >
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: '16px',
            padding: '8px 16px',
            fontSize: '14px',
            fontWeight: 500,
            backgroundColor: 'white',
            color: '#991b1b',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          Try Again
        </button>
      )}
    </div>
  );
}
