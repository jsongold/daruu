/**
 * Document preview component with editable field overlays.
 * Extends base DocumentPreview with click-to-edit functionality.
 * Uses react-zoom-pan-pinch for smooth pan/zoom in all directions.
 */

import {
  useState,
  useCallback,
  useRef,
  useMemo,
  type CSSProperties,
} from 'react';
import { TransformWrapper, TransformComponent, useControls } from 'react-zoom-pan-pinch';
import { Button } from '../ui/Button';
import { LoadingSpinner, EmptyState } from '../ui/LoadingState';
import { FieldHighlight, type FieldRegion } from './FieldHighlight';
import { InlineEditor } from '../editor/InlineEditor';
import type { FieldData, FontStyle } from '../../api/editClient';

export interface EditableDocumentPreviewProps {
  /** Image URLs for each page */
  pageUrls: string[];
  /** Fields to display as highlights */
  fields?: FieldData[];
  /** Currently selected field ID */
  selectedFieldId?: string | null;
  /** Initial page to display (1-indexed) */
  initialPage?: number;
  /** Called when page changes */
  onPageChange?: (page: number) => void;
  /** Called when a field is selected */
  onFieldSelect?: (fieldId: string | null) => void;
  /** Called when a field value is edited */
  onFieldEdit?: (fieldId: string, value: string, fontStyle?: FontStyle) => void;
  /** Whether the preview is loading */
  isLoading?: boolean;
  /** Whether field edit is in progress */
  isEditLoading?: boolean;
  /** Error message if preview failed */
  error?: string | null;
  /** Title to display in header */
  title?: string;
  /** Called when download is requested */
  onDownload?: () => void;
  /** Whether download is available */
  canDownload?: boolean;
  /** Enable field highlighting */
  enableFieldHighlights?: boolean;
  /** Show undo/redo buttons */
  showUndoRedo?: boolean;
  /** Whether undo is available */
  canUndo?: boolean;
  /** Whether redo is available */
  canRedo?: boolean;
  /** Called when undo is clicked */
  onUndo?: () => void;
  /** Called when redo is clicked */
  onRedo?: () => void;
}

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.25;

// Zoom controls component that uses react-zoom-pan-pinch hooks
interface ZoomControlsProps {
  showUndoRedo: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  canDownload: boolean;
  onDownload?: () => void;
}

function ZoomControls({
  showUndoRedo,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  canDownload,
  onDownload,
}: ZoomControlsProps) {
  const { zoomIn, zoomOut, resetTransform, instance } = useControls();
  const scale = instance.transformState.scale;

  const controlsStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexWrap: 'wrap',
  };

  const dividerStyle: CSSProperties = {
    width: '1px',
    height: '24px',
    backgroundColor: '#e5e7eb',
    margin: '0 4px',
  };

  const zoomInfoStyle: CSSProperties = {
    fontSize: '12px',
    color: '#9ca3af',
    minWidth: '48px',
    textAlign: 'center',
  };

  return (
    <div style={controlsStyle}>
      {/* Undo/Redo controls */}
      {showUndoRedo && (
        <>
          <Button
            variant="ghost"
            size="sm"
            onClick={onUndo}
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
          >
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
            </svg>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onRedo}
            disabled={!canRedo}
            title="Redo (Ctrl+Shift+Z)"
          >
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10H11a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6" />
            </svg>
          </Button>
          <div style={dividerStyle} />
        </>
      )}

      {/* Zoom controls */}
      <Button variant="ghost" size="sm" onClick={() => zoomOut(ZOOM_STEP)} disabled={scale <= MIN_ZOOM}>
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
        </svg>
      </Button>
      <span style={zoomInfoStyle}>{Math.round(scale * 100)}%</span>
      <Button variant="ghost" size="sm" onClick={() => zoomIn(ZOOM_STEP)} disabled={scale >= MAX_ZOOM}>
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      </Button>
      <Button variant="ghost" size="sm" onClick={() => resetTransform()} disabled={scale === 1}>
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
          />
        </svg>
      </Button>

      {/* Download button */}
      {canDownload && onDownload && (
        <>
          <div style={dividerStyle} />
          <Button variant="secondary" size="sm" onClick={onDownload}>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Download
          </Button>
        </>
      )}
    </div>
  );
}

