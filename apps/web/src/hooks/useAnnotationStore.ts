/**
 * State management hook for the annotation tool.
 * Mode-driven architecture: single `mode` state drives all UI behavior.
 */

import { useState, useCallback, useMemo } from 'react';
import type {
  AnnotationDocumentState,
  AnnotationMode,
  AnnotationPair,
  LabelOverlay,
  FieldOverlay,
  AnnotationBBox,
  ExportEntry,
} from '../types/annotation';
import type { AcroFormFieldInfo, PageDimensions } from '../types/api';
import { getDocument, getAcroFormFields, getTextBlocks } from '../api/client';
import type { TextBlock } from '../api/client';
import { runAiPairing } from '../utils/aiPairing';
import { computeOverlayConfig } from './computeOverlayConfig';

/**
 * Normalize a bbox from PDF coordinates to 0-1 range.
 */
function normalizeBBox(
  x: number,
  y: number,
  width: number,
  height: number,
  pageDim: PageDimensions
): AnnotationBBox {
  return {
    x: x / pageDim.width,
    y: y / pageDim.height,
    width: width / pageDim.width,
    height: height / pageDim.height,
  };
}

function textBlocksToLabels(
  blocks: TextBlock[],
  pageDimensions: PageDimensions[]
): LabelOverlay[] {
  return blocks
    .filter((b) => b.text.trim().length > 0)
    .map((block) => {
      const pageDim = pageDimensions.find((pd) => pd.page === block.page);
      if (!pageDim) return null;
      return {
        id: block.id,
        text: block.text,
        bbox: normalizeBBox(block.bbox[0], block.bbox[1], block.bbox[2], block.bbox[3], pageDim),
        page: block.page,
      };
    })
    .filter((label): label is LabelOverlay => label !== null);
}

function acroFormToFields(
  fields: AcroFormFieldInfo[],
  pageDimensions: PageDimensions[]
): FieldOverlay[] {
  return fields
    .map((field) => {
      const pageDim = pageDimensions.find((pd) => pd.page === field.bbox.page);
      if (!pageDim) return null;
      return {
        id: `field-${field.field_name}`,
        fieldName: field.field_name,
        bbox: normalizeBBox(field.bbox.x, field.bbox.y, field.bbox.width, field.bbox.height, pageDim),
        page: field.bbox.page,
      };
    })
    .filter((f): f is FieldOverlay => f !== null);
}

const emptyState: AnnotationDocumentState = {
  documentId: '',
  filename: '',
  totalPages: 0,
  currentPage: 1,
  labels: [],
  fields: [],
  pairs: [],
};

