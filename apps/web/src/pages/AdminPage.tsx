/**
 * Admin page - unified dashboard for job creation and viewing.
 *
 * When no job is selected: shows job creation UI (load existing or create new)
 * When a job is selected: shows full job detail view
 */

import { useState, useCallback, useEffect, type CSSProperties } from 'react';
import type { DocumentResponse, JobMode, Field, RunMode, FieldAnswer, AcroFormFieldInfo, BBox } from '../types/api';
import {
  isApiHealthy,
  getJob,
  createJob,
  downloadOutputPdf,
  exportJobJson,
  updateFieldValue,
} from '../api/client';
import { useJob } from '../hooks/useJob';
import { useDebouncedSave } from '../hooks/useDebounce';
import { DocumentUploader } from '../components/documents/DocumentUploader';
import { JobHeader } from '../components/jobs/JobHeader';
import { FieldListPanel } from '../components/fields/FieldListPanel';
import { PageViewer } from '../components/documents/PageViewer';
import type { BBoxUpdate } from '../components/documents/FieldOverlay';
import { ActivityTimeline } from '../components/jobs/ActivityTimeline';
import { CostDisplay } from '../components/jobs/CostDisplay';
import { IssuesPanel, IssuesSummary } from '../components/jobs/IssuesPanel';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { LoadingOverlay, ErrorState } from '../components/ui/LoadingState';
import { useToast } from '../components/ui/Toast';
import { useRef, useMemo } from 'react';

export interface AdminPageProps {
  jobId: string | null;
  onJobSelect: (jobId: string) => void;
  onClearJob: () => void;
}

export function AdminPage({ jobId, onJobSelect, onClearJob }: AdminPageProps) {
  // If we have a jobId, render the job detail view
  if (jobId) {
    return (
      <JobDetailView
        jobId={jobId}
        onBack={onClearJob}
      />
    );
  }

  // Otherwise, render the job creation view
  return <JobCreateView onJobSelect={onJobSelect} />;
}

// ============================================================================
// Job Creation View
// ============================================================================

interface JobCreateViewProps {
  onJobSelect: (jobId: string) => void;
}

