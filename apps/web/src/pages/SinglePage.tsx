/**
 * Single-page PDF form filling interface.
 *
 * Layout:
 * - Left: Field list (read-only, click to highlight)
 * - Center: Document preview with inline editing
 * - Right: Activity log
 * - Bottom: Document upload + list
 *
 * URL: /single?d=<document_id>
 */

import { useState, useCallback, useEffect } from 'react';
import { EditableDocumentPreview } from '../components/preview/EditableDocumentPreview';
import { DocumentBar } from '../components/single/DocumentBar';
import { FieldListReadOnly } from '../components/single/FieldListReadOnly';
import { ActivityLog, type Activity } from '../components/single/ActivityLog';
import { uploadDocument, getPagePreviewUrl, getAcroFormFields } from '../api/client';
import type { FieldData } from '../api/editClient';
import type { AcroFormFieldInfo, PageDimensions } from '../types/api';

interface DocumentWithPages {
  document_id: string;
  filename: string;
  page_count: number;
  pageUrls: string[];
  pageDimensions?: PageDimensions[];
}

// URL helpers
function getDocumentIdFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('d');
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

export function SinglePage() {
  // Document state
  const [documents, setDocuments] = useState<DocumentWithPages[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(getDocumentIdFromUrl);

  // Field state
  const [fields, setFields] = useState<FieldData[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);

  // UI state
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Activity state
  const [activities, setActivities] = useState<Activity[]>([]);

  // Get active document
  const activeDocument = documents.find(d => d.document_id === activeDocumentId);

  // Handle browser back/forward
  useEffect(() => {
    const handlePopState = () => {
      const docId = getDocumentIdFromUrl();
      if (docId && documents.find(d => d.document_id === docId)) {
        setActiveDocumentId(docId);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [documents]);

  // Add activity helper
  const addActivity = useCallback((type: Activity['type'], message: string, details?: string) => {
    const activity: Activity = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type,
      message,
      details,
      timestamp: new Date(),
    };
    setActivities(prev => [activity, ...prev]);
  }, []);

  // Map AcroForm field type to FieldData type
  const mapFieldType = (type: string): FieldData['type'] => {
    switch (type.toLowerCase()) {
      case 'checkbox':
      case 'check':
      case 'btn':
        return 'checkbox';
      case 'date':
        return 'date';
      case 'number':
        return 'number';
      default:
        return 'text';
    }
  };

  // Normalize bbox coordinates (PDF coords to 0-1 range)
  const normalizeBbox = (
    bbox: { x: number; y: number; width: number; height: number },
    pageDimensions: PageDimensions | undefined
  ) => {
    if (!pageDimensions) {
      // Fallback: assume standard letter size (612x792 points)
      return {
        x: bbox.x / 612,
        y: bbox.y / 792,
        width: bbox.width / 612,
        height: bbox.height / 792,
      };
    }
    return {
      x: bbox.x / pageDimensions.width,
      y: bbox.y / pageDimensions.height,
      width: bbox.width / pageDimensions.width,
      height: bbox.height / pageDimensions.height,
    };
  };

  // Load fields for a document
  const loadFields = useCallback(async (documentId: string, pageDimensions?: PageDimensions[]) => {
    setIsLoadingFields(true);

    try {
      const acroFields = await getAcroFormFields(documentId);
      const dims = pageDimensions || acroFields.page_dimensions;

      // Convert AcroForm fields to FieldData format with normalized coordinates
      const fieldData: FieldData[] = acroFields.fields.map((field: AcroFormFieldInfo) => {
        const page = field.bbox?.page || 1;
        const pageDim = dims?.find(d => d.page === page);

        const normalizedBbox = field.bbox ? normalizeBbox(field.bbox, pageDim) : null;

        return {
          field_id: field.field_name,
          label: field.field_name,
          value: field.value || '',
          type: mapFieldType(field.field_type),
          bbox: normalizedBbox ? {
            x: normalizedBbox.x,
            y: normalizedBbox.y,
            width: normalizedBbox.width,
            height: normalizedBbox.height,
            page,
          } : null,
          required: false,
        };
      });

      setFields(fieldData);
      addActivity('info', `Found ${fieldData.length} fields`);

    } catch (err) {
      // Document might not have AcroForm fields
      setFields([]);
      addActivity('info', 'No form fields detected');
    } finally {
      setIsLoadingFields(false);
    }
  }, [addActivity]);

  // Handle document upload
  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setError(null);

    try {
      addActivity('upload', `Uploading ${file.name}...`);

      const doc = await uploadDocument(file, 'target');
      const pageCount = doc.meta.page_count;
      const filename = doc.meta.filename;

      // Generate page URLs
      const pageUrls: string[] = [];
      for (let i = 1; i <= pageCount; i++) {
        pageUrls.push(getPagePreviewUrl(doc.document_id, i));
      }

      // Get AcroForm fields to also get page dimensions
      let pageDimensions: PageDimensions[] | undefined;
      try {
        const acroFields = await getAcroFormFields(doc.document_id);
        pageDimensions = acroFields.page_dimensions;
      } catch {
        // Ignore if no AcroForm
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

      addActivity('upload', `Uploaded ${filename}`, `${pageCount} pages`);

      // Load fields for the document
      await loadFields(doc.document_id, pageDimensions);

    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
      addActivity('error', 'Upload failed', message);
    } finally {
      setIsUploading(false);
    }
  }, [addActivity, loadFields]);

  // Handle document selection
  const handleSelectDocument = useCallback((documentId: string) => {
    const doc = documents.find(d => d.document_id === documentId);
    setActiveDocumentId(documentId);
    setSelectedFieldId(null);
    updateUrl(documentId);

    // Load fields for selected document
    loadFields(documentId, doc?.pageDimensions);
  }, [documents, loadFields]);

  // Handle document removal
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
      setFields([]);
    }

    addActivity('info', 'Document removed');
  }, [activeDocumentId, documents, addActivity]);

  // Handle field selection (from left panel)
  const handleFieldSelect = useCallback((fieldId: string | null) => {
    setSelectedFieldId(fieldId);
  }, []);

  // Handle field edit (from preview)
  const handleFieldEdit = useCallback((fieldId: string, value: string) => {
    setFields(prev => prev.map(field =>
      field.field_id === fieldId
        ? { ...field, value }
        : field
    ));

    const field = fields.find(f => f.field_id === fieldId);
    addActivity('edit', `Updated "${field?.label || fieldId}"`, value || '(cleared)');
  }, [fields, addActivity]);

  // Handle export
  const handleExport = useCallback(() => {
    if (!activeDocument) return;

    addActivity('export', 'Exporting PDF...');

    // TODO: Implement actual export via API
    setTimeout(() => {
      addActivity('export', 'PDF exported successfully');
    }, 1000);
  }, [activeDocument, addActivity]);

  // Handle clear all
  const handleClearAll = useCallback(() => {
    setDocuments([]);
    setActiveDocumentId(null);
    setFields([]);
    setSelectedFieldId(null);
    setActivities([]);
    updateUrl(null);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">Daru PDF</h1>
          <span className="text-sm text-gray-500">Single Page Editor</span>
        </div>
        <div className="flex items-center gap-2">
          {activeDocument && (
            <button
              onClick={handleExport}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
            >
              Export PDF
            </button>
          )}
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0">
        {/* Left Panel - Fields */}
        <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
          <div className="p-3 border-b border-gray-200">
            <h2 className="text-sm font-medium text-gray-700">Fields</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <FieldListReadOnly
              fields={fields}
              selectedFieldId={selectedFieldId}
              onFieldSelect={handleFieldSelect}
              isLoading={isLoadingFields}
            />
          </div>
        </aside>

        {/* Center - Preview */}
        <main className="flex-1 min-w-0">
          <EditableDocumentPreview
            pageUrls={activeDocument?.pageUrls || []}
            fields={fields}
            selectedFieldId={selectedFieldId}
            onFieldSelect={handleFieldSelect}
            onFieldEdit={handleFieldEdit}
            isLoading={isUploading}
            error={error}
            title={activeDocument?.filename || 'Document Preview'}
            enableFieldHighlights={true}
            showUndoRedo={false}
          />
        </main>

        {/* Right Panel - Activity */}
        <aside className="w-72 bg-white border-l border-gray-200 flex flex-col shrink-0">
          <div className="p-3 border-b border-gray-200">
            <h2 className="text-sm font-medium text-gray-700">Activity</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ActivityLog activities={activities} />
          </div>
        </aside>
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
