/**
 * Heuristic AI pairing: matches labels to fields based on spatial proximity.
 * For each unpaired label, finds the closest unpaired field on the same page
 * (looking to the right or below the label, as is typical in forms).
 */

import type { LabelOverlay, FieldOverlay, AnnotationPair } from '../types/annotation';

export function runAiPairing(
  labels: LabelOverlay[],
  fields: FieldOverlay[],
  existingPairs: AnnotationPair[]
): AnnotationPair[] {
  const pairedLabelIds = new Set(existingPairs.map((p) => p.label.id));
  const pairedFieldIds = new Set(existingPairs.map((p) => p.field.id));

  const unpairedLabels = labels.filter((l) => !pairedLabelIds.has(l.id));
  const unpairedFields = fields.filter((f) => !pairedFieldIds.has(f.id));

  const usedFields = new Set<string>();
  const newPairs: AnnotationPair[] = [];

  for (const label of unpairedLabels) {
    const candidates = unpairedFields.filter(
      (f) => f.page === label.page && !usedFields.has(f.id)
    );

    if (candidates.length === 0) continue;

    let best = candidates[0];
    let bestScore = Infinity;

    for (const field of candidates) {
      const dx = field.bbox.x - (label.bbox.x + label.bbox.width);
      const dy = field.bbox.y - label.bbox.y;

      // Penalize fields that are far to the left of the label end
      const horizontalPenalty = dx < -0.03 ? 500 : 0;
      const score = Math.sqrt(dx * dx + dy * dy) + horizontalPenalty;

      if (score < bestScore) {
        bestScore = score;
        best = field;
      }
    }

    // Confidence based on distance (scaled for normalized 0-1 coords)
    const normalizedDistance = bestScore * 1000;
    const confidence = Math.max(30, Math.min(99, Math.round(100 - normalizedDistance / 5)));

    usedFields.add(best.id);
    newPairs.push({
      id: crypto.randomUUID(),
      label,
      field: best,
      confidence,
      status: confidence >= 60 ? 'confirmed' : 'flagged',
      isManual: false,
    });
  }

  return newPairs;
}
