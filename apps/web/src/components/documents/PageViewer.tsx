/**
 * PDF page viewer with pagination and zoom controls.
 */

import { useState, useEffect, useCallback, useRef, type CSSProperties } from 'react';
import { getPagePreviewUrl, getAcroFormFields } from '../../api/client';
import { Button } from '../ui/Button';
import { LoadingSpinner, ErrorState } from '../ui/LoadingState';
import { FieldOverlay, type BBoxUpdate, type FieldSaveStatus } from './FieldOverlay';
import type { AcroFormFieldInfo, AcroFormFieldsResponse } from '../../types/api';

// Re-export for convenience
export type { FieldSaveStatus };

export interface PageViewerProps {
  documentId: string;
  pageCount: number;
  title?: string;
  initialPage?: number;
  onPageChange?: (page: number) => void;
  height?: string | number;
  showFieldOverlay?: boolean;
  onFieldClick?: (field: AcroFormFieldInfo) => void;
  onFieldHover?: (field: AcroFormFieldInfo | null) => void;
  /** Externally highlighted field name (for bidirectional selection) */
  highlightedFieldName?: string | null;
  /** Additional bbox to highlight (e.g., anchor/label bbox) */
  highlightedAnchorBbox?: { x: number; y: number; width: number; height: number; page: number } | null;
  /** Enable field value editing in the overlay */
  editable?: boolean;
  /** Callback when a field value is changed */
  onFieldValueChange?: (update: BBoxUpdate) => void;
  /** External field values to display (field name -> value) - overrides AcroForm values */
  fieldValues?: Map<string, string>;
  /** Save status for each field (field name -> status) */
  fieldSaveStatus?: Map<string, FieldSaveStatus>;
  /** Error messages for fields with save errors (field name -> error message) */
  fieldSaveErrors?: Map<string, string>;
}

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2];

