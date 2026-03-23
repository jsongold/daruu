/**
 * Toolbar for annotation actions: AI pairing, export, clear.
 */

import { useState } from 'react';
import type { AnnotationMode } from '../../types/annotation';

interface AnnotationToolbarProps {
  mode: AnnotationMode;
  totalLabels: number;
  totalFields: number;
  pairedCount: number;
  aiLoading: boolean;
  onRunAi: () => void;
  onExport: () => void;
  onClear: () => void;
  onCancel: () => void;
}

export function AnnotationToolbar({
  mode,
  totalLabels,
  totalFields,
  pairedCount,
  aiLoading,
  onRunAi,
  onExport,
  onClear,
  onCancel,
}: AnnotationToolbarProps) {
  const [showClearWarning, setShowClearWarning] = useState(false);

  const modeLabel =
    mode.type === 'field-selection'
      ? 'Select a field to pair'
      : mode.type === 'focus-pair'
        ? 'Viewing pair'
        : null;

  return (
    <div className="space-y-2.5">
      {/* Stats */}
      <div className="flex flex-wrap gap-1.5">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
          {totalLabels} labels
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
          {totalFields} fields
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
          {pairedCount} paired
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
          {Math.max(0, totalLabels - pairedCount)} left
        </span>
      </div>

      {/* Mode indicator */}
      {modeLabel && (
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-blue-50 border border-blue-200">
          <span className="text-xs text-blue-700">{modeLabel}</span>
          <button
            onClick={onCancel}
            className="text-xs text-blue-500 hover:text-blue-700 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onRunAi}
          disabled={aiLoading}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:bg-blue-300 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          {aiLoading && (
            <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          {aiLoading ? 'Pairing...' : 'AI Auto-Pair'}
        </button>
        <button
          onClick={onExport}
          disabled={pairedCount === 0}
          className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded-lg border border-gray-300 hover:bg-gray-200 transition-colors disabled:text-gray-400 disabled:cursor-not-allowed"
        >
          Export
        </button>
        <button
          onClick={() => setShowClearWarning(true)}
          disabled={pairedCount === 0}
          className="px-3 py-1.5 text-red-500 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors disabled:text-gray-400 disabled:cursor-not-allowed"
        >
          Clear
        </button>
      </div>

      {/* Clear Warning Dialog */}
      {showClearWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-5 w-80 space-y-3">
            <h3 className="text-sm font-semibold text-gray-900">Clear all pairs?</h3>
            <p className="text-xs text-gray-500">
              This will remove all {pairedCount} annotation pairs. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => setShowClearWarning(false)}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowClearWarning(false);
                  onClear();
                }}
                className="px-3 py-1.5 text-xs font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors"
              >
                Clear All
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
