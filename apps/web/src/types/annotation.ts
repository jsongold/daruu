/**
 * Type definitions for the Label & Bbox Annotation Tool.
 * Used to pair text labels with form field bounding boxes.
 */

export interface AnnotationBBox {
  /** Normalized 0-1 coordinate */
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LabelOverlay {
  id: string;
  text: string;
  bbox: AnnotationBBox;
  page: number;
}

export interface FieldOverlay {
  id: string;
  fieldName: string;
  bbox: AnnotationBBox;
  page: number;
}

export interface AnnotationPair {
  id: string;
  label: LabelOverlay;
  field: FieldOverlay;
  confidence: number;
  status: 'confirmed' | 'flagged';
  isManual: boolean;
}

export type AnnotationMode =
  | { type: 'idle' }
  | { type: 'field-selection'; labelId: string }
  | { type: 'focus-pair'; labelId: string; fieldId: string; pairId: string };

export type LabelColorKey = 'default' | 'paired' | 'focused';
export type FieldColorKey = 'default' | 'paired';

export interface OverlayConfig {
  labels: Array<{ overlay: LabelOverlay; colorKey: LabelColorKey }>;
  fields: Array<{ overlay: FieldOverlay; colorKey: FieldColorKey }>;
}

export interface AnnotationDocumentState {
  documentId: string;
  filename: string;
  totalPages: number;
  currentPage: number;
  labels: LabelOverlay[];
  fields: FieldOverlay[];
  pairs: AnnotationPair[];
}

export interface ExportEntry {
  label_text: string;
  label_bbox: AnnotationBBox;
  field_bbox: AnnotationBBox;
  field_id: string;
  field_name: string;
  page: number;
  confidence: number;
  status: 'confirmed' | 'flagged';
}
