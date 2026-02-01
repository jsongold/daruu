/**
 * Template preview card component.
 * Shows template name, preview image, field count, and similarity score.
 */

import type { CSSProperties } from 'react';
import type { TemplateMatch } from '../../api/templateClient';

export interface TemplatePreviewProps {
  /** Template match data */
  match: TemplateMatch;
  /** Whether this template is selected */
  isSelected?: boolean;
  /** Click handler */
  onClick?: () => void;
}

/**
 * Format similarity score as percentage.
 */
function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Get color based on similarity score.
 */
function getScoreColor(score: number): string {
  if (score >= 0.9) {
    return '#059669'; // Green
  }
  if (score >= 0.7) {
    return '#d97706'; // Amber
  }
  return '#6b7280'; // Gray
}

/**
 * Get background color based on similarity score.
 */
function getScoreBgColor(score: number): string {
  if (score >= 0.9) {
    return '#d1fae5'; // Light green
  }
  if (score >= 0.7) {
    return '#fef3c7'; // Light amber
  }
  return '#f3f4f6'; // Light gray
}

export function TemplatePreview({
  match,
  isSelected = false,
  onClick,
}: TemplatePreviewProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    border: isSelected ? '2px solid #3b82f6' : '1px solid #e5e7eb',
    borderRadius: '8px',
    overflow: 'hidden',
    backgroundColor: isSelected ? '#eff6ff' : 'white',
    cursor: onClick ? 'pointer' : 'default',
    transition: 'all 0.15s ease',
    width: '100%',
    maxWidth: '200px',
  };

  const imageContainerStyle: CSSProperties = {
    position: 'relative',
    width: '100%',
    height: '120px',
    backgroundColor: '#f9fafb',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  };

  const imageStyle: CSSProperties = {
    maxWidth: '100%',
    maxHeight: '100%',
    objectFit: 'contain',
  };

  const placeholderStyle: CSSProperties = {
    color: '#9ca3af',
    fontSize: '12px',
    textAlign: 'center',
    padding: '8px',
  };

  const scoreBadgeStyle: CSSProperties = {
    position: 'absolute',
    top: '8px',
    right: '8px',
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 600,
    backgroundColor: getScoreBgColor(match.similarity_score),
    color: getScoreColor(match.similarity_score),
  };

  const contentStyle: CSSProperties = {
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  };

  const nameStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 500,
    color: '#1f2937',
    margin: 0,
    lineHeight: 1.3,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const fieldCountStyle: CSSProperties = {
    fontSize: '12px',
    color: '#6b7280',
    margin: 0,
  };

  return (
    <div
      style={containerStyle}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div style={imageContainerStyle}>
        {match.preview_url ? (
          <img
            src={match.preview_url}
            alt={`Preview of ${match.template_name}`}
            style={imageStyle}
          />
        ) : (
          <div style={placeholderStyle}>
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div>No preview</div>
          </div>
        )}
        <span style={scoreBadgeStyle}>
          {formatScore(match.similarity_score)} match
        </span>
      </div>
      <div style={contentStyle}>
        <h4 style={nameStyle} title={match.template_name}>
          {match.template_name}
        </h4>
        <p style={fieldCountStyle}>
          {match.field_count} {match.field_count === 1 ? 'field' : 'fields'}
        </p>
      </div>
    </div>
  );
}
