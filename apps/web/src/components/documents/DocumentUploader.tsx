/**
 * Document upload component with drag-and-drop support.
 */

import { useState, useRef, useCallback, type DragEvent, type CSSProperties } from 'react';
import type { DocumentResponse, DocumentType } from '../../types/api';
import { useDocumentUpload, formatFileSize } from '../../hooks/useDocumentUpload';
import { Button } from '../ui/Button';

export interface DocumentUploaderProps {
  documentType: DocumentType;
  onUploadComplete: (document: DocumentResponse) => void;
  disabled?: boolean;
  label?: string;
  required?: boolean;
}

export function DocumentUploader({
  documentType,
  onUploadComplete,
  disabled = false,
  label,
  required = false,
}: DocumentUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    file,
    document,
    uploading,
    error,
    validationError,
    selectFile,
    clearFile,
    upload,
    reset,
  } = useDocumentUpload();

  const handleDragEnter = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (disabled) return;

      const droppedFile = e.dataTransfer.files?.[0];
      if (droppedFile) {
        selectFile(droppedFile);
      }
    },
    [disabled, selectFile]
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        selectFile(selectedFile);
      }
    },
    [selectFile]
  );

  const handleUpload = useCallback(async () => {
    const result = await upload(documentType);
    if (result) {
      onUploadComplete(result);
    }
  }, [upload, documentType, onUploadComplete]);

  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const displayLabel = label || (documentType === 'source' ? 'Source Document' : 'Target Document');

  const containerStyles: CSSProperties = {
    opacity: disabled ? 0.6 : 1,
    pointerEvents: disabled ? 'none' : 'auto',
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '12px',
  };

  const labelStyles: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
  };

  const requiredStyles: CSSProperties = {
    fontSize: '12px',
    fontWeight: 500,
    color: 'white',
    backgroundColor: '#ef4444',
    padding: '2px 6px',
    borderRadius: '4px',
  };

  const dropzoneStyles: CSSProperties = {
    border: `2px dashed ${isDragging ? '#3b82f6' : '#d1d5db'}`,
    borderRadius: '8px',
    padding: '24px',
    textAlign: 'center',
    backgroundColor: isDragging ? '#eff6ff' : '#fafafa',
    transition: 'all 0.15s ease',
    cursor: disabled ? 'not-allowed' : 'pointer',
  };

  const fileInfoStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    backgroundColor: '#f3f4f6',
    borderRadius: '8px',
    marginTop: '12px',
  };

  const successStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '16px',
    backgroundColor: '#f0fdf4',
    border: '1px solid #86efac',
    borderRadius: '8px',
  };

  const errorStyles: CSSProperties = {
    marginTop: '8px',
    padding: '8px 12px',
    backgroundColor: '#fee2e2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    fontSize: '13px',
    color: '#991b1b',
  };

  // Show success state if document is uploaded
  if (document) {
    return (
      <div style={containerStyles}>
        <div style={headerStyles}>
          <span style={labelStyles}>{displayLabel}</span>
          {required && <span style={requiredStyles}>Required</span>}
        </div>
        <div style={successStyles}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: '#22c55e',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              fontWeight: 600,
            }}
          >
            O
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '14px', fontWeight: 500, color: '#166534' }}>
              {document.meta.filename}
            </div>
            <div style={{ fontSize: '12px', color: '#22c55e', marginTop: '2px' }}>
              {document.meta.page_count} page{document.meta.page_count !== 1 ? 's' : ''} - {formatFileSize(document.meta.file_size)}
            </div>
            <div style={{ fontSize: '11px', color: '#6b7280', marginTop: '2px' }}>
              ID: {document.document_id.slice(0, 8)}...
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={reset}>
            Change
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyles}>
      <div style={headerStyles}>
        <span style={labelStyles}>{displayLabel}</span>
        {required && <span style={requiredStyles}>Required</span>}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.webp"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        disabled={disabled || uploading}
      />

      <div
        style={dropzoneStyles}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={!file ? handleBrowseClick : undefined}
        role="button"
        tabIndex={0}
        aria-label={`Upload ${displayLabel}`}
      >
        {!file ? (
          <>
            <div style={{ fontSize: '36px', marginBottom: '12px', color: '#9ca3af' }}>
              ^
            </div>
            <p style={{ margin: 0, fontSize: '14px', color: '#374151', fontWeight: 500 }}>
              Drop your file here or click to browse
            </p>
            <p style={{ margin: '8px 0 0 0', fontSize: '12px', color: '#6b7280' }}>
              PDF, PNG, JPEG, TIFF, WebP (max 50MB)
            </p>
          </>
        ) : (
          <div>
            <div style={{ fontSize: '36px', marginBottom: '8px' }}>
              [PDF]
            </div>
            <p style={{ margin: 0, fontSize: '14px', color: '#374151', fontWeight: 500 }}>
              {file.name}
            </p>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#6b7280' }}>
              {formatFileSize(file.size)}
            </p>
          </div>
        )}
      </div>

      {file && !document && (
        <div style={fileInfoStyles}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              {file.name}
            </div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
              {formatFileSize(file.size)}
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={clearFile} disabled={uploading}>
            Remove
          </Button>
          <Button variant="primary" size="sm" onClick={handleUpload} loading={uploading}>
            Upload
          </Button>
        </div>
      )}

      {(error || validationError) && (
        <div style={errorStyles}>
          {validationError || error}
        </div>
      )}
    </div>
  );
}