export function PageViewer({
  documentId,
  pageCount,
  title,
  initialPage = 1,
  onPageChange,
  height = '500px',
  showFieldOverlay = false,
  onFieldClick,
  onFieldHover,
  highlightedFieldName,
  highlightedAnchorBbox,
  editable = false,
  onFieldValueChange,
  fieldValues,
  fieldSaveStatus,
  fieldSaveErrors,
}: PageViewerProps) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [zoom, setZoom] = useState(1);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acroFormData, setAcroFormData] = useState<AcroFormFieldsResponse | null>(null);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const loadPage = useCallback(async () => {
    if (!documentId || currentPage < 1) return;

    setLoading(true);
    setError(null);

    try {
      const url = getPagePreviewUrl(documentId, currentPage);
      // Preload the image
      const img = new Image();
      img.onload = () => {
        setImageUrl(url);
        setLoading(false);
      };
      img.onerror = () => {
        setError('Failed to load page preview');
        setLoading(false);
      };
      img.src = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load page');
      setLoading(false);
    }
  }, [documentId, currentPage]);

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  // Load AcroForm fields when overlay is enabled
  useEffect(() => {
    if (!showFieldOverlay || !documentId) {
      setAcroFormData(null);
      return;
    }

    const loadAcroFormFields = async () => {
      try {
        const data = await getAcroFormFields(documentId);
        setAcroFormData(data);
      } catch {
        // Silently fail - overlay just won't show
        setAcroFormData(null);
      }
    };

    loadAcroFormFields();
  }, [documentId, showFieldOverlay]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      if (newPage >= 1 && newPage <= pageCount) {
        setCurrentPage(newPage);
        onPageChange?.(newPage);
      }
    },
    [pageCount, onPageChange]
  );

  const handleZoomIn = useCallback(() => {
    const currentIndex = ZOOM_LEVELS.indexOf(zoom);
    if (currentIndex < ZOOM_LEVELS.length - 1) {
      setZoom(ZOOM_LEVELS[currentIndex + 1]);
    }
  }, [zoom]);

  const handleZoomOut = useCallback(() => {
    const currentIndex = ZOOM_LEVELS.indexOf(zoom);
    if (currentIndex > 0) {
      setZoom(ZOOM_LEVELS[currentIndex - 1]);
    }
  }, [zoom]);

  const handleFitWidth = useCallback(() => {
    setZoom(1);
  }, []);

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#f3f4f6',
    borderRadius: '8px',
    overflow: 'hidden',
    height: typeof height === 'number' ? `${height}px` : height,
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    backgroundColor: 'white',
    borderBottom: '1px solid #e5e7eb',
    flexShrink: 0,
  };

  const titleStyles: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    maxWidth: '200px',
  };

  const controlsStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  const viewportStyles: CSSProperties = {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '16px',
  };

  const imageContainerStyles: CSSProperties = {
    transform: `scale(${zoom})`,
    transformOrigin: 'center center',
    transition: 'transform 0.2s ease',
    position: 'relative',
  };

  const imageStyles: CSSProperties = {
    maxWidth: '100%',
    height: 'auto',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    borderRadius: '4px',
    backgroundColor: 'white',
  };

  const footerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    padding: '12px',
    backgroundColor: 'white',
    borderTop: '1px solid #e5e7eb',
    flexShrink: 0,
  };

  const paginationStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  return (
    <div style={containerStyles}>
      <div style={headerStyles}>
        {title && <span style={titleStyles} title={title}>{title}</span>}
        <div style={controlsStyles}>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomOut}
            disabled={zoom <= ZOOM_LEVELS[0]}
            aria-label="Zoom out"
          >
            -
          </Button>
          <span style={{ fontSize: '12px', color: '#6b7280', minWidth: '50px', textAlign: 'center' }}>
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomIn}
            disabled={zoom >= ZOOM_LEVELS[ZOOM_LEVELS.length - 1]}
            aria-label="Zoom in"
          >
            +
          </Button>
          <Button variant="ghost" size="sm" onClick={handleFitWidth}>
            Fit
          </Button>
        </div>
      </div>

      <div style={viewportStyles}>
        {loading && <LoadingSpinner size={32} />}
        {error && !loading && (
          <ErrorState
            message={error}
            onRetry={loadPage}
            style={{ maxWidth: '300px' }}
          />
        )}
        {!loading && !error && imageUrl && (
          <div style={imageContainerStyles}>
            <img
              ref={imageRef}
              src={imageUrl}
              alt={`Page ${currentPage} of ${pageCount}`}
              style={imageStyles}
              onLoad={(e) => {
                const img = e.currentTarget;
                setImageDimensions({ width: img.offsetWidth, height: img.offsetHeight });
              }}
              onError={() => setError('Failed to display image')}
            />
            {showFieldOverlay && acroFormData && acroFormData.has_acroform && imageDimensions && (
              <FieldOverlay
                fields={acroFormData.fields}
                currentPage={currentPage}
                previewScale={acroFormData.preview_scale}
                zoom={zoom}
                pageDimensions={
                  acroFormData.page_dimensions.find((p) => p.page === currentPage)
                    ? {
                        width: acroFormData.page_dimensions.find((p) => p.page === currentPage)!.width,
                        height: acroFormData.page_dimensions.find((p) => p.page === currentPage)!.height,
                      }
                    : undefined
                }
                imageDimensions={imageDimensions}
                onFieldClick={onFieldClick}
                onFieldHover={onFieldHover}
                highlightedFieldName={highlightedFieldName}
                highlightedAnchorBbox={highlightedAnchorBbox}
                editable={editable}
                onBboxChange={onFieldValueChange}
                fieldValues={fieldValues}
                fieldSaveStatus={fieldSaveStatus}
                fieldSaveErrors={fieldSaveErrors}
              />
            )}
          </div>
        )}
      </div>

      {pageCount > 1 && (
        <div style={footerStyles}>
          <div style={paginationStyles}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(1)}
              disabled={currentPage <= 1}
              aria-label="First page"
            >
              {'<<'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              aria-label="Previous page"
            >
              {'<'}
            </Button>
            <span style={{ fontSize: '13px', color: '#374151', minWidth: '100px', textAlign: 'center' }}>
              Page {currentPage} of {pageCount}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= pageCount}
              aria-label="Next page"
            >
              {'>'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(pageCount)}
              disabled={currentPage >= pageCount}
              aria-label="Last page"
            >
              {'>>'}
            </Button>
          </div>

          {/* Thumbnail navigation */}
          <div style={{ display: 'flex', gap: '4px', marginLeft: '16px' }}>
            {Array.from({ length: Math.min(pageCount, 10) }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                onClick={() => handlePageChange(page)}
                style={{
                  width: '28px',
                  height: '28px',
                  border: page === currentPage ? '2px solid #3b82f6' : '1px solid #d1d5db',
                  borderRadius: '4px',
                  backgroundColor: page === currentPage ? '#dbeafe' : 'white',
                  color: page === currentPage ? '#1d4ed8' : '#374151',
                  fontSize: '12px',
                  fontWeight: page === currentPage ? 600 : 400,
                  cursor: 'pointer',
                }}
                aria-label={`Go to page ${page}`}
                aria-current={page === currentPage ? 'page' : undefined}
              >
                {page}
              </button>
            ))}
            {pageCount > 10 && (
              <span style={{ fontSize: '12px', color: '#6b7280', padding: '0 4px' }}>...</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
