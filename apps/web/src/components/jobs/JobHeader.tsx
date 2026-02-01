/**
 * Job header component with status, progress, and actions.
 */

import { type CSSProperties } from 'react';
import type { JobContext, RunMode } from '../../types/api';
import { StatusBadge, Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { formatRelativeTime, truncateId, formatCost } from '../../utils/format';

export interface JobHeaderProps {
  job: JobContext;
  onRun?: (mode: RunMode) => void;
  onDownload?: () => void;
  onExport?: () => void;
  isRunning?: boolean;
  pendingAnswers?: number;
  onSubmitAnswers?: () => void;
}

export function JobHeader({
  job,
  onRun,
  onDownload,
  onExport,
  isRunning = false,
  pendingAnswers = 0,
  onSubmitAnswers,
}: JobHeaderProps) {
  const canRun = job.next_actions.includes('run') && job.status !== 'running';
  const canDownload = job.status === 'done';
  const needsInput = job.status === 'awaiting_input' || job.status === 'blocked';

  const containerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    padding: '20px 24px',
    backgroundColor: 'white',
    borderBottom: '1px solid #e5e7eb',
    gap: '24px',
  };

  const infoStyles: CSSProperties = {
    flex: 1,
    minWidth: 0,
  };

  const titleRowStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '8px',
  };

  const titleStyles: CSSProperties = {
    fontSize: '20px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  };

  const metaStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    fontSize: '13px',
    color: '#6b7280',
    marginBottom: '12px',
  };

  const progressContainerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  };

  const progressBarStyles: CSSProperties = {
    flex: 1,
    height: '8px',
    backgroundColor: '#e5e7eb',
    borderRadius: '4px',
    overflow: 'hidden',
    maxWidth: '300px',
  };

  const progressFillStyles: CSSProperties = {
    height: '100%',
    backgroundColor: job.status === 'done' ? '#22c55e' : '#3b82f6',
    borderRadius: '4px',
    transition: 'width 0.3s ease',
    width: `${job.progress * 100}%`,
  };

  const actionsStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexShrink: 0,
  };

  const stageStyles: CSSProperties = {
    fontSize: '12px',
    color: '#6b7280',
    padding: '4px 8px',
    backgroundColor: '#f3f4f6',
    borderRadius: '4px',
  };

  return (
    <div style={containerStyles}>
      <div style={infoStyles}>
        <div style={titleRowStyles}>
          <h1 style={titleStyles}>Job: {truncateId(job.id)}</h1>
          <StatusBadge status={job.status} />
          <Badge variant="default" size="sm">
            {job.mode.toUpperCase()}
          </Badge>
        </div>

        <div style={metaStyles}>
          <span>Created {formatRelativeTime(job.created_at)}</span>
          <span>|</span>
          <span>Updated {formatRelativeTime(job.updated_at)}</span>
          {job.cost && (
            <>
              <span>|</span>
              <span>Cost: {formatCost(job.cost.estimated_cost_usd)}</span>
            </>
          )}
          <span>|</span>
          <span>Iteration: {job.iteration_count}</span>
        </div>

        <div style={progressContainerStyles}>
          <div style={progressBarStyles}>
            <div style={progressFillStyles} />
          </div>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151', minWidth: '45px' }}>
            {Math.round(job.progress * 100)}%
          </span>
          {job.current_stage && <span style={stageStyles}>{job.current_stage}</span>}
        </div>
      </div>

      <div style={actionsStyles}>
        {needsInput && pendingAnswers > 0 && onSubmitAnswers && (
          <Button
            variant="primary"
            onClick={onSubmitAnswers}
            disabled={isRunning}
          >
            Submit Answers ({pendingAnswers})
          </Button>
        )}

        {canRun && onRun && (
          <>
            <Button
              variant="secondary"
              onClick={() => onRun('step')}
              disabled={isRunning}
              loading={isRunning}
            >
              Step
            </Button>
            <Button
              variant="primary"
              onClick={() => onRun('until_blocked')}
              disabled={isRunning}
              loading={isRunning}
            >
              Run
            </Button>
          </>
        )}

        {needsInput && onRun && (
          <Button
            variant="secondary"
            onClick={() => onRun('until_blocked')}
            disabled={isRunning}
            loading={isRunning}
          >
            Continue
          </Button>
        )}

        {job.status === 'running' && (
          <Button variant="secondary" disabled loading>
            Running...
          </Button>
        )}

        {canDownload && onDownload && (
          <Button variant="primary" onClick={onDownload}>
            Download PDF
          </Button>
        )}

        {onExport && (
          <Button variant="ghost" onClick={onExport}>
            Export JSON
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * Compact job status indicator.
 */
export function JobStatusIndicator({ job }: { job: JobContext }) {
  const indicatorStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    backgroundColor: '#f9fafb',
    borderRadius: '6px',
    fontSize: '13px',
  };

  return (
    <div style={indicatorStyles}>
      <StatusBadge status={job.status} size="sm" />
      <span style={{ color: '#6b7280' }}>
        {Math.round(job.progress * 100)}%
      </span>
      {job.current_stage && (
        <span style={{ color: '#374151', fontWeight: 500 }}>
          {job.current_stage}
        </span>
      )}
    </div>
  );
}
