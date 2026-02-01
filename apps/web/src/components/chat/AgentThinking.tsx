/**
 * Agent thinking indicator component.
 * Shows the current processing stage with an animated indicator.
 */

import type { CSSProperties } from 'react';
import type { AgentStage } from '../../lib/api-types';
import { LoadingSpinner } from '../ui/LoadingState';

export interface AgentThinkingProps {
  stage: AgentStage;
  message?: string;
}

const stageLabels: Record<AgentStage, string> = {
  idle: 'Ready',
  analyzing: 'Analyzing documents...',
  confirming: 'Confirming document roles...',
  mapping: 'Mapping fields...',
  filling: 'Filling form...',
  reviewing: 'Reviewing results...',
  complete: 'Complete',
  error: 'Error occurred',
};

const stageDescriptions: Record<AgentStage, string> = {
  idle: '',
  analyzing: 'Understanding the structure and rules of your documents',
  confirming: 'Identifying which document is the form and which are sources',
  mapping: 'Matching source data to form fields',
  filling: 'Applying values to the form',
  reviewing: 'Checking for any issues or missing information',
  complete: 'Your form is ready',
  error: 'Something went wrong',
};

function StageIndicator({ stage }: { stage: AgentStage }) {
  const isActive = stage !== 'idle' && stage !== 'complete' && stage !== 'error';
  const isError = stage === 'error';
  const isComplete = stage === 'complete';

  const indicatorStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    backgroundColor: isError ? '#fee2e2' : isComplete ? '#d1fae5' : '#eff6ff',
  };

  if (isActive) {
    return (
      <div style={indicatorStyle}>
        <LoadingSpinner size={18} color="#3b82f6" />
      </div>
    );
  }

  if (isComplete) {
    return (
      <div style={indicatorStyle}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
    );
  }

  if (isError) {
    return (
      <div style={indicatorStyle}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2.5">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </div>
    );
  }

  return (
    <div style={indicatorStyle}>
      <div
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: '#9ca3af',
        }}
      />
    </div>
  );
}

export function AgentThinking({ stage, message }: AgentThinkingProps) {
  const isVisible = stage !== 'idle';

  if (!isVisible) {
    return null;
  }

  const containerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
    padding: '16px',
    backgroundColor: '#f9fafb',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
    maxWidth: '75%',
    alignSelf: 'flex-start',
  };

  const contentStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  };

  const labelStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 500,
    color: stage === 'error' ? '#dc2626' : stage === 'complete' ? '#059669' : '#1f2937',
  };

  const descriptionStyle: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
  };

  const displayMessage = message || stageDescriptions[stage];

  return (
    <div style={containerStyle}>
      <StageIndicator stage={stage} />
      <div style={contentStyle}>
        <span style={labelStyle}>{stageLabels[stage]}</span>
        {displayMessage && <span style={descriptionStyle}>{displayMessage}</span>}
      </div>
    </div>
  );
}

/**
 * Compact version of the thinking indicator for inline use.
 */
export function AgentThinkingCompact({ stage, message }: AgentThinkingProps) {
  const isVisible = stage !== 'idle' && stage !== 'complete';

  if (!isVisible) {
    return null;
  }

  const containerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    backgroundColor: '#eff6ff',
    borderRadius: '20px',
    fontSize: '13px',
    color: '#1e40af',
  };

  return (
    <div style={containerStyle}>
      <LoadingSpinner size={14} color="#3b82f6" />
      <span>{message || stageLabels[stage]}</span>
    </div>
  );
}