function JobCreateView({ onJobSelect }: JobCreateViewProps) {
  const toast = useToast();

  // API health check
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  // Load existing job state
  const [loadJobId, setLoadJobId] = useState('');
  const [loadLoading, setLoadLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Create new job state
  const [mode, setMode] = useState<JobMode>('transfer');
  const [sourceDocument, setSourceDocument] = useState<DocumentResponse | null>(null);
  const [targetDocument, setTargetDocument] = useState<DocumentResponse | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    isApiHealthy().then(setApiHealthy);
  }, []);

  const handleLoadJob = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!loadJobId.trim()) return;

      setLoadLoading(true);
      setLoadError(null);

      try {
        await getJob(loadJobId.trim());
        onJobSelect(loadJobId.trim());
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : 'Failed to load job');
      } finally {
        setLoadLoading(false);
      }
    },
    [loadJobId, onJobSelect]
  );

  const handleSourceUpload = useCallback((doc: DocumentResponse) => {
    setSourceDocument(doc);
    setCreateError(null);
    toast.success('Source document uploaded');
  }, [toast]);

  const handleTargetUpload = useCallback((doc: DocumentResponse) => {
    setTargetDocument(doc);
    setCreateError(null);
    toast.success('Target document uploaded');
  }, [toast]);

  const handleCreateJob = useCallback(async () => {
    if (!targetDocument) {
      setCreateError('Target document is required');
      return;
    }

    if (mode === 'transfer' && !sourceDocument) {
      setCreateError('Source document is required for transfer mode');
      return;
    }

    setCreating(true);
    setCreateError(null);

    try {
      const result = await createJob({
        mode,
        target_document_id: targetDocument.document_id,
        ...(mode === 'transfer' && sourceDocument
          ? { source_document_id: sourceDocument.document_id }
          : {}),
      });

      toast.success('Job created successfully');
      onJobSelect(result.job_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create job';
      setCreateError(message);
      toast.error(message);
    } finally {
      setCreating(false);
    }
  }, [mode, sourceDocument, targetDocument, onJobSelect, toast]);

  const canCreate = targetDocument && (mode === 'scratch' || sourceDocument);

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#f3f4f6',
  };

  const headerStyles: CSSProperties = {
    padding: '16px 24px',
    backgroundColor: 'white',
    borderBottom: '1px solid #e5e7eb',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  };

  const titleStyles: CSSProperties = {
    fontSize: '20px',
    fontWeight: 700,
    color: '#111827',
    margin: 0,
  };

  const mainStyles: CSSProperties = {
    flex: 1,
    overflow: 'auto',
    padding: '24px',
  };

  const contentStyles: CSSProperties = {
    maxWidth: '1000px',
    margin: '0 auto',
  };

  const gridStyles: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '24px',
    marginBottom: '24px',
  };

  const inputStyles: CSSProperties = {
    width: '100%',
    padding: '10px 14px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    outline: 'none',
    marginBottom: '12px',
  };

  const sectionHeaderStyles: CSSProperties = {
    fontSize: '15px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 16px 0',
  };

  const modeContainerStyles: CSSProperties = {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px',
  };

  const modeOptionStyles = (selected: boolean): CSSProperties => ({
    flex: 1,
    padding: '14px',
    borderRadius: '10px',
    border: `2px solid ${selected ? '#3b82f6' : '#e5e7eb'}`,
    backgroundColor: selected ? '#eff6ff' : 'white',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  });

  const modeTitleStyles: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#111827',
    marginBottom: '4px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  const modeDescStyles: CSSProperties = {
    fontSize: '12px',
    color: '#6b7280',
    lineHeight: 1.4,
  };

  const uploadsContainerStyles: CSSProperties = {
    display: 'flex',
    gap: '16px',
    marginBottom: '16px',
  };

  return (
    <div style={containerStyles}>
      {/* Header */}
      <div style={headerStyles}>
        <h1 style={titleStyles}>Daru PDF Admin</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {apiHealthy === null && <Badge variant="default">Checking API...</Badge>}
          {apiHealthy === true && <Badge variant="success">API Connected</Badge>}
          {apiHealthy === false && <Badge variant="danger">API Offline</Badge>}
        </div>
      </div>

      {/* Main Content */}
      <div style={mainStyles}>
        <div style={contentStyles}>
          {apiHealthy === false && (
            <div
              style={{
                padding: '16px',
                backgroundColor: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                marginBottom: '24px',
              }}
            >
              <p style={{ margin: 0, fontSize: '14px', color: '#991b1b' }}>
                Cannot connect to the API server. Please ensure it is running.
              </p>
            </div>
          )}

          <div style={gridStyles}>
            {/* Load Existing Job */}
            <Card padding="lg">
              <h2 style={sectionHeaderStyles}>Load Existing Job</h2>
              <form onSubmit={handleLoadJob}>
                <input
                  type="text"
                  value={loadJobId}
                  onChange={(e) => setLoadJobId(e.target.value)}
                  placeholder="Enter job ID"
                  style={inputStyles}
                  disabled={loadLoading || apiHealthy === false}
                />
                <Button
                  type="submit"
                  variant="primary"
                  fullWidth
                  loading={loadLoading}
                  disabled={!loadJobId.trim() || apiHealthy === false}
                >
                  Load Job
                </Button>
              </form>
              {loadError && (
                <ErrorState
                  message={loadError}
                  onRetry={() => setLoadError(null)}
                  style={{ marginTop: '12px' }}
                />
              )}
            </Card>

            {/* Processing Mode */}
            <Card padding="lg">
              <h2 style={sectionHeaderStyles}>Processing Mode</h2>
              <div style={modeContainerStyles}>
                <div
                  style={modeOptionStyles(mode === 'transfer')}
                  onClick={() => setMode('transfer')}
                  role="button"
                  tabIndex={0}
                >
                  <div style={modeTitleStyles}>
                    <input
                      type="radio"
                      name="mode"
                      checked={mode === 'transfer'}
                      onChange={() => setMode('transfer')}
                    />
                    Transfer
                  </div>
                  <p style={modeDescStyles}>Copy from filled to blank form</p>
                </div>
                <div
                  style={modeOptionStyles(mode === 'scratch')}
                  onClick={() => setMode('scratch')}
                  role="button"
                  tabIndex={0}
                >
                  <div style={modeTitleStyles}>
                    <input
                      type="radio"
                      name="mode"
                      checked={mode === 'scratch'}
                      onChange={() => setMode('scratch')}
                    />
                    Scratch
                  </div>
                  <p style={modeDescStyles}>Fill blank form with answers</p>
                </div>
              </div>
            </Card>
          </div>

          {/* Upload Documents */}
          <Card padding="lg">
            <h2 style={sectionHeaderStyles}>Upload Documents</h2>
            <div style={uploadsContainerStyles}>
              {mode === 'transfer' && (
                <div style={{ flex: 1 }}>
                  <DocumentUploader
                    documentType="source"
                    onUploadComplete={handleSourceUpload}
                    disabled={creating || apiHealthy === false}
                    label="Source Document (filled)"
                    required
                  />
                </div>
              )}
              <div style={{ flex: 1 }}>
                <DocumentUploader
                  documentType="target"
                  onUploadComplete={handleTargetUpload}
                  disabled={creating || apiHealthy === false}
                  label="Target Document (blank)"
                  required
                />
              </div>
            </div>

            {createError && (
              <ErrorState
                message={createError}
                onRetry={() => setCreateError(null)}
                style={{ marginBottom: '16px' }}
              />
            )}

            <Button
              variant="primary"
              fullWidth
              onClick={handleCreateJob}
              disabled={!canCreate || apiHealthy === false}
              loading={creating}
            >
              Create Job
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Job Detail View
// ============================================================================

interface JobDetailViewProps {
  jobId: string;
  onBack: () => void;
}

function JobDetailView({ jobId, onBack }: JobDetailViewProps) {
  const toast = useToast();
  const { job, loading, error, isRunning, run, submitFieldAnswers, refresh } = useJob(jobId);

  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [pendingEdits, setPendingEdits] = useState<Map<string, string>>(new Map());
  const [highlightedFieldName, setHighlightedFieldName] = useState<string | null>(null);
  const [highlightedAnchorBbox, setHighlightedAnchorBbox] = useState<BBox | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [rightTab, setRightTab] = useState<'activity' | 'issues' | 'stats'>('activity');

  const autoSave = useDebouncedSave<string, string>(
    useCallback(
      async (fieldId: string, value: string) => {
        await updateFieldValue(jobId, fieldId, value);
        setPendingEdits((prev) => {
          const next = new Map(prev);
          next.delete(fieldId);
          return next;
        });
        refresh();
      },
      [jobId, refresh]
    ),
    500
  );

  const handleRun = useCallback(
    async (mode: RunMode) => {
      try {
        await run(mode);
        toast.success(`Job ${mode === 'step' ? 'stepped' : 'started'}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to run job');
      }
    },
    [run, toast]
  );

  const handleFieldEdit = useCallback((fieldId: string, value: string) => {
    setPendingEdits((prev) => {
      const next = new Map(prev);
      next.set(fieldId, value);
      return next;
    });
  }, []);

  const handleSubmitAnswers = useCallback(async () => {
    if (pendingEdits.size === 0) return;

    const answers: FieldAnswer[] = Array.from(pendingEdits.entries()).map(
      ([field_id, value]) => ({ field_id, value })
    );

    try {
      await submitFieldAnswers(answers);
      setPendingEdits(new Map());
      toast.success('Answers submitted successfully');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to submit answers');
    }
  }, [pendingEdits, submitFieldAnswers, toast]);

  const handleDownload = useCallback(async () => {
    try {
      const blob = await downloadOutputPdf(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `output_${jobId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('PDF downloaded');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to download PDF');
    }
  }, [jobId, toast]);

  const handleExport = useCallback(async () => {
    try {
      const data = await exportJobJson(jobId);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `job_${jobId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('JSON exported');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export JSON');
    }
  }, [jobId, toast]);

  const targetFields = useMemo(() => {
    if (!job) return [];
    return job.fields.filter((f) => f.document_id === job.target_document.id);
  }, [job]);

  const prevErrorKeysRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const currentErrors = autoSave.errorKeys;
    const prevErrors = prevErrorKeysRef.current;

    for (const [fieldId, errorMessage] of currentErrors) {
      if (!prevErrors.has(fieldId)) {
        const field = targetFields.find((f) => f.id === fieldId);
        const fieldName = field?.name || fieldId;
        toast.error(`Failed to save "${fieldName}": ${errorMessage}`);
      }
    }

    prevErrorKeysRef.current = new Set(currentErrors.keys());
  }, [autoSave.errorKeys, targetFields, toast]);

  const sourceFields = useMemo(() => {
    if (!job || !job.source_document) return [];
    return job.fields.filter((f) => f.document_id === job.source_document?.id);
  }, [job]);

  const fieldValues = useMemo(() => {
    const values = new Map<string, string>();
    for (const field of targetFields) {
      if (field.value) {
        values.set(field.name, field.value);
      }
    }
    for (const [fieldId, value] of pendingEdits) {
      const field = targetFields.find((f) => f.id === fieldId);
      if (field) {
        values.set(field.name, value);
      }
    }
    return values;
  }, [targetFields, pendingEdits]);

  const fieldSaveStatus = useMemo(() => {
    const status = new Map<string, 'pending' | 'saving' | 'success' | 'error'>();
    for (const field of targetFields) {
      if (autoSave.pendingKeys.has(field.id)) {
        status.set(field.name, 'pending');
      } else if (autoSave.savingKeys.has(field.id)) {
        status.set(field.name, 'saving');
      } else if (autoSave.successKeys.has(field.id)) {
        status.set(field.name, 'success');
      } else if (autoSave.errorKeys.has(field.id)) {
        status.set(field.name, 'error');
      }
    }
    return status;
  }, [targetFields, autoSave.pendingKeys, autoSave.savingKeys, autoSave.successKeys, autoSave.errorKeys]);

  const fieldSaveErrors = useMemo(() => {
    const errors = new Map<string, string>();
    for (const field of targetFields) {
      const error = autoSave.errorKeys.get(field.id);
      if (error) {
        errors.set(field.name, error);
      }
    }
    return errors;
  }, [targetFields, autoSave.errorKeys]);

  const handleFieldSelect = useCallback((field: Field) => {
    setSelectedFieldId(field.id);
    setHighlightedFieldName(field.name);
    if (field.page !== currentPage) {
      setCurrentPage(field.page);
    }
    setHighlightedAnchorBbox(null);
  }, [currentPage]);

  const handleBboxClick = useCallback((acroField: AcroFormFieldInfo) => {
    const matchingField = targetFields.find((f) => f.name === acroField.field_name);
    if (matchingField) {
      setSelectedFieldId(matchingField.id);
      setHighlightedFieldName(acroField.field_name);
    }
  }, [targetFields]);

  const handleOverlayValueChange = useCallback((update: BBoxUpdate) => {
    if (update.value === undefined) return;
    const matchingField = targetFields.find((f) => f.name === update.fieldName);
    if (matchingField) {
      setPendingEdits((prev) => {
        const next = new Map(prev);
        next.set(matchingField.id, update.value!);
        return next;
      });
      autoSave.save(matchingField.id, update.value);
    }
  }, [targetFields, autoSave]);

  if (loading && !job) {
    return <LoadingOverlay message="Loading job..." />;
  }

  if (error && !job) {
    return (
      <div style={{ padding: '48px' }}>
        <ErrorState title="Failed to load job" message={error} onRetry={refresh} />
        <div style={{ marginTop: '24px', textAlign: 'center' }}>
          <Button variant="secondary" onClick={onBack}>
            Go Back
          </Button>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <ErrorState title="Job not found" message="The requested job could not be found." />
    );
  }

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#f3f4f6',
  };

  const headerContainerStyles: CSSProperties = {
    flexShrink: 0,
  };

  const mainStyles: CSSProperties = {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  };

  const leftPanelStyles: CSSProperties = {
    width: '320px',
    flexShrink: 0,
    backgroundColor: 'white',
    borderRight: '1px solid #e5e7eb',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const centerPanelStyles: CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    backgroundColor: '#f9fafb',
  };

  const rightPanelStyles: CSSProperties = {
    width: '300px',
    flexShrink: 0,
    backgroundColor: 'white',
    borderLeft: '1px solid #e5e7eb',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const panelHeaderStyles: CSSProperties = {
    padding: '12px 16px',
    borderBottom: '1px solid #e5e7eb',
    backgroundColor: 'white',
    flexShrink: 0,
  };

  const panelTitleStyles: CSSProperties = {
    margin: 0,
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
  };

  const panelContentStyles: CSSProperties = {
    flex: 1,
    overflow: 'auto',
    padding: '16px',
  };

  const rightTabsStyles: CSSProperties = {
    display: 'flex',
    borderBottom: '1px solid #e5e7eb',
    backgroundColor: 'white',
    padding: '0 8px',
    flexShrink: 0,
  };

  const rightTabStyles = (active: boolean): CSSProperties => ({
    padding: '10px 12px',
    fontSize: '12px',
    fontWeight: 500,
    color: active ? '#3b82f6' : '#6b7280',
    borderBottom: active ? '2px solid #3b82f6' : '2px solid transparent',
    cursor: 'pointer',
    background: 'none',
    border: 'none',
  });

  return (
    <div style={containerStyles}>
      <div style={headerContainerStyles}>
        <div
          style={{
            padding: '12px 24px',
            borderBottom: '1px solid #e5e7eb',
            backgroundColor: 'white',
          }}
        >
          <Button variant="ghost" size="sm" onClick={onBack}>
            &larr; Back to Admin
          </Button>
        </div>
        <JobHeader
          job={job}
          onRun={handleRun}
          onDownload={handleDownload}
          onExport={handleExport}
          isRunning={isRunning}
          pendingAnswers={pendingEdits.size}
          onSubmitAnswers={handleSubmitAnswers}
        />
      </div>

      <div style={mainStyles}>
        <div style={leftPanelStyles}>
          <div style={panelHeaderStyles}>
            <h3 style={panelTitleStyles}>Fields ({targetFields.length})</h3>
          </div>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <FieldListPanel
              fields={targetFields}
              issues={job.issues}
              onFieldEdit={handleFieldEdit}
              onFieldSelect={handleFieldSelect}
              selectedFieldId={selectedFieldId}
              title=""
              pendingEdits={pendingEdits}
            />
          </div>
        </div>

        <div style={centerPanelStyles}>
          <div style={{ ...panelHeaderStyles, backgroundColor: '#f9fafb' }}>
            <h3 style={panelTitleStyles}>
              {job.target_document.meta.filename}
              {job.source_document && (
                <span style={{ fontWeight: 400, color: '#6b7280', marginLeft: '8px' }}>
                  | Source: {job.source_document.meta.filename}
                </span>
              )}
            </h3>
          </div>
          <div style={{ flex: 1, padding: '16px', overflow: 'auto' }}>
            <div style={{ display: 'flex', gap: '16px', height: '100%' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <PageViewer
                  documentId={job.target_document.id}
                  pageCount={job.target_document.meta.page_count}
                  title="Target"
                  height="100%"
                  showFieldOverlay={true}
                  initialPage={currentPage}
                  onPageChange={setCurrentPage}
                  onFieldClick={handleBboxClick}
                  highlightedFieldName={highlightedFieldName}
                  highlightedAnchorBbox={highlightedAnchorBbox}
                  editable={true}
                  onFieldValueChange={handleOverlayValueChange}
                  fieldValues={fieldValues}
                  fieldSaveStatus={fieldSaveStatus}
                  fieldSaveErrors={fieldSaveErrors}
                />
              </div>
              {job.source_document && (
                <div style={{ flex: 1, minWidth: 0 }}>
                  <PageViewer
                    documentId={job.source_document.id}
                    pageCount={job.source_document.meta.page_count}
                    title="Source"
                    height="100%"
                    showFieldOverlay={true}
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        <div style={rightPanelStyles}>
          <div style={rightTabsStyles}>
            <button
              style={rightTabStyles(rightTab === 'activity')}
              onClick={() => setRightTab('activity')}
            >
              Activity
            </button>
            <button
              style={rightTabStyles(rightTab === 'issues')}
              onClick={() => setRightTab('issues')}
            >
              Issues ({job.issues.length})
            </button>
            <button
              style={rightTabStyles(rightTab === 'stats')}
              onClick={() => setRightTab('stats')}
            >
              Stats
            </button>
          </div>
          <div style={panelContentStyles}>
            {rightTab === 'activity' && (
              <ActivityTimeline activities={job.activities} maxItems={20} />
            )}
            {rightTab === 'issues' && <IssuesPanel issues={job.issues} />}
            {rightTab === 'stats' && (
              <>
                <div style={{ marginBottom: '20px' }}>
                  <IssuesSummary issues={job.issues} />
                </div>
                {job.cost && (
                  <div style={{ marginBottom: '20px' }}>
                    <CostDisplay cost={job.cost} showDetails />
                  </div>
                )}
                {sourceFields.length > 0 && (
                  <div>
                    <h4
                      style={{
                        margin: '0 0 12px 0',
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#6b7280',
                      }}
                    >
                      Source Fields ({sourceFields.length})
                    </h4>
                    <div style={{ fontSize: '13px' }}>
                      {sourceFields.map((field) => (
                        <div
                          key={field.id}
                          style={{
                            padding: '8px 0',
                            borderBottom: '1px solid #f3f4f6',
                            display: 'flex',
                            justifyContent: 'space-between',
                          }}
                        >
                          <span style={{ color: '#6b7280' }}>{field.name}</span>
                          <span style={{ color: '#374151', fontWeight: 500 }}>
                            {field.value || '-'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
