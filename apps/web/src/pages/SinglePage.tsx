/**
 * Single-page PDF form filling interface.
 *
 * Layout:
 * - Left: Field list (read-only, click to highlight)
 * - Center: Document preview with inline editing
 * - Right: Activity log
 * - Bottom: Document upload + list
 *
 * URL: /single?d=<document_id>&c=<conversation_id>
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { EditableDocumentPreview } from '../components/preview/EditableDocumentPreview';
import { DocumentBar } from '../components/single/DocumentBar';
import { FieldListReadOnly } from '../components/single/FieldListReadOnly';
import { ActivityLog, type Activity } from '../components/single/ActivityLog';
import { uploadDocument, getPagePreviewUrl, getAcroFormFields, getDocument, fillAndDownloadPdf } from '../api/client';
import { createConversation, getConversation } from '../api/conversationClient';
import { autofillWithVision } from '../api/autofillClient';
import { updateField as apiUpdateField, getFields as apiGetFields } from '../api/editClient';
import { useDataSources } from '../hooks/useDataSources';
import type { FieldData, FontStyle } from '../api/editClient';
import type { AcroFormFieldInfo, PageDimensions } from '../types/api';

interface DocumentWithPages {
  document_id: string;
  document_ref: string;
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

function getConversationIdFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('c');
}

function updateUrl(documentId: string | null, conversationId?: string | null): void {
  const url = new URL(window.location.href);
  if (documentId) {
    url.searchParams.set('d', documentId);
  } else {
    url.searchParams.delete('d');
  }
  if (conversationId) {
    url.searchParams.set('c', conversationId);
  } else if (conversationId === null) {
    url.searchParams.delete('c');
  }
  window.history.pushState({}, '', url.toString());
}

export function SinglePage() {
  // Document state
  const [documents, setDocuments] = useState<DocumentWithPages[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(getDocumentIdFromUrl);

  // Conversation state (persisted in URL for reload support)
  const [conversationId, setConversationId] = useState<string | null>(getConversationIdFromUrl);

  // Track pending saves to avoid race conditions
  const pendingSaveRef = useRef<AbortController | null>(null);

  // Field state
  const [fields, setFields] = useState<FieldData[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);

  // UI state
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isAutofilling, setIsAutofilling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Activity state
  const [activities, setActivities] = useState<Activity[]>([]);

  // Data sources hook
  const {
    dataSources,
    isUploading: isDataSourceUploading,
    uploadFiles: uploadDataSourceFiles,
    createText: createDataSourceText,
    remove: removeDataSource,
    error: dataSourceError,
  } = useDataSources(conversationId);

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

  // Helper: ensure a conversation exists (reuse from URL or create new)
  const ensureConversation = useCallback(async (filename: string): Promise<string | null> => {
    const existingConvId = getConversationIdFromUrl();

    // Try to reuse conversation from URL
    if (existingConvId) {
      try {
        await getConversation(existingConvId);
        console.log('[SinglePage] Reusing conversation from URL:', existingConvId);
        setConversationId(existingConvId);
        return existingConvId;
      } catch {
        console.warn('[SinglePage] Conversation from URL not found, creating new');
      }
    }

    // Create a new conversation
    try {
      const conversation = await createConversation({
        title: `SinglePage: ${filename}`,
      });
      setConversationId(conversation.id);
      console.log('[SinglePage] Created conversation:', conversation.id);
      return conversation.id;
    } catch (convErr) {
      console.warn('[SinglePage] Failed to create conversation:', convErr);
      return null;
    }
  }, []);

  // Initialize document from URL on mount
  useEffect(() => {
    const initDocumentFromUrl = async () => {
      const docId = getDocumentIdFromUrl();
      if (!docId) return;

      // Check if already loaded
      if (documents.find(d => d.document_id === docId)) return;

      console.log('[SinglePage] Loading document from URL:', docId);
      setIsUploading(true);
      setError(null);

      try {
        // Fetch document details from API
        const doc = await getDocument(docId);
        const pageCount = doc.meta.page_count;
        const filename = doc.meta.filename;

        console.log('[SinglePage] Document loaded:', { docId, filename, pageCount });

        // Generate page URLs
        const pageUrls: string[] = [];
        for (let i = 1; i <= pageCount; i++) {
          pageUrls.push(getPagePreviewUrl(docId, i));
        }

        // Get AcroForm fields to also get page dimensions
        let pageDimensions: PageDimensions[] | undefined;
        try {
          const acroFields = await getAcroFormFields(docId);
          pageDimensions = acroFields.page_dimensions;
          console.log('[SinglePage] Page dimensions:', pageDimensions);
        } catch (e) {
          console.log('[SinglePage] No AcroForm fields:', e);
        }

        const docWithPages: DocumentWithPages = {
          document_id: docId,
          document_ref: doc.document_ref,
          filename,
          page_count: pageCount,
          pageUrls,
          pageDimensions,
        };

        setDocuments([docWithPages]);
        setActiveDocumentId(docId);
        addActivity('info', `Loaded ${filename}`, `${pageCount} pages`);

        // Ensure conversation exists (reuse or create)
        const convId = await ensureConversation(filename);

        // Persist both document and conversation in URL
        updateUrl(docId, convId);

        // Load fields for the document, then merge saved edits from backend
        await loadFields(docId, pageDimensions, convId);

      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load document';
        console.error('[SinglePage] Error loading document:', err);
        setError(message);
        addActivity('error', 'Failed to load document', message);
        // Clear the invalid document ID from URL
        updateUrl(null, null);
        setActiveDocumentId(null);
      } finally {
        setIsUploading(false);
      }
    };

    initDocumentFromUrl();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount

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

  // Load fields for a document, optionally merging saved edits from the backend
  const loadFields = useCallback(async (documentId: string, pageDimensions?: PageDimensions[], convId?: string | null) => {
    setIsLoadingFields(true);
    console.log('[SinglePage] Loading fields for document:', documentId);

    try {
      const acroFields = await getAcroFormFields(documentId);
      const dims = pageDimensions || acroFields.page_dimensions;
      console.log('[SinglePage] AcroForm response:', {
        fieldCount: acroFields.fields.length,
        dims,
        hasAcroform: acroFields.has_acroform
      });

      // Convert AcroForm fields to FieldData format with normalized coordinates
      const fieldData: FieldData[] = acroFields.fields.map((field: AcroFormFieldInfo) => {
        const page = field.bbox?.page || 1;
        const pageDim = dims?.find(d => d.page === page);

        const normalizedBbox = field.bbox ? normalizeBbox(field.bbox, pageDim) : null;

        // Debug log first few fields
        if (acroFields.fields.indexOf(field) < 3) {
          console.log('[SinglePage] Field normalization:', {
            name: field.field_name,
            originalBbox: field.bbox,
            pageDim,
            normalizedBbox,
          });
        }

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

      // Try to restore saved edits from the backend
      const activeConvId = convId ?? conversationId;
      let restoredCount = 0;

      if (activeConvId) {
        try {
          const savedFields = await apiGetFields(activeConvId);
          if (savedFields.fields.length > 0) {
            const savedMap = new Map(savedFields.fields.map(f => [f.field_id, f]));

            const mergedFields = fieldData.map(field => {
              const saved = savedMap.get(field.field_id);
              if (saved?.value) {
                restoredCount++;
                return { ...field, value: saved.value };
              }
              return field;
            });

            setFields(mergedFields);
            console.log('[SinglePage] Fields loaded:', mergedFields.length, `(${restoredCount} restored from backend)`);
            addActivity('info', `Found ${mergedFields.length} fields${restoredCount > 0 ? ` (${restoredCount} values restored)` : ''}`);
            return;
          }
        } catch (err) {
          console.warn('[SinglePage] Could not load saved edits from backend:', err);
        }
      }

      setFields(fieldData);
      console.log('[SinglePage] Fields loaded:', fieldData.length);
      addActivity('info', `Found ${fieldData.length} fields`);

    } catch (err) {
      // Document might not have AcroForm fields
      setFields([]);
      addActivity('info', 'No form fields detected');
    } finally {
      setIsLoadingFields(false);
    }
  }, [addActivity, conversationId]);

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
        document_ref: doc.document_ref,
        filename,
        page_count: pageCount,
        pageUrls,
        pageDimensions,
      };

      setDocuments(prev => [...prev, docWithPages]);
      setActiveDocumentId(doc.document_id);

      addActivity('upload', `Uploaded ${filename}`, `${pageCount} pages`);

      // Ensure conversation exists
      const convId = await ensureConversation(filename);

      // Persist both document and conversation in URL
      updateUrl(doc.document_id, convId);

      // Load fields for the document
      await loadFields(doc.document_id, pageDimensions, convId);

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
    updateUrl(documentId, conversationId);

    // Load fields for selected document
    loadFields(documentId, doc?.pageDimensions, conversationId);
  }, [documents, conversationId, loadFields]);

  // Handle document removal
  const handleRemoveDocument = useCallback((documentId: string) => {
    setDocuments(prev => prev.filter(d => d.document_id !== documentId));

    if (activeDocumentId === documentId) {
      const remaining = documents.filter(d => d.document_id !== documentId);
      if (remaining.length > 0) {
        setActiveDocumentId(remaining[0].document_id);
        updateUrl(remaining[0].document_id, conversationId);
      } else {
        setActiveDocumentId(null);
        updateUrl(null, null);
      }
      setFields([]);
    }

    addActivity('info', 'Document removed');
  }, [activeDocumentId, documents, conversationId, addActivity]);

  // Handle field selection (from left panel)
  const handleFieldSelect = useCallback((fieldId: string | null) => {
    setSelectedFieldId(fieldId);
  }, []);

  // Handle field edit (from preview) - updates state and persists to backend
  const handleFieldEdit = useCallback((fieldId: string, value: string, fontStyle?: FontStyle) => {
    setFields(prev => prev.map(field =>
      field.field_id === fieldId
        ? { ...field, value, ...(fontStyle && { fontStyle }) }
        : field
    ));

    const field = fields.find(f => f.field_id === fieldId);
    addActivity('edit', `Updated "${field?.label || fieldId}"`, value || '(cleared)');

    // Persist to backend (fire-and-forget, cancel previous pending save for same field)
    if (conversationId) {
      if (pendingSaveRef.current) {
        pendingSaveRef.current.abort();
      }
      const controller = new AbortController();
      pendingSaveRef.current = controller;

      apiUpdateField(conversationId, fieldId, value, 'inline')
        .then(() => {
          if (!controller.signal.aborted) {
            console.log('[SinglePage] Field saved to backend:', fieldId);
          }
        })
        .catch((err) => {
          if (!controller.signal.aborted) {
            console.warn('[SinglePage] Failed to save field to backend:', err);
          }
        });
    }
  }, [fields, conversationId, addActivity]);

  // Convert hex color to RGB tuple [0-1, 0-1, 0-1]
  const hexToRgbTuple = (hex: string): [number, number, number] => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (result) {
      return [
        parseInt(result[1], 16) / 255,
        parseInt(result[2], 16) / 255,
        parseInt(result[3], 16) / 255,
      ];
    }
    return [0, 0, 0]; // Default to black
  };

  // Handle export
  const handleExport = useCallback(async () => {
    if (!activeDocument) return;

    // Filter fields that have values
    const fieldsWithValues = fields.filter(field => field.value);

    if (fieldsWithValues.length === 0) {
      addActivity('error', 'Cannot export', 'Please fill in at least one field before exporting');
      return;
    }

    setIsExporting(true);
    addActivity('export', 'Exporting PDF...');

    try {
      // Collect field values with bbox coordinates for the fill service
      // Need to denormalize bbox back to PDF points for the API
      const fillFields = fieldsWithValues
        .map(field => {
          // Find page dimensions to denormalize coordinates
          const pageDim = activeDocument.pageDimensions?.find(
            d => d.page === (field.bbox?.page || 1)
          );

          // Denormalize bbox from 0-1 range back to PDF points
          let denormalizedBbox: {
            x: number;
            y: number;
            width: number;
            height: number;
            page: number;
          } | null = null;

          if (field.bbox && pageDim) {
            denormalizedBbox = {
              x: field.bbox.x * pageDim.width,
              y: field.bbox.y * pageDim.height,
              width: field.bbox.width * pageDim.width,
              height: field.bbox.height * pageDim.height,
              page: field.bbox.page,
            };
          } else if (field.bbox) {
            // Fallback: assume standard letter size if no dimensions
            denormalizedBbox = {
              x: field.bbox.x * 612,
              y: field.bbox.y * 792,
              width: field.bbox.width * 612,
              height: field.bbox.height * 792,
              page: field.bbox.page,
            };
          }

          return {
            field_id: field.field_id,
            value: field.value,
            ...(denormalizedBbox && {
              x: denormalizedBbox.x,
              y: denormalizedBbox.y,
              width: denormalizedBbox.width,
              height: denormalizedBbox.height,
              page: denormalizedBbox.page,
            }),
          };
        });

      // Collect per-field font style parameters
      const fieldParams: Record<string, {
        font_name?: string;
        font_size?: number;
        font_color?: [number, number, number];
        alignment?: 'left' | 'center' | 'right';
      }> = {};

      fieldsWithValues.forEach(field => {
        if (field.fontStyle) {
          const params: typeof fieldParams[string] = {};
          if (field.fontStyle.fontFamily) {
            params.font_name = field.fontStyle.fontFamily;
          }
          if (field.fontStyle.fontSize) {
            params.font_size = field.fontStyle.fontSize;
          }
          if (field.fontStyle.fontColor) {
            params.font_color = hexToRgbTuple(field.fontStyle.fontColor);
          }
          if (field.fontStyle.alignment) {
            params.alignment = field.fontStyle.alignment;
          }
          if (Object.keys(params).length > 0) {
            fieldParams[field.field_id] = params;
          }
        }
      });

      // Generate download filename from original filename
      const baseName = activeDocument.filename.replace(/\.pdf$/i, '');
      const downloadFilename = `${baseName}-filled.pdf`;

      // Call fill service and trigger download
      const result = await fillAndDownloadPdf(
        activeDocument.document_ref,
        fillFields,
        downloadFilename,
        'auto',
        Object.keys(fieldParams).length > 0 ? fieldParams : undefined
      );

      addActivity(
        'export',
        'PDF exported successfully',
        `Filled ${result.filledCount} fields${result.failedCount > 0 ? `, ${result.failedCount} failed` : ''}`
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed';
      addActivity('error', 'Export failed', message);
      // Don't set global error - it would hide the preview
    } finally {
      setIsExporting(false);
    }
  }, [activeDocument, fields, addActivity]);

  // Handle autofill
  const handleAutofill = useCallback(async () => {
    if (!activeDocument || !conversationId) {
      addActivity('error', 'Cannot auto-fill', 'No document or conversation');
      return;
    }

    if (dataSources.length === 0) {
      addActivity('error', 'Cannot auto-fill', 'Add data sources first');
      return;
    }

    setIsAutofilling(true);
    addActivity('info', 'Running AI auto-fill...');

    try {
      const result = await autofillWithVision(
        activeDocument.document_id,
        conversationId,
        fields.map(f => ({
          field_id: f.field_id,
          label: f.label,
          type: f.type,
          bbox: f.bbox,
        }))
      );

      if (result.success && result.filled_fields.length > 0) {
        // Apply filled values to fields
        setFields(prev => prev.map(field => {
          const filled = result.filled_fields.find(f => f.field_id === field.field_id);
          return filled ? { ...field, value: filled.value } : field;
        }));

        // Persist autofill results to backend
        if (conversationId) {
          for (const filled of result.filled_fields) {
            apiUpdateField(conversationId, filled.field_id, filled.value, 'inline')
              .catch(err => console.warn('[SinglePage] Failed to save autofill value:', err));
          }
        }

        addActivity(
          'info',
          `Auto-filled ${result.filled_fields.length} fields`,
          result.unfilled_fields.length > 0
            ? `${result.unfilled_fields.length} fields could not be filled`
            : undefined
        );

        // Log any warnings
        result.warnings.forEach(warning => {
          addActivity('info', 'Auto-fill warning', warning);
        });
      } else {
        addActivity(
          'error',
          'Auto-fill found no matches',
          result.error || 'Try adding more data sources'
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Auto-fill failed';
      addActivity('error', 'Auto-fill failed', message);
      // Don't set global error - it would hide the preview
    } finally {
      setIsAutofilling(false);
    }
  }, [activeDocument, conversationId, dataSources.length, fields, addActivity]);

  // Handle clear all
  const handleClearAll = useCallback(() => {
    setDocuments([]);
    setActiveDocumentId(null);
    setConversationId(null);
    setFields([]);
    setSelectedFieldId(null);
    setActivities([]);
    updateUrl(null, null);
  }, []);

  // Data source handlers
  const handleDataSourceUpload = useCallback(async (files: File[]) => {
    const results = await uploadDataSourceFiles(files);
    if (results.length > 0) {
      addActivity('upload', `Added ${results.length} data source(s)`, results.map(r => r.name).join(', '));
    }
  }, [uploadDataSourceFiles, addActivity]);

  const handleDataSourceTextAdd = useCallback(async (name: string, content: string) => {
    const result = await createDataSourceText(name, content);
    if (result) {
      addActivity('upload', `Added text data: ${name}`);
    }
  }, [createDataSourceText, addActivity]);

  const handleDataSourceRemove = useCallback(async (id: string) => {
    const source = dataSources.find(ds => ds.id === id);
    const removed = await removeDataSource(id);
    if (removed && source) {
      addActivity('info', `Removed data source: ${source.name}`);
    }
  }, [removeDataSource, dataSources, addActivity]);

  // Log data source errors
  useEffect(() => {
    if (dataSourceError) {
      addActivity('error', 'Data source error', dataSourceError);
    }
  }, [dataSourceError, addActivity]);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">Daru PDF</h1>
          <span className="text-sm text-gray-500">Single Page Editor</span>
        </div>
        <div className="flex items-center gap-2">
          {activeDocument && conversationId && dataSources.length > 0 && (
            <button
              onClick={handleAutofill}
              disabled={isAutofilling}
              className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors disabled:bg-green-400 disabled:cursor-not-allowed"
            >
              {isAutofilling ? 'Auto-filling...' : 'Auto-Fill'}
            </button>
          )}
          {activeDocument && (
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:bg-blue-400 disabled:cursor-not-allowed"
            >
              {isExporting ? 'Exporting...' : 'Export PDF'}
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
        // Data sources props
        dataSources={dataSources}
        onDataSourceUpload={handleDataSourceUpload}
        onDataSourceTextAdd={handleDataSourceTextAdd}
        onDataSourceRemove={handleDataSourceRemove}
        isDataSourceUploading={isDataSourceUploading}
      />
    </div>
  );
}
