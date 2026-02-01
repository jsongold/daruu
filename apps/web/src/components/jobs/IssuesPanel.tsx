/**
 * Issues panel for displaying and managing job issues.
 */

import { useMemo, type CSSProperties } from 'react';
import type { Issue, IssueSeverity } from '../../types/api';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/LoadingState';
import { getSeverityColor } from '../../utils/format';

export interface IssuesPanelProps {
  issues: Issue[];
  onIssueClick?: (issue: Issue) => void;
  showFieldLink?: boolean;
}

export function IssuesPanel({ issues, onIssueClick, showFieldLink = true }: IssuesPanelProps) {
  const sortedIssues = useMemo(() => {
    const severityOrder: Record<IssueSeverity, number> = {
      critical: 0,
      error: 1,
      high: 2,
      warning: 3,
      info: 4,
    };

    return [...issues].sort(
      (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
    );
  }, [issues]);

  const stats = useMemo(() => {
    const critical = issues.filter(
      (i) => i.severity === 'critical' || i.severity === 'error' || i.severity === 'high'
    ).length;
    const warnings = issues.filter((i) => i.severity === 'warning').length;
    const info = issues.filter((i) => i.severity === 'info').length;
    return { critical, warnings, info, total: issues.length };
  }, [issues]);

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  };

  const summaryStyles: CSSProperties = {
    display: 'flex',
    gap: '12px',
    padding: '12px',
    backgroundColor: '#f9fafb',
    borderRadius: '6px',
  };

  const summaryItemStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '13px',
  };

  const listStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  };

  return (
    <Card
      title="Issues"
      subtitle={`${stats.total} issue${stats.total !== 1 ? 's' : ''} found`}
      padding="md"
    >
      {issues.length === 0 ? (
        <EmptyState
          title="No issues"
          description="All fields look good!"
          style={{ padding: '24px 0' }}
        />
      ) : (
        <div style={containerStyles}>
          <div style={summaryStyles}>
            {stats.critical > 0 && (
              <div style={summaryItemStyles}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: '#ef4444',
                  }}
                />
                <span style={{ color: '#ef4444', fontWeight: 500 }}>
                  {stats.critical} Critical
                </span>
              </div>
            )}
            {stats.warnings > 0 && (
              <div style={summaryItemStyles}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: '#f59e0b',
                  }}
                />
                <span style={{ color: '#f59e0b', fontWeight: 500 }}>
                  {stats.warnings} Warning{stats.warnings !== 1 ? 's' : ''}
                </span>
              </div>
            )}
            {stats.info > 0 && (
              <div style={summaryItemStyles}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: '#3b82f6',
                  }}
                />
                <span style={{ color: '#3b82f6', fontWeight: 500 }}>
                  {stats.info} Info
                </span>
              </div>
            )}
          </div>

          <div style={listStyles}>
            {sortedIssues.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                onClick={onIssueClick ? () => onIssueClick(issue) : undefined}
                showFieldLink={showFieldLink}
              />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

interface IssueCardProps {
  issue: Issue;
  onClick?: () => void;
  showFieldLink?: boolean;
}

function IssueCard({ issue, onClick, showFieldLink = true }: IssueCardProps) {
  const severityColor = getSeverityColor(issue.severity);

  const cardStyles: CSSProperties = {
    padding: '12px',
    borderRadius: '6px',
    borderLeft: `3px solid ${severityColor}`,
    backgroundColor: severityColor + '10',
    cursor: onClick ? 'pointer' : 'default',
    transition: 'background-color 0.15s ease',
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '12px',
    marginBottom: '8px',
  };

  const typeStyles: CSSProperties = {
    fontSize: '11px',
    fontWeight: 500,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.025em',
  };

  const messageStyles: CSSProperties = {
    fontSize: '14px',
    color: '#374151',
    lineHeight: 1.5,
  };

  const actionStyles: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
    marginTop: '8px',
    paddingTop: '8px',
    borderTop: '1px solid ' + severityColor + '30',
  };

  const severityBadgeVariant =
    issue.severity === 'critical' || issue.severity === 'error' || issue.severity === 'high'
      ? 'danger'
      : issue.severity === 'warning'
      ? 'warning'
      : 'info';

  return (
    <div style={cardStyles} onClick={onClick} role={onClick ? 'button' : undefined}>
      <div style={headerStyles}>
        <span style={typeStyles}>{issue.issue_type.replace(/_/g, ' ')}</span>
        <Badge variant={severityBadgeVariant} size="sm">
          {issue.severity}
        </Badge>
      </div>
      <p style={messageStyles}>{issue.message}</p>
      {issue.suggested_action && (
        <div style={actionStyles}>
          <strong>Suggestion:</strong> {issue.suggested_action}
        </div>
      )}
      {showFieldLink && issue.field_id && (
        <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '8px' }}>
          Field: {issue.field_id.slice(0, 8)}...
        </div>
      )}
    </div>
  );
}

/**
 * Compact issues summary for headers.
 */
export function IssuesSummary({ issues }: { issues: Issue[] }) {
  const criticalCount = issues.filter(
    (i) => i.severity === 'critical' || i.severity === 'error' || i.severity === 'high'
  ).length;
  const warningCount = issues.filter((i) => i.severity === 'warning').length;

  if (issues.length === 0) {
    return (
      <Badge variant="success" size="sm">
        No Issues
      </Badge>
    );
  }

  const summaryStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  return (
    <div style={summaryStyles}>
      {criticalCount > 0 && (
        <Badge variant="danger" size="sm">
          {criticalCount} Critical
        </Badge>
      )}
      {warningCount > 0 && (
        <Badge variant="warning" size="sm">
          {warningCount} Warning{warningCount !== 1 ? 's' : ''}
        </Badge>
      )}
    </div>
  );
}
