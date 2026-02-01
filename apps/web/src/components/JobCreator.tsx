import { useState } from "react";
import { DocumentUpload } from "./DocumentUpload";
import type { DocumentUploadResponse } from "../api/jobClient";
import { createJob, type JobCreateRequest } from "../api/jobClient";
import "./JobCreator.css";

interface JobCreatorProps {
  onJobCreated: (jobId: string) => void;
}

export function JobCreator({ onJobCreated }: JobCreatorProps) {
  const [sourceDocument, setSourceDocument] =
    useState<DocumentUploadResponse | null>(null);
  const [targetDocument, setTargetDocument] =
    useState<DocumentUploadResponse | null>(null);
  const [mode, setMode] = useState<"transfer" | "scratch">("transfer");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSourceUpload = (document: DocumentUploadResponse) => {
    setSourceDocument(document);
    setError(null);
  };

  const handleTargetUpload = (document: DocumentUploadResponse) => {
    setTargetDocument(document);
    setError(null);
  };

  const handleCreateJob = async () => {
    if (!targetDocument) {
      setError("Target document is required");
      return;
    }

    if (mode === "transfer" && !sourceDocument) {
      setError("Source document is required for transfer mode");
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const request: JobCreateRequest = {
        mode,
        target_document_id: targetDocument.document_id,
        ...(mode === "transfer" && sourceDocument
          ? { source_document_id: sourceDocument.document_id }
          : {}),
      };

      const result = await createJob(request);
      onJobCreated(result.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setCreating(false);
    }
  };

  const canCreateJob =
    targetDocument && (mode === "scratch" || sourceDocument);

  return (
    <div className="job-creator">
      <div className="job-creator-header">
        <h2>Create New Job</h2>
        <p>Upload documents to start processing</p>
      </div>

      <div className="job-creator-mode">
        <label className="mode-option">
          <input
            type="radio"
            name="mode"
            value="transfer"
            checked={mode === "transfer"}
            onChange={(e) => {
              setMode(e.target.value as "transfer");
              setError(null);
            }}
          />
          <div className="mode-content">
            <div className="mode-title">Transfer Mode</div>
            <div className="mode-description">
              Transfer data from source document to target document
            </div>
          </div>
        </label>
        <label className="mode-option">
          <input
            type="radio"
            name="mode"
            value="scratch"
            checked={mode === "scratch"}
            onChange={(e) => {
              setMode(e.target.value as "scratch");
              setError(null);
            }}
          />
          <div className="mode-content">
            <div className="mode-title">Scratch Mode</div>
            <div className="mode-description">
              Fill target document from scratch (questions will be asked)
            </div>
          </div>
        </label>
      </div>

      <div className="job-creator-uploads">
        {mode === "transfer" && (
          <DocumentUpload
            documentType="source"
            onUploadComplete={handleSourceUpload}
            disabled={creating}
          />
        )}
        <DocumentUpload
          documentType="target"
          onUploadComplete={handleTargetUpload}
          disabled={creating}
        />
      </div>

      {error && <div className="job-creator-error">{error}</div>}

      <div className="job-creator-actions">
        <button
          onClick={handleCreateJob}
          disabled={!canCreateJob || creating}
          className="btn-create-job"
        >
          {creating ? "Creating Job..." : "Create Job"}
        </button>
      </div>
    </div>
  );
}
