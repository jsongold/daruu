/**
 * Activity timeline component for job history.
 */

import { type CSSProperties } from 'react';
import type { Activity, ActivityAction } from '../../types/api';
import { Card } from '../ui/Card';
import { formatRelativeTime, formatDateTime } from '../../utils/format';

export interface ActivityTimelineProps {
  activities: Activity[];
  maxItems?: number;
  showTimestamp?: boolean;
}

const actionConfig: Record<
  ActivityAction,
  { icon: string; label: string; color: string }
> = {
  job_created: { icon: '+', label: 'Job Created', color: '#3b82f6' },
  job_started: { icon: '>', label: 'Job Started', color: '#3b82f6' },
  document_uploaded: { icon: '^', label: 'Document Uploaded', color: '#8b5cf6' },
  extraction_started: { icon: '*', label: 'Extraction Started', color: '#f59e0b' },
  extraction_completed: { icon: 'O', label: 'Extraction Completed', color: '#22c55e' },
  mapping_created: { icon: '-', label: 'Mapping Created', color: '#06b6d4' },
  field_extracted: { icon: 'F', label: 'Field Extracted', color: '#10b981' },
  question_asked: { icon: '?', label: 'Question Asked', color: '#f59e0b' },
  answer_received: { icon: 'A', label: 'Answer Received', color: '#22c55e' },
  field_edited: { icon: 'E', label: 'Field Edited', color: '#8b5cf6' },
  rendering_started: { icon: 'R', label: 'Rendering Started', color: '#f59e0b' },
  rendering_completed: { icon: 'D', label: 'Rendering Completed', color: '#22c55e' },
  job_completed: { icon: 'V', label: 'Job Completed', color: '#22c55e' },
  job_failed: { icon: 'X', label: 'Job Failed', color: '#ef4444' },
  error_occurred: { icon: '!', label: 'Error Occurred', color: '#ef4444' },
  retry_started: { icon: 'R', label: 'Retry Started', color: '#f59e0b' },
};

export function ActivityTimeline({
  activities,
  maxItems = 20,
  showTimestamp = true,
}: ActivityTimelineProps) {
  const displayActivities = activities.slice(0, maxItems);
  const hasMore = activities.length > maxItems;

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
  };

  const itemStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
    position: 'relative',
    paddingBottom: '16px',
  };

  const lineStyles: CSSProperties = {
    position: 'absolute',
    left: '15px',
    top: '28px',
    bottom: 0,
    width: '2px',
    backgroundColor: '#e5e7eb',
  };

  return (
    <Card title="Activity Timeline" padding="md">
      <div style={containerStyles}>
        {displayActivities.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px', color: '#6b7280' }}>
            No activity yet
          </div>
        ) : (
          displayActivities.map((activity, index) => {
            const config = actionConfig[activity.action] || {
              icon: '-',
              label: activity.action,
              color: '#6b7280',
            };
            const isLast = index === displayActivities.length - 1;

            return (
              <div key={activity.id} style={itemStyles}>
                {!isLast && <div style={lineStyles} />}
                <ActivityIcon icon={config.icon} color={config.color} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: '14px',
                      fontWeight: 500,
                      color: '#111827',
                      marginBottom: '2px',
                    }}
                  >
                    {config.label}
                  </div>
                  {activity.details && Object.keys(activity.details).length > 0 && (
                    <ActivityDetails details={activity.details} />
                  )}
                  {showTimestamp && (
                    <div
                      style={{
                        fontSize: '12px',
                        color: '#9ca3af',
                        marginTop: '4px',
                      }}
                      title={formatDateTime(activity.timestamp)}
                    >
                      {formatRelativeTime(activity.timestamp)}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
        {hasMore && (
          <div
            style={{
              textAlign: 'center',
              fontSize: '13px',
              color: '#6b7280',
              paddingTop: '8px',
            }}
          >
            + {activities.length - maxItems} more activities
          </div>
        )}
      </div>
    </Card>
  );
}

function ActivityIcon({ icon, color }: { icon: string; color: string }) {
  const iconStyles: CSSProperties = {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    backgroundColor: color + '20',
    color: color,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    fontWeight: 600,
    flexShrink: 0,
  };

  return <div style={iconStyles}>{icon}</div>;
}

function ActivityDetails({ details }: { details: Record<string, unknown> }) {
  const detailsStyles: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
    marginTop: '4px',
  };

  const formatValue = (value: unknown): string => {
    if (typeof value === 'object' && value !== null) {
      return JSON.stringify(value);
    }
    return String(value);
  };

  const entries = Object.entries(details).slice(0, 3);

  return (
    <div style={detailsStyles}>
      {entries.map(([key, value]) => (
        <span key={key} style={{ marginRight: '12px' }}>
          <span style={{ color: '#9ca3af' }}>{key}:</span>{' '}
          <span style={{ color: '#4b5563' }}>{formatValue(value)}</span>
        </span>
      ))}
    </div>
  );
}

/**
 * Compact activity feed for sidebars.
 */
export function ActivityFeed({
  activities,
  maxItems = 5,
}: {
  activities: Activity[];
  maxItems?: number;
}) {
  const displayActivities = activities.slice(0, maxItems);

  const itemStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 0',
    borderBottom: '1px solid #f3f4f6',
    fontSize: '13px',
  };

  return (
    <div>
      {displayActivities.map((activity) => {
        const config = actionConfig[activity.action] || {
          icon: '-',
          label: activity.action,
          color: '#6b7280',
        };

        return (
          <div key={activity.id} style={itemStyles}>
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: config.color,
                flexShrink: 0,
              }}
            />
            <span style={{ flex: 1, color: '#374151' }}>{config.label}</span>
            <span style={{ color: '#9ca3af', fontSize: '11px' }}>
              {formatRelativeTime(activity.timestamp)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
