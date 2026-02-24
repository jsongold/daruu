/**
 * Prompt Tuning page for vision autofill.
 *
 * Layout:
 * - Left: Field list (read-only, click to highlight)
 * - Center: Document preview with field highlights
 * - Right: Tabbed panel (Prompt Editor | Results | Activity Log)
 * - Bottom: Document upload + data sources
 *
 * URL: /prompt_tuning?d=<document_id>&c=<conversation_id>
 */

import { useState, useCallback, useEffect } from 'react';
import { EditableDocumentPreview } from '../components/preview/EditableDocumentPreview';
import { DocumentBar } from '../components/single/DocumentBar';
import { FieldListReadOnly } from '../components/single/FieldListReadOnly';
import { ActivityLog, type Activity } from '../components/single/ActivityLog';
import { PipelineLogPanel } from '../components/single/PipelineLogPanel';
import {
  uploadDocument,
  getPagePreviewUrl,
  getAcroFormFields,
  getDocument,
} from '../api/client';
import { createConversation, getConversation } from '../api/conversationClient';
import { autofillWithVision, previewPrompt } from '../api/autofillClient';
import type { VisionAutofillResponse, PromptPreviewResponse } from '../api/autofillClient';
import { autofillPipeline } from '../api/autofillPipelineClient';
import type { AutofillMode, PipelineStepLog } from '../api/autofillPipelineClient';
import { listPromptAttempts, getPromptAttempt } from '../api/promptAttemptClient';
import type { PromptAttempt } from '../api/promptAttemptClient';
import { useDataSources } from '../hooks/useDataSources';
import type { FieldData } from '../api/editClient';
import type { AcroFormFieldInfo, PageDimensions } from '../types/api';

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

type RightTab = 'prompt' | 'results' | 'pipeline' | 'history' | 'activity';

// ============================================================================
// URL Helpers
// ============================================================================

function getDocumentIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('d');
}

function getConversationIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('c');
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

// ============================================================================
// Field helpers (same as SinglePage)
// ============================================================================

function mapFieldType(type: string): FieldData['type'] {
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
}

function normalizeBbox(
  bbox: { x: number; y: number; width: number; height: number },
  pageDimensions: PageDimensions | undefined
) {
  const pw = pageDimensions?.width ?? 612;
  const ph = pageDimensions?.height ?? 792;
  return {
    x: bbox.x / pw,
    y: bbox.y / ph,
    width: bbox.width / pw,
    height: bbox.height / ph,
  };
}

// ============================================================================
// Component
// ============================================================================