export function useAnnotationStore() {
  const [doc, setDoc] = useState<AnnotationDocumentState>(emptyState);
  const [mode, _setMode] = useState<AnnotationMode>({ type: 'idle' });
  const setMode = useCallback((next: AnnotationMode) => {
    console.log('[AnnotationMode]', next.type, next);
    _setMode(next);
  }, []);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Derived data ---
  const currentLabels = doc.labels.filter((l) => l.page === doc.currentPage);
  const currentFields = doc.fields.filter((f) => f.page === doc.currentPage);

  const manuallyPairedLabelIds = useMemo(
    () => new Set(doc.pairs.filter((p) => p.isManual).map((p) => p.label.id)),
    [doc.pairs]
  );
  const manuallyPairedFieldIds = useMemo(
    () => new Set(doc.pairs.filter((p) => p.isManual).map((p) => p.field.id)),
    [doc.pairs]
  );

  // --- Overlay config (single source of truth for rendering) ---
  const overlayConfig = useMemo(
    () => computeOverlayConfig(mode, currentLabels, currentFields, manuallyPairedLabelIds, manuallyPairedFieldIds),
    [mode, currentLabels, currentFields, manuallyPairedLabelIds, manuallyPairedFieldIds]
  );

  // --- Document loading ---
  const loadDocument = useCallback(async (documentId: string) => {
    setLoading(true);
    setError(null);
    try {
      const [docResponse, acroFormResponse, textBlocksResponse] = await Promise.all([
        getDocument(documentId),
        getAcroFormFields(documentId),
        getTextBlocks(documentId),
      ]);

      const labels = textBlocksToLabels(
        textBlocksResponse.blocks,
        acroFormResponse.page_dimensions
      );

      const fieldOverlays = acroFormToFields(
        acroFormResponse.fields,
        acroFormResponse.page_dimensions
      );

      setDoc({
        documentId,
        filename: docResponse.meta.filename,
        totalPages: docResponse.meta.page_count,
        currentPage: 1,
        labels,
        fields: fieldOverlays,
        pairs: [],
      });
      setMode({ type: 'idle' });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load document';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const setPage = useCallback((page: number) => {
    setDoc((d) => ({
      ...d,
      currentPage: Math.max(1, Math.min(d.totalPages, page)),
    }));
    setMode({ type: 'idle' });
  }, []);

  // --- Mode transitions ---

  /** Click a label on the overlay or in the pair list */
  const clickLabel = useCallback((labelId: string) => {
    const pair = doc.pairs.find((p) => p.label.id === labelId);
    if (pair) {
      setMode({ type: 'focus-pair', labelId, fieldId: pair.field.id, pairId: pair.id });
    } else {
      setMode({ type: 'field-selection', labelId });
    }
  }, [doc.pairs]);

  /** Click a field bbox */
  const clickField = useCallback((fieldId: string) => {
    // In focus-pair mode: unpair and enter field-selection to re-pair
    if (mode.type === 'focus-pair') {
      setDoc((d) => ({ ...d, pairs: d.pairs.filter((p) => p.id !== mode.pairId) }));
      setMode({ type: 'field-selection', labelId: mode.labelId });
      return;
    }

    if (mode.type !== 'field-selection') return;

    const label = doc.labels.find((l) => l.id === mode.labelId);
    const field = doc.fields.find((f) => f.id === fieldId);
    if (!label || !field) return;

    const newPair: AnnotationPair = {
      id: crypto.randomUUID(),
      label,
      field,
      confidence: 100,
      status: 'confirmed',
      isManual: true,
    };
    setDoc((d) => ({ ...d, pairs: [...d.pairs, newPair] }));
    setMode({ type: 'idle' });
  }, [mode, doc.labels, doc.fields]);

  /** Click empty space -> back to idle */
  const clickEmpty = useCallback(() => {
    setMode({ type: 'idle' });
  }, []);

  /** Click a pair in the PairList -> navigate to page and focus */
  const focusPairFromList = useCallback((labelId: string) => {
    const label = doc.labels.find((l) => l.id === labelId);
    if (!label) return;

    if (label.page !== doc.currentPage) {
      setDoc((d) => ({ ...d, currentPage: label.page }));
    }

    const pair = doc.pairs.find((p) => p.label.id === labelId);
    if (pair) {
      setMode({ type: 'focus-pair', labelId, fieldId: pair.field.id, pairId: pair.id });
    } else {
      setMode({ type: 'field-selection', labelId });
    }
  }, [doc.labels, doc.pairs, doc.currentPage]);

  const deletePair = useCallback((pairId: string) => {
    setDoc((d) => ({ ...d, pairs: d.pairs.filter((p) => p.id !== pairId) }));
    setMode({ type: 'idle' });
  }, []);

  const addLabel = useCallback((text: string, bbox: AnnotationBBox, page: number) => {
    const newLabel: LabelOverlay = {
      id: crypto.randomUUID(),
      text,
      bbox,
      page,
    };
    setDoc((d) => ({ ...d, labels: [...d.labels, newLabel] }));
  }, []);

  const runAi = useCallback(async () => {
    setAiLoading(true);
    await new Promise((r) => setTimeout(r, 800));
    setDoc((d) => {
      const newPairs = runAiPairing(d.labels, d.fields, d.pairs);
      return { ...d, pairs: [...d.pairs, ...newPairs] };
    });
    setAiLoading(false);
  }, []);

  const clearPairs = useCallback(() => {
    setDoc((d) => ({ ...d, pairs: [] }));
    setMode({ type: 'idle' });
  }, []);

  const exportJson = useCallback(() => {
    const entries: ExportEntry[] = doc.pairs.map((p) => ({
      label_text: p.label.text,
      label_bbox: p.label.bbox,
      field_bbox: p.field.bbox,
      field_id: p.field.id,
      field_name: p.field.fieldName,
      page: p.label.page,
      confidence: p.confidence,
      status: p.status,
    }));
    const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${doc.filename.replace('.pdf', '')}_annotations.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [doc.pairs, doc.filename]);

  return {
    doc,
    mode,
    overlayConfig,
    aiLoading,
    loading,
    error,
    currentLabels,
    currentFields,
    loadDocument,
    setPage,
    clickLabel,
    clickField,
    clickEmpty,
    focusPairFromList,
    deletePair,
    addLabel,
    runAi,
    clearPairs,
    exportJson,
  };
}
