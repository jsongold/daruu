/**
 * Chip component for displaying a data source item.
 * Shows file type icon, name, and remove button.
 */

import { useCallback } from 'react';
import type { DataSourceResponse, DataSourceType } from '../../lib/api-types';
import { formatFileSize } from '../../api/dataSourceClient';

interface DataSourceChipProps {
  dataSource: DataSourceResponse;
  onRemove: () => void;
  onClick?: () => void;
}

export function DataSourceChip({ dataSource, onRemove, onClick }: DataSourceChipProps) {
  const handleRemove = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onRemove();
    },
    [onRemove]
  );

  // Truncate name if too long
  const displayName =
    dataSource.name.length > 18
      ? dataSource.name.substring(0, 15) + '...'
      : dataSource.name;

  const icon = getTypeIcon(dataSource.type);
  const sizeText = formatFileSize(dataSource.file_size_bytes);

  return (
    <div
      onClick={onClick}
      className={`
        group relative flex items-center gap-2 px-3 py-2 rounded-lg
        transition-colors shrink-0
        bg-gray-100 text-gray-700 border border-transparent hover:bg-gray-200
        ${onClick ? 'cursor-pointer' : ''}
      `}
    >
      {/* Type Icon */}
      <span className="text-lg shrink-0" role="img" aria-label={dataSource.type}>
        {icon}
      </span>

      {/* Name and size */}
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-medium truncate" title={dataSource.name}>
          {displayName}
        </span>
        {sizeText && (
          <span className="text-xs text-gray-500">{sizeText}</span>
        )}
      </div>

      {/* Remove button */}
      <button
        onClick={handleRemove}
        className="
          absolute -top-1 -right-1 w-5 h-5 rounded-full bg-gray-500 text-white
          flex items-center justify-center opacity-0 group-hover:opacity-100
          hover:bg-red-500 transition-all
        "
        aria-label="Remove data source"
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>
  );
}

function getTypeIcon(type: DataSourceType): string {
  switch (type) {
    case 'pdf':
      return '📄';
    case 'image':
      return '🖼️';
    case 'text':
      return '📝';
    case 'csv':
      return '📊';
    default:
      return '📁';
  }
}