export function PromptingPage() {
  // Document state
  const [documents, setDocuments] = useState<DocumentWithPages[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(getDocumentIdFromUrl);

  // Conversation state
  const [conversationId, setConversationId] = useState<string | null>(getConversationIdFromUrl);

  // Field state
  const [fields, setFields] = useState<FieldData[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);

  // UI state
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [isPreviewingPrompt, setIsPreviewingPrompt] = useState(false);
  const [isAutofilling, setIsAutofilling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Right panel tab
  const [activeTab, setActiveTab] = useState<RightTab>('prompt');

  // Prompt editor state
  const [systemPrompt, setSystemPrompt] = useState('');
  const [customRules, setCustomRules] = useState<string[]>([]);
  const [newRule, setNewRule] = useState('');

  // Preview state
  const [previewedPrompt, setPreviewedPrompt] = useState<PromptPreviewResponse | null>(null);

  // Results state
  const [autofillResult, setAutofillResult] = useState<VisionAutofillResponse | null>(null);
  const [confidenceMap, setConfidenceMap] = useState<Record<string, number>>({});

  // History state
  const [promptAttempts, setPromptAttempts] = useState<PromptAttempt[]>([]);
  const [promptAttemptsTotal, setPromptAttemptsTotal] = useState(0);
  const [selectedAttempt, setSelectedAttempt] = useState<PromptAttempt | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Autofill mode state
  const [autofillMode, setAutofillMode] = useState<AutofillMode>('quick');

  // Pipeline step logs state
  const [pipelineStepLogs, setPipelineStepLogs] = useState<PipelineStepLog[]>([]);

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

  const activeDocument = documents.find(d => d.document_id === activeDocumentId);

  // ---- Helpers ----

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

  const loadHistory = useCallback(async (convId: string) => {
    setIsLoadingHistory(true);
    try {
      const result = await listPromptAttempts(convId);
      setPromptAttempts(result.items);
      setPromptAttemptsTotal(result.total);
    } catch {
      // history load is best-effort
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const ensureConversation = useCallback(async (filename: string): Promise<string | null> => {
    const existingConvId = getConversationIdFromUrl();
    if (existingConvId) {
      try {
        await getConversation(existingConvId);
        setConversationId(existingConvId);
        return existingConvId;
      } catch {
        // conversation not found, create new
      }
    }
    try {
      const conversation = await createConversation({
        title: `Prompting: ${filename}`,
      });
      setConversationId(conversation.id);
      return conversation.id;
    } catch (convErr) {
      console.warn('[PromptingPage] Failed to create conversation:', convErr);
      return null;
    }
  }, []);

  const loadFields = useCallback(async (documentId: string, pageDimensions?: PageDimensions[]) => {
    setIsLoadingFields(true);
    try {
      const acroFields = await getAcroFormFields(documentId);
      const dims = pageDimensions || acroFields.page_dimensions;

      const fieldData: FieldData[] = acroFields.fields.map((field: AcroFormFieldInfo) => {
        const page = field.bbox?.page || 1;
        const pageDim = dims?.find(d => d.page === page);
        const normalized = field.bbox ? normalizeBbox(field.bbox, pageDim) : null;

        return {
          field_id: field.field_name,
          label: field.field_name,
          value: field.value || '',
          type: mapFieldType(field.field_type),
          bbox: normalized ? { x: normalized.x, y: normalized.y, width: normalized.width, height: normalized.height, page } : null,
          required: false,
        };
      });

      setFields(fieldData);
      addActivity('info', `Found ${fieldData.length} fields`);
    } catch {
      setFields([]);
      addActivity('info', 'No form fields detected');
    } finally {
      setIsLoadingFields(false);
    }
  }, [addActivity]);

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
        addActivity('info', `Loaded ${filename}`, `${pageCount} pages`);

        const convId = await ensureConversation(filename);
        updateUrl(docId, convId);
        await loadFields(docId, pageDimensions);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load document';
        setError(message);
        addActivity('error', 'Failed to load document', message);
        updateUrl(null, null);
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
      addActivity('upload', `Uploading ${file.name}...`);
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
      addActivity('upload', `Uploaded ${filename}`, `${pageCount} pages`);

      const convId = await ensureConversation(filename);
      updateUrl(doc.document_id, convId);
      await loadFields(doc.document_id, pageDimensions);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
      addActivity('error', 'Upload failed', message);
    } finally {
      setIsUploading(false);
    }
  }, [addActivity, loadFields, ensureConversation]);

  const handleSelectDocument = useCallback((documentId: string) => {
    const doc = documents.find(d => d.document_id === documentId);
    setActiveDocumentId(documentId);
    setSelectedFieldId(null);
    updateUrl(documentId, conversationId);
    loadFields(documentId, doc?.pageDimensions);
  }, [documents, conversationId, loadFields]);

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

  const handleClearAll = useCallback(() => {
    setDocuments([]);
    setActiveDocumentId(null);
    setConversationId(null);
    setFields([]);
    setSelectedFieldId(null);
    setActivities([]);
    setAutofillResult(null);
    setPreviewedPrompt(null);
    setConfidenceMap({});
    setPipelineStepLogs([]);
    updateUrl(null, null);
  }, []);

  // ---- Data source handlers ----

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

  useEffect(() => {
    if (dataSourceError) {
      addActivity('error', 'Data source error', dataSourceError);
    }
  }, [dataSourceError, addActivity]);

  // Load attempt history when conversation is available
  useEffect(() => {
    if (conversationId) {
      loadHistory(conversationId);
    }
  }, [conversationId, loadHistory]);

  // ---- Prompt actions ----

  const buildRequestFields = useCallback(() => {
    return fields.map(f => ({
      field_id: f.field_id,
      label: f.label,
      type: f.type,
      bbox: f.bbox,
    }));
  }, [fields]);

  const handlePreviewPrompt = useCallback(async () => {
    if (!activeDocument || !conversationId) return;

    setIsPreviewingPrompt(true);
    setActiveTab('prompt');
    addActivity('info', 'Previewing prompt...');

    try {
      const result = await previewPrompt({
        document_id: activeDocument.document_id,
        conversation_id: conversationId,
        fields: buildRequestFields(),
        rules: customRules.length > 0 ? customRules : undefined,
        ...(systemPrompt.trim() && { system_prompt: systemPrompt }),
      });

      setPreviewedPrompt(result);
      // Initialize system prompt editor if user hasn't edited it yet
      if (!systemPrompt.trim()) {
        setSystemPrompt(result.system_prompt);
      }
      addActivity('info', 'Prompt preview ready', `${result.data_source_count} data source(s)`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Preview failed';
      addActivity('error', 'Preview prompt failed', message);
    } finally {
      setIsPreviewingPrompt(false);
    }
  }, [activeDocument, conversationId, fields, customRules, systemPrompt, buildRequestFields, addActivity]);

  const handleRunAutofill = useCallback(async () => {
    if (!activeDocument || !conversationId) {
      addActivity('error', 'Cannot auto-fill', 'No document or conversation');
      return;
    }
    if (dataSources.length === 0) {
      addActivity('error', 'Cannot auto-fill', 'Add data sources first');
      return;
    }

    setIsAutofilling(true);
    setActiveTab('results');
    setPipelineStepLogs([]);
    addActivity('info', 'Running AI auto-fill...');

    const requestFields = buildRequestFields();

    // Run vision autofill + pipeline autofill in parallel
    // Vision autofill: used for Results tab (records prompt attempts)
    // Pipeline autofill: used for Pipeline tab (captures step logs)
    const visionPromise = autofillWithVision(
      activeDocument.document_id,
      conversationId,
      requestFields,
      customRules.length > 0 ? customRules : undefined,
      systemPrompt.trim() || undefined,
    );

    const pipelinePromise = autofillPipeline({
      document_id: activeDocument.document_id,
      conversation_id: conversationId,
      fields: requestFields.map(f => ({
        field_id: f.field_id,
        label: f.label,
        type: f.type,
        x: f.bbox?.x ?? null,
        y: f.bbox?.y ?? null,
        width: f.bbox?.width ?? null,
        height: f.bbox?.height ?? null,
        page: f.bbox?.page ?? null,
      })),
      rules: customRules.length > 0 ? customRules : undefined,
      mode: autofillMode,
    }).catch(err => {
      // Pipeline call is best-effort for logging; don't block main flow
      addActivity('info', 'Pipeline logs unavailable', err instanceof Error ? err.message : String(err));
      return null;
    });

    try {
      const [result, pipelineResult] = await Promise.all([visionPromise, pipelinePromise]);

      setAutofillResult(result);

      // Capture pipeline step logs
      if (pipelineResult?.step_logs) {
        setPipelineStepLogs(pipelineResult.step_logs);
        setActiveTab('pipeline');
      }

      if (result.success && result.filled_fields.length > 0) {
        // Apply filled values to fields
        const newConfidenceMap: Record<string, number> = {};
        setFields(prev => prev.map(field => {
          const filled = result.filled_fields.find(f => f.field_id === field.field_id);
          if (filled) {
            newConfidenceMap[field.field_id] = filled.confidence;
            return { ...field, value: filled.value };
          }
          return field;
        }));
        setConfidenceMap(newConfidenceMap);

        addActivity(
          'info',
          `Auto-filled ${result.filled_fields.length} fields`,
          result.unfilled_fields.length > 0
            ? `${result.unfilled_fields.length} fields could not be filled`
            : undefined,
        );

        result.warnings.forEach(warning => {
          addActivity('info', 'Auto-fill warning', warning);
        });
      } else {
        addActivity(
          'error',
          'Auto-fill found no matches',
          result.error || 'Try adding more data sources',
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Auto-fill failed';
      addActivity('error', 'Auto-fill failed', message);
    } finally {
      setIsAutofilling(false);
      if (conversationId) {
        loadHistory(conversationId);
      }
    }
  }, [activeDocument, conversationId, dataSources.length, fields, customRules, systemPrompt, buildRequestFields, addActivity, loadHistory]);

  // ---- Rule management ----

  const handleAddRule = useCallback(() => {
    const trimmed = newRule.trim();
    if (trimmed) {
      setCustomRules(prev => [...prev, trimmed]);
      setNewRule('');
    }
  }, [newRule]);

  const handleRemoveRule = useCallback((index: number) => {
    setCustomRules(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ---- Render ----

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">Prompt Tuning</h1>
          <span className="text-sm text-gray-500">Vision Autofill</span>
        </div>
        <div className="flex items-center gap-2">
          {activeDocument && conversationId && (
            <button
              onClick={handlePreviewPrompt}
              disabled={isPreviewingPrompt}
              className="px-4 py-2 bg-gray-600 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isPreviewingPrompt ? 'Previewing...' : 'Preview Prompt'}
            </button>
          )}
          {activeDocument && conversationId && dataSources.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex bg-gray-100 rounded-lg p-0.5 text-xs">
                <button
                  onClick={() => setAutofillMode('quick')}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    autofillMode === 'quick'
                      ? 'bg-white text-gray-900 shadow-sm font-medium'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Quick
                </button>
                <button
                  onClick={() => setAutofillMode('detailed')}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    autofillMode === 'detailed'
                      ? 'bg-white text-gray-900 shadow-sm font-medium'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Detailed
                </button>
              </div>
              <button
                onClick={handleRunAutofill}
                disabled={isAutofilling}
                className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors disabled:bg-green-400 disabled:cursor-not-allowed"
              >
                {isAutofilling ? 'Running...' : 'Run Autofill'}
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0">
        {/* Left Panel - Fields */}
        <aside className="w-60 bg-white border-r border-gray-200 flex flex-col shrink-0">
          <div className="p-3 border-b border-gray-200">
            <h2 className="text-sm font-medium text-gray-700">Fields</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <FieldListReadOnly
              fields={fields}
              selectedFieldId={selectedFieldId}
              onFieldSelect={setSelectedFieldId}
              isLoading={isLoadingFields}
              confidenceMap={Object.keys(confidenceMap).length > 0 ? confidenceMap : undefined}
            />
          </div>
        </aside>

        {/* Center - Preview */}
        <main className="flex-1 min-w-0">
          <EditableDocumentPreview
            pageUrls={activeDocument?.pageUrls || []}
            fields={fields}
            selectedFieldId={selectedFieldId}
            onFieldSelect={setSelectedFieldId}
            onFieldEdit={() => {}}
            isLoading={isUploading}
            error={error}
            title={activeDocument?.filename || 'Document Preview'}
            enableFieldHighlights={true}
            showUndoRedo={false}
          />
        </main>

        {/* Right Panel - Tabbed */}
        <aside className="w-96 bg-white border-l border-gray-200 flex flex-col shrink-0">
          {/* Tab Bar */}
          <div className="flex border-b border-gray-200">
            {(['prompt', 'results', 'pipeline', 'history', 'activity'] as RightTab[]).map(tab => {
              const tabLabels: Record<RightTab, string> = {
                prompt: 'Prompt',
                results: 'Results',
                pipeline: 'Pipeline',
                history: `History${promptAttemptsTotal > 0 ? ` (${promptAttemptsTotal})` : ''}`,
                activity: 'Activity',
              };
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`
                    flex-1 px-2 py-2.5 text-xs font-medium transition-colors
                    ${activeTab === tab
                      ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/50'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                    }
                  `}
                >
                  {tabLabels[tab]}
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === 'prompt' && (
              <PromptEditorTab
                systemPrompt={systemPrompt}
                onSystemPromptChange={setSystemPrompt}
                customRules={customRules}
                newRule={newRule}
                onNewRuleChange={setNewRule}
                onAddRule={handleAddRule}
                onRemoveRule={handleRemoveRule}
                previewedPrompt={previewedPrompt}
              />
            )}

            {activeTab === 'results' && (
              <ResultsTab
                result={autofillResult}
                isRunning={isAutofilling}
              />
            )}

            {activeTab === 'pipeline' && (
              <PipelineLogPanel stepLogs={pipelineStepLogs} />
            )}

            {activeTab === 'history' && (
              <HistoryTab
                attempts={promptAttempts}
                total={promptAttemptsTotal}
                isLoading={isLoadingHistory}
                selectedAttempt={selectedAttempt}
                onSelectAttempt={async (attempt) => {
                  if (selectedAttempt?.id === attempt.id) {
                    setSelectedAttempt(null);
                    return;
                  }
                  try {
                    const full = await getPromptAttempt(attempt.id);
                    setSelectedAttempt(full);
                  } catch {
                    setSelectedAttempt(attempt);
                  }
                }}
                onBackToList={() => setSelectedAttempt(null)}
              />
            )}

            {activeTab === 'activity' && (
              <ActivityLog activities={activities} />
            )}
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
        dataSources={dataSources}
        onDataSourceUpload={handleDataSourceUpload}
        onDataSourceTextAdd={handleDataSourceTextAdd}
        onDataSourceRemove={handleDataSourceRemove}
        isDataSourceUploading={isDataSourceUploading}
      />
    </div>
  );
}

// ============================================================================
// Prompt Editor Tab
// ============================================================================

interface PromptEditorTabProps {
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
  customRules: string[];
  newRule: string;
  onNewRuleChange: (value: string) => void;
  onAddRule: () => void;
  onRemoveRule: (index: number) => void;
  previewedPrompt: PromptPreviewResponse | null;
}

function PromptEditorTab({
  systemPrompt,
  onSystemPromptChange,
  customRules,
  newRule,
  onNewRuleChange,
  onAddRule,
  onRemoveRule,
  previewedPrompt,
}: PromptEditorTabProps) {
  return (
    <div className="p-4 space-y-4">
      {/* System Prompt */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          System Prompt
        </label>
        <textarea
          value={systemPrompt}
          onChange={e => onSystemPromptChange(e.target.value)}
          placeholder="Leave empty to use default system prompt. Click 'Preview Prompt' to see the default."
          rows={8}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono resize-y focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* Custom Rules */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Custom Rules
        </label>
        <div className="space-y-1.5 mb-2">
          {customRules.map((rule, i) => (
            <div key={i} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-1.5">
              <span className="flex-1 text-sm text-gray-700 truncate">{rule}</span>
              <button
                onClick={() => onRemoveRule(i)}
                className="text-gray-400 hover:text-red-500 transition-colors shrink-0"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newRule}
            onChange={e => onNewRuleChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') onAddRule(); }}
            placeholder="e.g., Use MM/DD/YYYY for dates"
            className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <button
            onClick={onAddRule}
            disabled={!newRule.trim()}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            Add
          </button>
        </div>
      </div>

      {/* Previewed User Prompt (read-only) */}
      {previewedPrompt && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Extractions Summary
            </label>
            <div className="bg-gray-50 rounded-lg p-3 text-sm">
              <p className="text-gray-600">
                {previewedPrompt.data_source_count} data source(s)
              </p>
              {previewedPrompt.extractions_summary.map((s, i) => (
                <div key={i} className="flex justify-between mt-1 text-xs text-gray-500">
                  <span>{s.source_name} ({s.source_type})</span>
                  <span>{s.field_count} fields</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              User Prompt (read-only)
            </label>
            <pre className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs font-mono overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap text-gray-700">
              {previewedPrompt.user_prompt}
            </pre>
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Results Tab
// ============================================================================

interface ResultsTabProps {
  result: VisionAutofillResponse | null;
  isRunning: boolean;
}

function ResultsTab({ result, isRunning }: ResultsTabProps) {
  if (isRunning) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
        <span className="ml-3 text-sm text-gray-600">Running autofill...</span>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="p-4 text-center">
        <p className="text-sm text-gray-500">No results yet</p>
        <p className="text-xs text-gray-400 mt-1">Click "Run Autofill" to see results</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
        <span className={`inline-block w-2.5 h-2.5 rounded-full ${result.success ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-sm font-medium text-gray-700">
          {result.success ? 'Completed' : 'Failed'}
        </span>
        <span className="text-xs text-gray-500 ml-auto">{result.processing_time_ms}ms</span>
      </div>

      {/* Filled Fields */}
      {result.filled_fields.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            Filled Fields ({result.filled_fields.length})
          </h3>
          <div className="space-y-1.5">
            {result.filled_fields.map(f => (
              <div key={f.field_id} className="flex items-start gap-2 px-3 py-2 bg-green-50 rounded-lg">
                <ConfidenceDot confidence={f.confidence} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-700 truncate">{f.field_id}</div>
                  <div className="text-xs text-gray-600 truncate">{f.value}</div>
                  {f.source && (
                    <div className="text-xs text-gray-400 mt-0.5">from: {f.source}</div>
                  )}
                </div>
                <span className="text-xs text-gray-500 shrink-0">
                  {Math.round(f.confidence * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unfilled Fields */}
      {result.unfilled_fields.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            Unfilled ({result.unfilled_fields.length})
          </h3>
          <div className="space-y-1">
            {result.unfilled_fields.map(id => (
              <div key={id} className="px-3 py-1.5 bg-gray-50 rounded-lg text-sm text-gray-500">
                {id}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-amber-700 mb-2">Warnings</h3>
          <div className="space-y-1">
            {result.warnings.map((w, i) => (
              <div key={i} className="px-3 py-1.5 bg-amber-50 rounded-lg text-xs text-amber-700">
                {w}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {result.error && (
        <div className="px-3 py-2 bg-red-50 rounded-lg text-sm text-red-700">
          {result.error}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Confidence Dot
// ============================================================================

function ConfidenceDot({ confidence }: { confidence: number }) {
  let color = 'bg-orange-400'; // < 0.7
  if (confidence >= 0.9) {
    color = 'bg-green-500';
  } else if (confidence >= 0.7) {
    color = 'bg-yellow-400';
  }
  return <span className={`inline-block w-2 h-2 rounded-full mt-1.5 shrink-0 ${color}`} />;
}

// ============================================================================
// History Tab
// ============================================================================

interface HistoryTabProps {
  attempts: PromptAttempt[];
  total: number;
  isLoading: boolean;
  selectedAttempt: PromptAttempt | null;
  onSelectAttempt: (attempt: PromptAttempt) => void;
  onBackToList: () => void;
}

function HistoryTab({
  attempts,
  total,
  isLoading,
  selectedAttempt,
  onSelectAttempt,
  onBackToList,
}: HistoryTabProps) {
  if (selectedAttempt) {
    return (
      <AttemptDetailView
        attempt={selectedAttempt}
        onBack={onBackToList}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <span className="ml-3 text-sm text-gray-600">Loading history...</span>
      </div>
    );
  }

  if (attempts.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-sm text-gray-500">No attempts yet</p>
        <p className="text-xs text-gray-400 mt-1">Run autofill to start recording history</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-2">
      <div className="text-xs text-gray-500 mb-3">{total} attempt(s)</div>
      {attempts.map(attempt => {
        const ts = new Date(attempt.created_at);
        const timeStr = ts.toLocaleString();
        const processingMs = (attempt.metadata as Record<string, unknown>)?.processing_time_ms;
        const parsedResult = attempt.parsed_result as Record<string, unknown> | null;
        const filledCount = Array.isArray(parsedResult?.filled_fields)
          ? (parsedResult.filled_fields as unknown[]).length
          : 0;

        return (
          <button
            key={attempt.id}
            onClick={() => onSelectAttempt(attempt)}
            className="w-full text-left px-3 py-2.5 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/30 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${attempt.success ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm font-medium text-gray-700">
                {attempt.success ? 'Success' : 'Failed'}
              </span>
              {filledCount > 0 && (
                <span className="text-xs text-gray-500">{filledCount} filled</span>
              )}
              {typeof processingMs === 'number' && (
                <span className="text-xs text-gray-400 ml-auto">{processingMs}ms</span>
              )}
            </div>
            <div className="text-xs text-gray-400 mt-1">{timeStr}</div>
            {attempt.error && (
              <div className="text-xs text-red-500 mt-1 truncate">{attempt.error}</div>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ============================================================================
// Attempt Detail View
// ============================================================================

interface AttemptDetailViewProps {
  attempt: PromptAttempt;
  onBack: () => void;
}

function AttemptDetailView({ attempt, onBack }: AttemptDetailViewProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const toggleSection = (section: string) => {
    setExpandedSection(prev => (prev === section ? null : section));
  };

  const ts = new Date(attempt.created_at);
  const processingMs = (attempt.metadata as Record<string, unknown>)?.processing_time_ms;

  return (
    <div className="p-4 space-y-3">
      {/* Back button + summary */}
      <div className="flex items-center gap-2">
        <button
          onClick={onBack}
          className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
        >
          &larr; Back
        </button>
      </div>

      <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
        <span className={`inline-block w-2.5 h-2.5 rounded-full ${attempt.success ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-sm font-medium text-gray-700">
          {attempt.success ? 'Success' : 'Failed'}
        </span>
        {typeof processingMs === 'number' && (
          <span className="text-xs text-gray-500 ml-auto">{processingMs}ms</span>
        )}
      </div>
      <div className="text-xs text-gray-500">{ts.toLocaleString()}</div>

      {attempt.error && (
        <div className="px-3 py-2 bg-red-50 rounded-lg text-sm text-red-700">
          {attempt.error}
        </div>
      )}

      {/* Collapsible sections */}
      <CollapsibleSection
        title="System Prompt"
        isOpen={expandedSection === 'system'}
        onToggle={() => toggleSection('system')}
      >
        <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-64 overflow-y-auto">
          {attempt.system_prompt}
        </pre>
      </CollapsibleSection>

      <CollapsibleSection
        title="User Prompt"
        isOpen={expandedSection === 'user'}
        onToggle={() => toggleSection('user')}
      >
        <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-64 overflow-y-auto">
          {attempt.user_prompt}
        </pre>
      </CollapsibleSection>

      {attempt.custom_rules.length > 0 && (
        <CollapsibleSection
          title={`Custom Rules (${attempt.custom_rules.length})`}
          isOpen={expandedSection === 'rules'}
          onToggle={() => toggleSection('rules')}
        >
          <ul className="space-y-1">
            {attempt.custom_rules.map((rule, i) => (
              <li key={i} className="text-xs text-gray-700 bg-gray-50 rounded px-2 py-1">{rule}</li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      <CollapsibleSection
        title="Raw Response"
        isOpen={expandedSection === 'raw'}
        onToggle={() => toggleSection('raw')}
      >
        <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-80 overflow-y-auto">
          {attempt.raw_response || '(empty)'}
        </pre>
      </CollapsibleSection>

      {attempt.parsed_result && (
        <CollapsibleSection
          title="Parsed Result"
          isOpen={expandedSection === 'parsed'}
          onToggle={() => toggleSection('parsed')}
        >
          <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-80 overflow-y-auto">
            {JSON.stringify(attempt.parsed_result, null, 2)}
          </pre>
        </CollapsibleSection>
      )}
    </div>
  );
}

// ============================================================================
// Collapsible Section
// ============================================================================

interface CollapsibleSectionProps {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function CollapsibleSection({ title, isOpen, onToggle, children }: CollapsibleSectionProps) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
      >
        <span>{title}</span>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="px-3 py-2 border-t border-gray-200 bg-gray-50">
          {children}
        </div>
      )}
    </div>
  );
}
