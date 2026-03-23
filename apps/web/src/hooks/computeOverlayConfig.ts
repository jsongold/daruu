/**
 * Pure function that derives overlay rendering config from mode + data.
 * Single source of truth for what the overlay should display.
 */

import type {
  AnnotationMode,
  LabelOverlay,
  FieldOverlay,
  OverlayConfig,
} from '../types/annotation';

export function computeOverlayConfig(
  mode: AnnotationMode,
  labels: LabelOverlay[],
  fields: FieldOverlay[],
  manuallyPairedLabelIds: Set<string>,
  manuallyPairedFieldIds: Set<string>,
): OverlayConfig {
  switch (mode.type) {
    case 'idle':
      return {
        labels: labels.map((l) => ({
          overlay: l,
          colorKey: manuallyPairedLabelIds.has(l.id) ? 'paired' as const : 'default' as const,
        })),
        fields: [],
      };

    case 'field-selection': {
      const focusedLabel = labels.find((l) => l.id === mode.labelId);
      return {
        labels: focusedLabel
          ? [{ overlay: focusedLabel, colorKey: 'focused' as const }]
          : [],
        fields: fields.map((f) => ({
          overlay: f,
          colorKey: manuallyPairedFieldIds.has(f.id) ? 'paired' as const : 'default' as const,
        })),
      };
    }

    case 'focus-pair': {
      const focusedLabel = labels.find((l) => l.id === mode.labelId);
      const focusedField = fields.find((f) => f.id === mode.fieldId);
      return {
        labels: focusedLabel
          ? [{ overlay: focusedLabel, colorKey: 'focused' as const }]
          : [],
        fields: focusedField
          ? [{ overlay: focusedField, colorKey: 'paired' as const }]
          : [],
      };
    }
  }
}
