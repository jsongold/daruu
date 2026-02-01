/**
 * Field list panel with filtering and sorting.
 *
 * Supports bidirectional selection:
 * - Clicking a field triggers onFieldSelect callback
 * - External selection via selectedFieldId scrolls the field into view
 */

import { useState, useMemo, useCallback, useEffect, useRef, type CSSProperties } from 'react';
import type { Field, Issue } from '../../types/api';
import { FieldCard } from './FieldCard';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { EmptyState } from '../ui/LoadingState';
import { formatPercent } from '../../utils/format';

export type FieldFilter = 'all' | 'issues' | 'low_confidence' | 'missing' | 'editable';
export type FieldSort = 'name' | 'confidence' | 'page';

export interface FieldListPanelProps {
  fields: Field[];
  issues: Issue[];
  onFieldEdit?: (fieldId: string, value: string) => void;
  onFieldSelect?: (field: Field) => void;
  selectedFieldId?: string | null;
  onShowEvidence?: (fieldId: string) => void;
  title?: string;
  /** Pending edits to display (field ID -> edited value) */
  pendingEdits?: Map<string, string>;
}

export function FieldListPanel({
  fields,
  issues,
  onFieldEdit,
  onFieldSelect,
  selectedFieldId,
  onShowEvidence,
  title = 'Fields',
  pendingEdits,
}: FieldListPanelProps) {
  const [filter, setFilter] = useState<FieldFilter>('all');
  const [sort, setSort] = useState<FieldSort>('name');
  const [searchQuery, setSearchQuery] = useState('');

  // Refs for scrolling selected field into view
  const listContainerRef = useRef<HTMLDivElement>(null);
  const fieldCardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // Scroll selected field into view when selection changes externally
  useEffect(() => {
    if (selectedFieldId) {
      const fieldElement = fieldCardRefs.current.get(selectedFieldId);
      if (fieldElement) {
        fieldElement.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        });
      }
    }
  }, [selectedFieldId]);

  const getFieldIssues = useCallback(
    (fieldId: string): Issue[] => {
      return issues.filter((issue) => issue.field_id === fieldId);
    },
    [issues]
  );

  const filteredFields = useMemo(() => {
    let result = [...fields];

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (f) =>
          f.name.toLowerCase().includes(query) ||
          (f.value && f.value.toLowerCase().includes(query))
      );
    }

    // Apply category filter
    switch (filter) {
      case 'issues':
        result = result.filter((f) => getFieldIssues(f.id).length > 0);
        break;
      case 'low_confidence':
        result = result.filter((f) => f.confidence !== null && f.confidence < 0.7);
        break;
      case 'missing':
        result = result.filter((f) => !f.value);
        break;
      case 'editable':
        result = result.filter((f) => f.is_editable);
        break;
    }

    // Apply sorting
    switch (sort) {
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'confidence':
        result.sort((a, b) => {
          const confA = a.confidence ?? 0;
          const confB = b.confidence ?? 0;
          return confB - confA;
        });
        break;
      case 'page':
        result.sort((a, b) => a.page - b.page);
        break;
    }

    return result;
  }, [fields, filter, sort, searchQuery, getFieldIssues]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = fields.length;
    const withIssues = fields.filter((f) => getFieldIssues(f.id).length > 0).length;
    const lowConfidence = fields.filter(
      (f) => f.confidence !== null && f.confidence < 0.7
    ).length;
    const missing = fields.filter((f) => !f.value).length;
    const avgConfidence =
      fields.reduce((acc, f) => acc + (f.confidence ?? 0), 0) / (total || 1);

    return { total, withIssues, lowConfidence, missing, avgConfidence };
  }, [fields, getFieldIssues]);

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  };

  const controlsStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginBottom: '16px',
  };

  const searchStyles: CSSProperties = {
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    outline: 'none',
    width: '100%',
  };

  const filterRowStyles: CSSProperties = {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  };

  const selectStyles: CSSProperties = {
    padding: '6px 10px',
    fontSize: '13px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    backgroundColor: 'white',
    cursor: 'pointer',
  };

  const statsStyles: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '8px',
    marginBottom: '16px',
  };

  const statItemStyles: CSSProperties = {
    padding: '8px 12px',
    backgroundColor: '#f9fafb',
    borderRadius: '6px',
    textAlign: 'center',
  };

  const listStyles: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  };

  const filterOptions: { value: FieldFilter; label: string; count?: number }[] = [
    { value: 'all', label: 'All', count: stats.total },
    { value: 'issues', label: 'With Issues', count: stats.withIssues },
    { value: 'low_confidence', label: 'Low Confidence', count: stats.lowConfidence },
    { value: 'missing', label: 'Missing', count: stats.missing },
    { value: 'editable', label: 'Editable' },
  ];

  // When no title, render without Card wrapper for better scroll behavior
  const content = (
    <div style={containerStyles}>
      <div style={{ ...controlsStyles, padding: title ? 0 : '16px', paddingBottom: 0 }}>
          <input
            type="text"
            placeholder="Search fields..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={searchStyles}
          />

          <div style={filterRowStyles}>
            {filterOptions.map((opt) => (
              <Button
                key={opt.value}
                variant={filter === opt.value ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setFilter(opt.value)}
              >
                {opt.label}
                {opt.count !== undefined && ` (${opt.count})`}
              </Button>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', color: '#6b7280' }}>Sort by:</span>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as FieldSort)}
              style={selectStyles}
            >
              <option value="name">Name</option>
              <option value="confidence">Confidence</option>
              <option value="page">Page</option>
            </select>
          </div>
        </div>

        <div style={statsStyles}>
          <div style={statItemStyles}>
            <div style={{ fontSize: '18px', fontWeight: 600, color: '#111827' }}>
              {stats.total}
            </div>
            <div style={{ fontSize: '11px', color: '#6b7280' }}>Total</div>
          </div>
          <div style={statItemStyles}>
            <div
              style={{
                fontSize: '18px',
                fontWeight: 600,
                color: stats.withIssues > 0 ? '#dc2626' : '#22c55e',
              }}
            >
              {stats.withIssues}
            </div>
            <div style={{ fontSize: '11px', color: '#6b7280' }}>Issues</div>
          </div>
          <div style={statItemStyles}>
            <div
              style={{
                fontSize: '18px',
                fontWeight: 600,
                color: stats.missing > 0 ? '#f59e0b' : '#22c55e',
              }}
            >
              {stats.missing}
            </div>
            <div style={{ fontSize: '11px', color: '#6b7280' }}>Missing</div>
          </div>
          <div style={statItemStyles}>
            <div style={{ fontSize: '18px', fontWeight: 600, color: '#111827' }}>
              {formatPercent(stats.avgConfidence)}
            </div>
            <div style={{ fontSize: '11px', color: '#6b7280' }}>Avg Conf</div>
          </div>
        </div>

        <div ref={listContainerRef} style={listStyles}>
          {filteredFields.length === 0 ? (
            <EmptyState
              title="No fields found"
              description={
                filter !== 'all' || searchQuery
                  ? 'Try adjusting your filters or search query'
                  : 'No fields have been extracted yet'
              }
            />
          ) : (
            filteredFields.map((field) => (
              <div
                key={field.id}
                ref={(el) => {
                  if (el) {
                    fieldCardRefs.current.set(field.id, el);
                  } else {
                    fieldCardRefs.current.delete(field.id);
                  }
                }}
              >
                <FieldCard
                  field={field}
                  issues={getFieldIssues(field.id)}
                  onEdit={onFieldEdit}
                  onClick={onFieldSelect}
                  isSelected={selectedFieldId === field.id}
                  onShowEvidence={onShowEvidence}
                  pendingValue={pendingEdits?.get(field.id)}
                />
              </div>
            ))
          )}
        </div>
      </div>
  );

  // When title is provided, wrap in Card; otherwise render directly
  if (title) {
    return (
      <Card title={title} padding="md" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {content}
      </Card>
    );
  }

  return content;
}
