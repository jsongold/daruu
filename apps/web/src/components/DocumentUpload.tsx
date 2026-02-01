import { useState, useRef } from "react";
import { uploadDocument, type DocumentUploadResponse } from "../api/jobClient";
import "./DocumentUpload.css";

interface DocumentUploadProps {
  documentType: "source" | "target";
  onUploadComplete: (document: DocumentUploadResponse) => void;
  disabled?: boolean;
}

export function DocumentUpload({
  documentType,
  onUploadComplete,
  disabled = false,
}: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<DocumentUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      // Validate file type
      const validTypes = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
        "image/tif",
        "image/webp",
      ];
      
      if (!validTypes.includes(selectedFile.type)) {
        // Check by file extension as fallback
        const ext = selectedFile.name.split(".").pop()?.toLowerCase();
        const validExts = ["pdf", "png", "jpg", "jpeg", "tiff", "tif", "webp"];
        if (!ext || !validExts.includes(ext)) {
          setError(
            "Invalid file type. Supported: PDF, PNG, JPEG, TIFF, WebP"
          );
          return;
        }
      }

      // Validate file size (50MB max)
      const maxSize = 50 * 1024 * 1024; // 50MB
      if (selectedFile.size > maxSize) {
        setError(`File too large. Maximum size is 50MB.`);
        return;
      }

      setFile(selectedFile);
      setError(null);
      setUploaded(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const result = await uploadDocument(file, documentType);
      setUploaded(result);
      onUploadComplete(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleRemove = () => {
    setFile(null);
    setUploaded(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className={`document-upload ${disabled ? "disabled" : ""}`}>
      <div className="document-upload-header">
        <h3>
          {documentType === "source" ? "Source Document" : "Target Document"}
          {documentType === "target" && <span className="required-badge">Required</span>}
        </h3>
      </div>

      {!uploaded ? (
        <>
          <div className="document-upload-area">
            <input
              ref={fileInputRef}
              type="file"
              id={`file-input-${documentType}`}
              accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.webp,application/pdf,image/*"
              onChange={handleFileSelect}
              disabled={disabled || uploading}
              className="file-input"
            />
            <label
              htmlFor={`file-input-${documentType}`}
              className={`file-input-label ${disabled || uploading ? "disabled" : ""}`}
            >
              {file ? (
                <div className="file-selected">
                  <span className="file-icon">📄</span>
                  <div className="file-info">
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">{formatFileSize(file.size)}</div>
                  </div>
                </div>
              ) : (
                <div className="file-placeholder">
                  <span className="upload-icon">📤</span>
                  <span className="upload-text">
                    Click to select or drag and drop
                  </span>
                  <span className="upload-hint">
                    PDF, PNG, JPEG, TIFF, WebP (max 50MB)
                  </span>
                </div>
              )}
            </label>
          </div>

          {file && (
            <div className="document-upload-actions">
              <button
                onClick={handleUpload}
                disabled={uploading || disabled}
                className="btn-upload"
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
              <button
                onClick={handleRemove}
                disabled={uploading}
                className="btn-remove"
              >
                Remove
              </button>
            </div>
          )}

          {error && <div className="document-upload-error">{error}</div>}
        </>
      ) : (
        <div className="document-upload-success">
          <div className="success-content">
            <span className="success-icon">✓</span>
            <div className="success-info">
              <div className="success-filename">{uploaded.meta.filename}</div>
              <div className="success-meta">
                {uploaded.meta.page_count} page{uploaded.meta.page_count !== 1 ? "s" : ""} • {formatFileSize(uploaded.meta.file_size)}
              </div>
              <div className="success-id">ID: {uploaded.document_id.slice(0, 8)}...</div>
            </div>
          </div>
          <button onClick={handleRemove} className="btn-change">
            Change File
          </button>
        </div>
      )}
    </div>
  );
}
