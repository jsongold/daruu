/**
 * Panel showing the list of annotation pairs.
 */

import type { AnnotationPair } from '../../types/annotation';

interface PairListProps {
  pairs: AnnotationPair[];
  onFocusLabel: (labelId: string) => void;
  onDeletePair: (pairId: string) => void;
}

function confidenceColor(confidence: number): string {
  if (confidence >= 80) return 'bg-green-100 text-green-700';
  if (confidence >= 60) return 'bg-amber-100 text-amber-700';
  return 'bg-red-100 text-red-700';
}

export function PairList({ pairs, onFocusLabel, onDeletePair }: PairListProps) {
  const confirmedCount = pairs.filter((p) => p.status === 'confirmed').length;
  const manualCount = pairs.filter((p) => p.isManual).length;

  if (pairs.length === 0) {
    return (
      <div>
        <div className="text-xs font-medium text-gray-500 mb-2">Annotations (0)</div>
        <div className="text-xs text-gray-400 text-center py-6">
          No pairs yet. Click a label, then click a field to create a pair.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <div className="text-xs font-medium text-gray-500 mb-2">
        Annotations ({pairs.length}) -- {confirmedCount} confirmed, {manualCount} manual
      </div>
      {pairs.map((pair) => (
        <div
          key={pair.id}
          onClick={() => onFocusLabel(pair.label.id)}
          className={`px-3 py-2 rounded-lg border transition-colors cursor-pointer ${
            pair.isManual
              ? 'border-red-200 bg-red-50/50 hover:border-red-400'
              : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30'
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-gray-800 truncate">
                {pair.label.text}
              </div>
              <div className="text-xs text-gray-500 truncate">
                {pair.field.fieldName}
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${confidenceColor(pair.confidence)}`}>
                {pair.confidence}%
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeletePair(pair.id);
                }}
                className="text-gray-300 hover:text-red-500 transition-colors p-0.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
          <div className="flex gap-1.5 mt-1.5">
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
              pair.status === 'confirmed' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
            }`}>
              {pair.status}
            </span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
              p.{pair.label.page}
            </span>
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${
              pair.isManual ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-400'
            }`}>
              {pair.isManual ? '\u2611' : '\u2610'} manual
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
