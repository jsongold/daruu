/**
 * Template picker component.
 * Shows list of matched templates for user selection.
 */

import type { CSSProperties } from 'react';
import type { TemplateMatch } from '../../api/templateClient';
import { Button } from '../ui/Button';
import { TemplatePreview } from './TemplatePreview';

export interface TemplatePickerProps {
  /** List of template matches */
  matches: TemplateMatch[];
  /** Whether currently loading matches */
  isLoading?: boolean;
  /** Handler when a template is selected */
  onSelect: (templateId: string) => void;
  /** Handler when user skips template selection */
  onSkip: () => void;
  /** Optional title override */
  title?: string;
  /** Optional description override */
  description?: string;
}

function LoadingSpinner() {
  return (
    <svg
      width={24}
      height={24}
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
        stroke="#3b82f6"
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
        stroke="#3b82f6"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="31.4 31.4"
        strokeDashoffset="23.55"
      />
    </svg>
  );
}

export function TemplatePicker({
  matches,
  isLoading = false,
  onSelect,
  onSkip,
  title = 'Select a template',
  description = 'We found templates that match your document. Select one to speed up the process.',
}: TemplatePickerProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    padding: '16px',
    backgroundColor: '#f9fafb',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
    maxWidth: '100%',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  };

  const titleStyle: CSSProperties = {
    fontSize: '16px',
    fontWeight: 600,
    color: '#1f2937',
    margin: 0,
  };

  const descriptionStyle: CSSProperties = {
    fontSize: '14px',
    color: '#6b7280',
    margin: 0,
    lineHeight: 1.4,
  };

  const loadingContainerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '32px',
    gap: '12px',
  };

  const loadingTextStyle: CSSProperties = {
    fontSize: '14px',
    color: '#6b7280',
  };

  const gridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
    gap: '12px',
    maxHeight: '300px',
    overflowY: 'auto',
    padding: '4px',
  };

  const emptyStateStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    gap: '8px',
    textAlign: 'center',
  };

  const emptyIconStyle: CSSProperties = {
    color: '#9ca3af',
    marginBottom: '4px',
  };

  const emptyTitleStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
    margin: 0,
  };

  const emptyDescStyle: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
    margin: 0,
  };

  const actionsStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    paddingTop: '8px',
    borderTop: '1px solid #e5e7eb',
  };

  if (isLoading) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <h3 style={titleStyle}>{title}</h3>
        </div>
        <div style={loadingContainerStyle}>
          <LoadingSpinner />
          <span style={loadingTextStyle}>Finding matching templates...</span>
        </div>
      </div>
    );
  }

  const hasMatches = matches.length > 0;

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <h3 style={titleStyle}>{title}</h3>
        {hasMatches && <p style={descriptionStyle}>{description}</p>}
      </div>

      {hasMatches ? (
        <div style={gridStyle}>
          {matches.map((match) => (
            <TemplatePreview
              key={match.template_id}
              match={match}
              onClick={() => onSelect(match.template_id)}
            />
          ))}
        </div>
      ) : (
        <div style={emptyStateStyle}>
          <div style={emptyIconStyle}>
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              <path d="M12 3v6a1 1 0 001 1h6" />
            </svg>
          </div>
          <h4 style={emptyTitleStyle}>No matching templates found</h4>
          <p style={emptyDescStyle}>
            We will analyze this document from scratch to extract the form structure.
          </p>
        </div>
      )}

      <div style={actionsStyle}>
        <Button variant="ghost" size="sm" onClick={onSkip}>
          {hasMatches ? 'None of these - analyze fresh' : 'Continue without template'}
        </Button>
      </div>
    </div>
  );
}
