import { useState, useEffect } from "react";
import type { JobContext, FieldAnswer } from "../api/jobClient";
import {
  getJob,
  runJob,
  submitAnswers,
  downloadOutput,
} from "../api/jobClient";
import { FieldList } from "./FieldList";
import { RawJsonViewer } from "./RawJsonViewer";
import { DocumentPreview } from "./DocumentPreview";
import "./JobViewer.css";

interface JobViewerProps {
  jobId: string;
}

export function JobViewer({ jobId }: JobViewerProps) {
  const [job, setJob] = useState<JobContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [_selectedField, setSelectedField] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Map<string, string>>(new Map());
  const [running, setRunning] = useState(false);

  useEffect(() => {
    loadJob();
    // Poll for updates every 2 seconds if job is running
    const interval = setInterval(() => {
      if (job && (job.status === "running" || job.status === "awaiting_input")) {
        loadJob();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  const loadJob = async () => {
    try {
      setLoading(true);
      const jobData = await getJob(jobId);
      setJob(jobData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
    } finally {
      setLoading(false);
    }
  };

  const handleRun = async (mode: "step" | "until_blocked" | "until_done") => {
    if (!job) return;
    try {
      setRunning(true);
      const result = await runJob(jobId, { run_mode: mode });
      setJob(result.job_context);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run job");
    } finally {
      setRunning(false);
    }
  };

  const handleFieldEdit = (fieldId: string, value: string) => {
    setAnswers(new Map(answers.set(fieldId, value)));
  };

  const handleSubmitAnswers = async () => {
    if (!job || answers.size === 0) return;
    try {
      setRunning(true);
      const fieldAnswers: FieldAnswer[] = Array.from(answers.entries()).map(
        ([field_id, value]) => ({ field_id, value })
      );
      const updatedJob = await submitAnswers(jobId, fieldAnswers);
      setJob(updatedJob);
      setAnswers(new Map());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit answers");
    } finally {
      setRunning(false);
    }
  };

  const handleDownload = async () => {
    if (!job) return;
    try {
      const blob = await downloadOutput(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `output_${jobId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download output");
    }
  };

  if (loading && !job) {
    return <div className="job-viewer-loading">Loading job...</div>;
  }

  if (error && !job) {
    return <div className="job-viewer-error">Error: {error}</div>;
  }

  if (!job) {
    return <div className="job-viewer-error">Job not found</div>;
  }

  const targetFields = job.fields.filter(
    (f) => f.document_id === job.target_document.id
  );
  const sourceFields = job.fields.filter(
    (f) => f.document_id === job.source_document?.id
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case "done":
        return "#22c55e";
      case "running":
        return "#3b82f6";
      case "awaiting_input":
        return "#eab308";
      case "blocked":
        return "#ef4444";
      default:
        return "#6b7280";
    }
  };

  return (
    <div className="job-viewer">
      <div className="job-viewer-header">
        <div className="job-info">
          <h1>Job: {jobId.slice(0, 8)}...</h1>
          <div className="job-meta">
            <span
              className="job-status"
              style={{ color: getStatusColor(job.status) }}
            >
              {job.status.toUpperCase()}
            </span>
            <span className="job-progress">
              Progress: {(job.progress * 100).toFixed(0)}%
            </span>
            <span className="job-stage">Stage: {job.current_stage}</span>
          </div>
        </div>
        <div className="job-actions">
          {job.status === "awaiting_input" && (
            <>
              {answers.size > 0 && (
                <button
                  onClick={handleSubmitAnswers}
                  className="btn-primary"
                  disabled={running}
                >
                  Submit Answers ({answers.size})
                </button>
              )}
              <button
                onClick={() => handleRun("until_blocked")}
                className="btn-secondary"
                disabled={running}
              >
                Continue
              </button>
            </>
          )}
          {job.status === "running" && (
            <button className="btn-secondary" disabled>
              Running...
            </button>
          )}
          {job.status === "done" && (
            <button onClick={handleDownload} className="btn-primary">
              Download Output PDF
            </button>
          )}
          {job.next_actions.includes("run") && job.status !== "running" && (
            <button
              onClick={() => handleRun("until_blocked")}
              className="btn-secondary"
              disabled={running}
            >
              Run
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="job-viewer-error-banner">{error}</div>
      )}

      <div className="job-viewer-layout">
        {/* TOP SECTION: Documents and Fields */}
        <div className="job-viewer-top-section">
          {/* Document Previews - prominently displayed at TOP */}
          <div className="job-viewer-documents">
            <DocumentPreview
              documentId={job.target_document.id}
              pageCount={job.target_document.meta.page_count}
              title={`Target: ${job.target_document.meta.filename}`}
            />
            {job.source_document && (
              <DocumentPreview
                documentId={job.source_document.id}
                pageCount={job.source_document.meta.page_count}
                title={`Source: ${job.source_document.meta.filename}`}
              />
            )}
          </div>

          <div className="job-viewer-content">
            <div className="job-viewer-main">
              <FieldList
                fields={targetFields}
                issues={job.issues}
                onFieldSelect={(field) => setSelectedField(field.id)}
                onFieldEdit={handleFieldEdit}
              />
            </div>

            <div className="job-viewer-sidebar">
              <div className="sidebar-section">
                <h3>Source Fields</h3>
                <div className="source-fields-list">
                  {sourceFields.map((field) => (
                    <div key={field.id} className="source-field-item">
                      <div className="source-field-name">{field.name}</div>
                      <div className="source-field-value">{field.value || "-"}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="sidebar-section">
                <h3>Issues Summary</h3>
                <div className="issues-summary">
                  <div className="issue-count">
                    Total: {job.issues.length} issues
                  </div>
                  <div className="issue-breakdown">
                    {job.issues.filter((i) => i.severity === "error").length} errors
                  </div>
                  <div className="issue-breakdown">
                    {job.issues.filter((i) => i.severity === "warning").length}{" "}
                    warnings
                  </div>
                </div>
              </div>

              <div className="sidebar-section">
                <h3>Confidence Summary</h3>
                <div className="confidence-summary">
                  {targetFields.map((field) => (
                    <div key={field.id} className="confidence-item">
                      <span>{field.name}</span>
                      <span
                        style={{
                          color:
                            field.confidence === null
                              ? "#999"
                              : field.confidence >= 0.8
                              ? "#22c55e"
                              : field.confidence >= 0.5
                              ? "#eab308"
                              : "#ef4444",
                        }}
                      >
                        {field.confidence
                          ? `${(field.confidence * 100).toFixed(0)}%`
                          : "N/A"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* BOTTOM SECTION: Raw JSON Response */}
        <div className="job-viewer-bottom-section">
          <RawJsonViewer data={job} title="Raw JSON Response" />
        </div>
      </div>
    </div>
  );
}
