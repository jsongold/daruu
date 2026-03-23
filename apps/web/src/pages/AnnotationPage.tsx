/**
 * Annotation page: pair text labels with form field bounding boxes on a PDF.
 *
 * Layout (mirrors PromptingPage):
 * - Left: Pair list + toolbar
 * - Center: Document preview with annotation overlays
 * - Right: Label list
 * - Bottom: Document upload bar
 *
 * URL: /ann?d=<document_id>
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { DocumentBar } from '../components/single/DocumentBar';
import { AnnotationOverlay } from '../components/annotation/AnnotationOverlay';
import {
  uploadDocument,
  getPagePreviewUrl,
  getAcroFormFields,
  getDocument,
} from '../api/client';
import type { PageDimensions } from '../types/api';
import { PairList } from '../components/annotation/PairList';
import { AnnotationToolbar } from '../components/annotation/AnnotationToolbar';
import { useAnnotationStore } from '../hooks/useAnnotationStore';

// ============================================================================
// Types
// ============================================================================

interface DocumentWithPages {
  document_id: string;
  filename: string;
  page_count: number;
  pageUrls: string[];
  pageDimensions?: PageDimensions[];
}

// ============================================================================
// URL Helpers
// ============================================================================

function getDocumentIdFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  const id = params.get('d');
  if (id && /^[a-zA-Z0-9_-]+$/.test(id)) {
    return id;
  }
  return null;
}

function updateUrl(documentId: string | null): void {
  const url = new URL(window.location.href);
  if (documentId) {
    url.searchParams.set('d', documentId);
  } else {
    url.searchParams.delete('d');
  }
  window.history.pushState({}, '', url.toString());
}

// ============================================================================
// Component
// ============================================================================

export function AnnotationPage() {
  // Document state
  const [documents, setDocuments] = useState<DocumentWithPages[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(getDocumentIdFromUrl);

  // UI state
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Image size tracking for overlay coordinate mapping
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const imgRef = useRef<HTMLImageElement>(null);

  // Annotation store
  const store = useAnnotationStore();

  const activeDocument = documents.find(d => d.document_id === activeDocumentId);

  const handleImageLoad = useCallback(() => {
    if (imgRef.current) {
      setImageSize({
        width: imgRef.current.clientWidth,
        height: imgRef.current.clientHeight,
      });
    }
  }, []);

  // ---- Initialize from URL ----

  useEffect(() => {
    const initFromUrl = async () => {
      const docId = getDocumentIdFromUrl();
      if (!docId) return;
      if (documents.find(d => d.document_id === docId)) return;

      setIsUploading(true);
      setError(null);
      try {
        const doc = await getDocument(docId);
        const pageCount = doc.meta.page_count;
        const filename = doc.meta.filename;

        const pageUrls: string[] = [];
        for (let i = 1; i <= pageCount; i++) {
          pageUrls.push(getPagePreviewUrl(docId, i));
        }

        let pageDimensions: PageDimensions[] | undefined;
        try {
          const acroFields = await getAcroFormFields(docId);
          pageDimensions = acroFields.page_dimensions;
        } catch {
          // no acroform
        }

        const docWithPages: DocumentWithPages = {
          document_id: docId,
          filename,
          page_count: pageCount,
          pageUrls,
          pageDimensions,
        };

        setDocuments([docWithPages]);
        setActiveDocumentId(docId);

        await store.loadDocument(docId);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load document';
        setError(message);
        updateUrl(null);
        setActiveDocumentId(null);
      } finally {
        setIsUploading(false);
      }
    };

    initFromUrl();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Document handlers ----

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file, 'target');
      const pageCount = doc.meta.page_count;
      const filename = doc.meta.filename;

      const pageUrls: string[] = [];
      for (let i = 1; i <= pageCount; i++) {
        pageUrls.push(getPagePreviewUrl(doc.document_id, i));
      }

      let pageDimensions: PageDimensions[] | undefined;
      try {
        const acroFields = await getAcroFormFields(doc.document_id);
        pageDimensions = acroFields.page_dimensions;
      } catch {
        // no acroform
      }

      const docWithPages: DocumentWithPages = {
        document_id: doc.document_id,
        filename,
        page_count: pageCount,
        pageUrls,
        pageDimensions,
      };

      setDocuments(prev => [...prev, docWithPages]);
      setActiveDocumentId(doc.document_id);
      updateUrl(doc.document_id);
      await store.loadDocument(doc.document_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
    } finally {
      setIsUploading(false);
    }
  }, [store.loadDocument]);

  const handleSelectDocument = useCallback((documentId: string) => {
    const doc = documents.find(d => d.document_id === documentId);
    setActiveDocumentId(documentId);
    updateUrl(documentId);
    if (doc) {
      store.loadDocument(documentId);
    }
  }, [documents, store.loadDocument]);

  const handleRemoveDocument = useCallback((documentId: string) => {
    setDocuments(prev => prev.filter(d => d.document_id !== documentId));
    if (activeDocumentId === documentId) {
      const remaining = documents.filter(d => d.document_id !== documentId);
      if (remaining.length > 0) {
        setActiveDocumentId(remaining[0].document_id);
        updateUrl(remaining[0].document_id);
      } else {
        setActiveDocumentId(null);
        updateUrl(null);
      }
    }
  }, [activeDocumentId, documents]);

  const handleClearAll = useCallback(() => {
    setDocuments([]);
    setActiveDocumentId(null);
    store.clearPairs();
    updateUrl(null);
  }, [store.clearPairs]);

  // ---- Render ----

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">Annotation Tool</h1>
          <span className="text-sm text-gray-500">Label & Bbox Pairing</span>
        </div>
        <div className="flex items-center gap-2">
          {store.doc.pairs.length > 0 && (
            <button
              onClick={store.exportJson}
              className="px-4 py-2 bg-gray-600 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors"
            >
              Export JSON
            </button>
          )}
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Left Panel - Pairs + Toolbar */}
        <aside className="w-72 min-w-[288px] bg-white border-r border-gray-200 flex flex-col shrink-0">
          <div className="p-3 border-b border-gray-200">
            <AnnotationToolbar
              mode={store.mode}
              totalLabels={store.doc.labels.length}
              totalFields={store.doc.fields.length}
              pairedCount={store.doc.pairs.length}
              aiLoading={store.aiLoading}
              onRunAi={store.runAi}
              onExport={store.exportJson}
              onClear={store.clearPairs}
              onCancel={store.clickEmpty}
            />
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <PairList
              pairs={store.doc.pairs}
              onFocusLabel={store.focusPairFromList}
              onDeletePair={store.deletePair}
            />
          </div>
        </aside>

        {/* Center - PDF Preview with Annotation Overlays */}
        <main className="flex-1 min-w-0 overflow-hidden flex flex-col">
          {/* Top bar */}
          <div className="h-10 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0">
            <span className="text-xs text-gray-500">
              {activeDocument?.filename || 'No document'}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => store.setPage(store.doc.currentPage - 1)}
                disabled={store.doc.currentPage <= 1}
                className="px-2 py-1 text-xs text-gray-600 rounded hover:bg-gray-100 disabled:text-gray-300 disabled:cursor-not-allowed"
              >
                Prev
              </button>
              <span className="text-xs text-gray-500">
                {store.doc.currentPage} / {store.doc.totalPages || '-'}
              </span>
              <button
                onClick={() => store.setPage(store.doc.currentPage + 1)}
                disabled={store.doc.currentPage >= store.doc.totalPages}
                className="px-2 py-1 text-xs text-gray-600 rounded hover:bg-gray-100 disabled:text-gray-300 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>

          {/* PDF canvas with overlays */}
          <div className="flex-1 flex items-center justify-center overflow-hidden bg-gray-100 p-4">
            {store.loading ? (
              <div className="text-sm text-gray-400">Loading document...</div>
            ) : (store.error || error) ? (
              <div className="text-sm text-red-500">{store.error || error}</div>
            ) : activeDocument && store.doc.totalPages > 0 ? (
              <TransformWrapper
                initialScale={1}
                minScale={0.3}
                maxScale={4}
                wheel={{ step: 0.1 }}
              >
                <TransformComponent
                  wrapperStyle={{ width: '100%', height: '100%', overflow: 'hidden' }}
                  contentStyle={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}
                >
                  <div
                    style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', maxHeight: '100%' }}
                    onClick={() => store.clickEmpty()}
                  >
                    <img
                      ref={imgRef}
                      src={getPagePreviewUrl(activeDocument.document_id, store.doc.currentPage)}
                      alt={`Page ${store.doc.currentPage}`}
                      onLoad={handleImageLoad}
                      style={{
                        maxHeight: 'calc(100vh - 200px)',
                        width: 'auto',
                        display: 'block',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                      }}
                      draggable={false}
                    />
                    {imageSize.width > 0 && (
                      <AnnotationOverlay
                        config={store.overlayConfig}
                        onLabelClick={store.clickLabel}
                        onFieldClick={store.clickField}
                        containerWidth={imageSize.width}
                        containerHeight={imageSize.height}
                      />
                    )}
                  </div>
                </TransformComponent>
              </TransformWrapper>
            ) : (
              <div className="text-sm text-gray-400">Upload a document to start annotating</div>
            )}
          </div>
        </main>
      </div>

      {/* Bottom - Document Bar */}
      <DocumentBar
        documents={documents}
        activeDocumentId={activeDocumentId}
        onUpload={handleUpload}
        onSelect={handleSelectDocument}
        onRemove={handleRemoveDocument}
        onClearAll={handleClearAll}
        isUploading={isUploading}
      />
    </div>
  );
}
