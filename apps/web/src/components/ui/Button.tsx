/**
 * Button component with variants.
 */

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'link';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  fullWidth?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: `
    background-color: #3b82f6;
    color: white;
    border: none;
  `,
  secondary: `
    background-color: #f3f4f6;
    color: #374151;
    border: 1px solid #d1d5db;
  `,
  danger: `
    background-color: #ef4444;
    color: white;
    border: none;
  `,
  ghost: `
    background-color: transparent;
    color: #374151;
    border: none;
  `,
  link: `
    background-color: transparent;
    color: #3b82f6;
    border: none;
    padding: 0;
    text-decoration: underline;
  `,
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: `
    padding: 6px 12px;
    font-size: 13px;
    border-radius: 4px;
  `,
  md: `
    padding: 8px 16px;
    font-size: 14px;
    border-radius: 6px;
  `,
  lg: `
    padding: 12px 24px;
    font-size: 16px;
    border-radius: 8px;
  `,
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      leftIcon,
      rightIcon,
      fullWidth = false,
      disabled,
      children,
      style,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    const baseStyles: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      fontWeight: 500,
      cursor: isDisabled ? 'not-allowed' : 'pointer',
      opacity: isDisabled ? 0.6 : 1,
      transition: 'all 0.15s ease',
      width: fullWidth ? '100%' : 'auto',
    };

    // Parse CSS strings to objects
    const variantCss = variantStyles[variant]
      .trim()
      .split('\n')
      .filter(Boolean)
      .reduce<Record<string, string>>((acc, line) => {
        const [key, value] = line.split(':').map((s) => s.trim().replace(';', ''));
        if (key && value) {
          const camelKey = key.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
          acc[camelKey] = value;
        }
        return acc;
      }, {});

    const sizeCss = sizeStyles[size]
      .trim()
      .split('\n')
      .filter(Boolean)
      .reduce<Record<string, string>>((acc, line) => {
        const [key, value] = line.split(':').map((s) => s.trim().replace(';', ''));
        if (key && value) {
          const camelKey = key.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
          acc[camelKey] = value;
        }
        return acc;
      }, {});

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        style={{
          ...baseStyles,
          ...variantCss,
          ...sizeCss,
          ...style,
        }}
        {...props}
      >
        {loading && <LoadingSpinner size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />}
        {!loading && leftIcon}
        {children}
        {!loading && rightIcon}
      </button>
    );
  }
);

Button.displayName = 'Button';

function LoadingSpinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      style={{
        animation: 'spin 1s linear infinite',
      }}
    >
      <style>
        {`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}
      </style>
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
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
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="31.4 31.4"
        strokeDashoffset="23.55"
      />
    </svg>
  );
}
