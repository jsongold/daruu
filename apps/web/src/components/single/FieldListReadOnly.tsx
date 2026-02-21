/**
 * Read-only field list panel.
 * Displays all fields with their values. Click to highlight in preview.
 */

import type { FieldData } from '../../api/editClient';

interface FieldListReadOnlyProps {
  fields: FieldData[];
  selectedFieldId: string | null;
  onFieldSelect: (fieldId: string | null) => void;
  isLoading?: boolean;
  /** Optional confidence scores per field (0-1). Shows colored dot when provided. */
  confidenceMap?: Record<string, number>;
}

export function FieldListReadOnly({
  fields,
  selectedFieldId,
  onFieldSelect,
  isLoading = false,
  confidenceMap,
}: FieldListReadOnlyProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (fields.length === 0) {
    return (
      <div className="p-4 text-center">
        <svg className="w-10 h-10 mx-auto text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p className="text-sm text-gray-500">No fields detected</p>
        <p className="text-xs text-gray-400 mt-1">Upload a PDF with form fields</p>
      </div>
    );
  }

  // Group fields by page
  const fieldsByPage = fields.reduce((acc, field) => {
    const page = field.bbox?.page || 1;
    if (!acc[page]) acc[page] = [];
    acc[page].push(field);
    return acc;
  }, {} as Record<number, FieldData[]>);

  const pages = Object.keys(fieldsByPage).map(Number).sort((a, b) => a - b);

  // Stats
  const filledCount = fields.filter(f => f.value && f.value.trim() !== '').length;
  const totalCount = fields.length;

  return (
    <div className="flex flex-col">
      {/* Stats */}
      <div className="px-3 py-2 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{totalCount} fields</span>
          <span className={filledCount === totalCount ? 'text-green-600' : ''}>
            {filledCount}/{totalCount} filled
          </span>
        </div>
        {/* Progress bar */}
        <div className="mt-1.5 h-1 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 transition-all"
            style={{ width: `${totalCount > 0 ? (filledCount / totalCount) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Field list */}
      <div className="divide-y divide-gray-100">
        {pages.map(page => (
          <div key={page}>
            {pages.length > 1 && (
              <div className="px-3 py-1.5 bg-gray-50 text-xs font-medium text-gray-500">
                Page {page}
              </div>
            )}
            {fieldsByPage[page].map(field => (
              <FieldItem
                key={field.field_id}
                field={field}
                isSelected={field.field_id === selectedFieldId}
                onSelect={() => onFieldSelect(field.field_id)}
                confidence={confidenceMap?.[field.field_id]}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

interface FieldItemProps {
  field: FieldData;
  isSelected: boolean;
  onSelect: () => void;
  confidence?: number;
}

function FieldItem({ field, isSelected, onSelect, confidence }: FieldItemProps) {
  const hasValue = field.value && field.value.trim() !== '';

  return (
    <div
      onClick={onSelect}
      className={`
        px-3 py-2 cursor-pointer transition-colors
        ${isSelected
          ? 'bg-blue-50 border-l-2 border-blue-500'
          : 'hover:bg-gray-50 border-l-2 border-transparent'
        }
      `}
    >
      {/* Label */}
      <div className="flex items-center gap-1.5">
        <FieldTypeIcon type={field.type} />
        <span className="text-sm font-medium text-gray-700 truncate">
          {field.label}
        </span>
        {field.required && (
          <span className="text-red-500 text-xs">*</span>
        )}
      </div>

      {/* Value */}
      <div className="mt-1 text-xs truncate">
        {hasValue ? (
          <span className="text-gray-600">{field.value}</span>
        ) : (
          <span className="text-gray-400 italic">Empty</span>
        )}
      </div>

      {/* Status indicator */}
      <div className="mt-1 flex items-center gap-1">
        {hasValue ? (
          <span className="inline-flex items-center gap-1 text-xs text-green-600">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            Filled
          </span>
        ) : (
          <span className="text-xs text-gray-400">Not filled</span>
        )}
        {confidence !== undefined && (
          <span className="ml-auto flex items-center gap-1">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                confidence >= 0.9
                  ? 'bg-green-500'
                  : confidence >= 0.7
                    ? 'bg-yellow-400'
                    : 'bg-orange-400'
              }`}
            />
            <span className="text-xs text-gray-400">{Math.round(confidence * 100)}%</span>
          </span>
        )}
      </div>
    </div>
  );
}

function FieldTypeIcon({ type }: { type: FieldData['type'] }) {
  switch (type) {
    case 'checkbox':
      return (
        <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'date':
      return (
        <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    case 'number':
      return (
        <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
        </svg>
      );
    default:
      return (
        <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
        </svg>
      );
  }
}