export function EditableDocumentPreview({
  pageUrls,
  fields = [],
  selectedFieldId,
  initialPage = 1,
  onPageChange,
  onFieldSelect,
  onFieldEdit,
  isLoading = false,
  isEditLoading = false,
  error,
  title = 'Document Preview',
  onDownload,
  canDownload = false,
  enableFieldHighlights = true,
  showUndoRedo = true,
  canUndo = false,
  canRedo = false,
  onUndo,
  onRedo,
}: EditableDocumentPreviewProps) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [editingField, setEditingField] = useState<{
    fieldId: string;
    position: { x: number; y: number };
  } | null>(null);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });

  const imageRef = useRef<HTMLImageElement>(null);

  const totalPages = pageUrls.length;
  const currentPageUrl = pageUrls[currentPage - 1];

  // Convert fields to FieldRegion format for current page
  const fieldRegions = useMemo((): FieldRegion[] => {
    return fields
      .filter((field) => {
        // Filter by page if bbox has page info
        if (field.bbox?.page) {
          return field.bbox.page === currentPage;
        }
        return true;
      })
      .map((field): FieldRegion => {
        const status: 'empty' | 'filled' | 'selected' | 'error' =
          field.validation_status === 'invalid'
            ? 'error'
            : field.value
              ? 'filled'
              : 'empty';

        return {
          id: field.field_id,
          label: field.label,
          value: field.value,
          bbox: field.bbox ? {
            x: field.bbox.x,
            y: field.bbox.y,
            width: field.bbox.width,
            height: field.bbox.height,
          } : { x: 0, y: 0, width: 0, height: 0 },
          type: field.type,
          status,
          required: field.required,
          fontStyle: field.fontStyle,
        };
      })
      .filter((field) => field.bbox.width > 0 && field.bbox.height > 0);
  }, [fields, currentPage]);

  // Get field data for inline editor
  const getFieldForEditor = useCallback((fieldId: string) => {
    return fields.find((f) => f.field_id === fieldId);
  }, [fields]);

  // Get bbox in pixels for a field (for fit text feature)
  const getFieldBboxInPixels = useCallback((fieldId: string): { width: number; height: number } | undefined => {
    const field = fields.find((f) => f.field_id === fieldId);
    if (!field?.bbox || !imageRef.current) {
      return undefined;
    }
    const containerWidth = imageRef.current.offsetWidth || imageSize.width;
    const containerHeight = imageRef.current.offsetHeight || imageSize.height;
    return {
      width: field.bbox.width * containerWidth,
      height: field.bbox.height * containerHeight,
    };
  }, [fields, imageSize.width, imageSize.height]);

  // Store resetTransform function for page changes
  const resetTransformRef = useRef<(() => void) | null>(null);

  const handlePageChange = useCallback((page: number) => {
    const newPage = Math.max(1, Math.min(page, totalPages));
    setCurrentPage(newPage);
    // Reset pan/zoom when changing pages
    resetTransformRef.current?.();
    onPageChange?.(newPage);
    // Close editor when changing pages
    setEditingField(null);
  }, [totalPages, onPageChange]);

  // Handle field click for inline editing
  const handleFieldClick = useCallback((
    fieldId: string,
    position: { x: number; y: number }
  ) => {
    onFieldSelect?.(fieldId);
    setEditingField({ fieldId, position });
  }, [onFieldSelect]);

  // Handle save from inline editor
  const handleInlineEditorSave = useCallback((fieldId: string, value: string, fontStyle?: FontStyle) => {
    onFieldEdit?.(fieldId, value, fontStyle);
    setEditingField(null);
  }, [onFieldEdit]);

  // Handle cancel from inline editor
  const handleInlineEditorCancel = useCallback(() => {
    setEditingField(null);
  }, []);

  // Handle click outside field highlights
  const handleContainerClick = useCallback(() => {
    if (!editingField) {
      onFieldSelect?.(null);
    }
  }, [editingField, onFieldSelect]);

  // Track image size for field positioning
  const handleImageLoad = useCallback(() => {
    if (imageRef.current) {
      setImageSize({
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight,
      });
    }
  }, []);

  // Styles
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: '#f9fafb',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid #e5e7eb',
    backgroundColor: 'white',
    flexWrap: 'wrap',
    gap: '8px',
  };

  const titleStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#1f2937',
  };

  const viewerStyle: CSSProperties = {
    flex: 1,
    overflow: 'hidden',
    position: 'relative',
  };

  const imageContainerStyle: CSSProperties = {
    position: 'relative',
  };

  const imageStyle: CSSProperties = {
    maxWidth: '100%',
    maxHeight: '100%',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    borderRadius: '4px',
    display: 'block',
  };

  const footerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    padding: '12px 16px',
    borderTop: '1px solid #e5e7eb',
    backgroundColor: 'white',
  };

  const pageInfoStyle: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
  };

  // Loading state
  if (isLoading) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>{title}</span>
        </div>
        <div style={{ ...viewerStyle, flexDirection: 'column', gap: '16px' }}>
          <LoadingSpinner size={32} />
          <span style={{ color: '#6b7280', fontSize: '14px' }}>Loading preview...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>{title}</span>
        </div>
        <div style={viewerStyle}>
          <EmptyState
            title="Preview unavailable"
            description={error}
            icon={
              <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            }
          />
        </div>
      </div>
    );
  }

  // Empty state
  if (pageUrls.length === 0) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>{title}</span>
        </div>
        <div style={viewerStyle}>
          <EmptyState
            title="No document selected"
            description="Upload a document to see the preview"
            icon={
              <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <TransformWrapper
        initialScale={1}
        minScale={MIN_ZOOM}
        maxScale={MAX_ZOOM}
        centerOnInit
        wheel={{ step: ZOOM_STEP }}
        panning={{ velocityDisabled: true }}
        onInit={(ref) => {
          resetTransformRef.current = ref.resetTransform;
        }}
      >
        {/* Header with zoom controls */}
        <div style={headerStyle}>
          <span style={titleStyle}>{title}</span>
          <ZoomControls
            showUndoRedo={showUndoRedo}
            canUndo={canUndo}
            canRedo={canRedo}
            onUndo={onUndo}
            onRedo={onRedo}
            canDownload={canDownload}
            onDownload={onDownload}
          />
        </div>

        {/* Zoomable/pannable content */}
        <div style={viewerStyle} onClick={handleContainerClick}>
          <TransformComponent
            wrapperStyle={{
              width: '100%',
              height: '100%',
            }}
            contentStyle={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <div style={imageContainerStyle}>
              <img
                ref={imageRef}
                src={currentPageUrl}
                alt={`Page ${currentPage} of ${totalPages}`}
                style={imageStyle}
                draggable={false}
                onLoad={handleImageLoad}
              />

              {/* Field highlights overlay */}
              {enableFieldHighlights && imageSize.width > 0 && (
                <FieldHighlight
                  fields={fieldRegions}
                  selectedFieldId={selectedFieldId}
                  onFieldClick={handleFieldClick}
                  enabled={true}
                  containerWidth={imageRef.current?.offsetWidth ?? imageSize.width}
                  containerHeight={imageRef.current?.offsetHeight ?? imageSize.height}
                />
              )}
            </div>
          </TransformComponent>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={footerStyle}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </Button>
            <span style={pageInfoStyle}>
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
            >
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Button>
          </div>
        )}
      </TransformWrapper>

      {/* Inline editor popover */}
      {editingField && (
        <InlineEditor
          fieldId={editingField.fieldId}
          fieldLabel={getFieldForEditor(editingField.fieldId)?.label ?? editingField.fieldId}
          currentValue={getFieldForEditor(editingField.fieldId)?.value ?? ''}
          fieldType={getFieldForEditor(editingField.fieldId)?.type}
          position={editingField.position}
          onSave={handleInlineEditorSave}
          onCancel={handleInlineEditorCancel}
          isLoading={isEditLoading}
          currentFontStyle={getFieldForEditor(editingField.fieldId)?.fontStyle}
          showFontControls={true}
          bbox={getFieldBboxInPixels(editingField.fieldId)}
        />
      )}
    </div>
  );
}
