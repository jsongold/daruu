/**
 * Custom hook for document upload with validation and progress tracking.
 */

import { useState, useCallback, useRef } from 'react';
import type { DocumentResponse, DocumentType } from '../types/api';
import { uploadDocument, ApiError } from '../api/client';

export interface UseDocumentUploadOptions {
  /** Maximum file size in bytes (default: 50MB) */
  maxSize?: number;
  /** Allowed MIME types */
  allowedTypes?: string[];
}

export interface UseDocumentUploadReturn {
  /** Selected file */
  file: File | null;
  /** Upload result */
  document: DocumentResponse | null;
  /** Loading state */
  uploading: boolean;
  /** Error message */
  error: string | null;
  /** Select a file */
  selectFile: (file: File) => void;
  /** Clear selected file */
  clearFile: () => void;
  /** Upload the selected file */
  upload: (documentType: DocumentType) => Promise<DocumentResponse | null>;
  /** Reset all state */
  reset: () => void;
  /** Validation errors */
  validationError: string | null;
}

const DEFAULT_MAX_SIZE = 50 * 1024 * 1024; // 50MB
const DEFAULT_ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/tiff',
  'image/tif',
  'image/webp',
];

const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'tif', 'webp'];

export function useDocumentUpload(
  options: UseDocumentUploadOptions = {}
): UseDocumentUploadReturn {
  const {
    maxSize = DEFAULT_MAX_SIZE,
    allowedTypes = DEFAULT_ALLOWED_TYPES,
  } = options;

  const [file, setFile] = useState<File | null>(null);
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const validateFile = useCallback((file: File): string | null => {
    // Check file size
    if (file.size > maxSize) {
      const maxSizeMB = Math.round(maxSize / (1024 * 1024));
      return `File too large. Maximum size is ${maxSizeMB}MB.`;
    }

    // Check MIME type
    if (file.type && !allowedTypes.includes(file.type)) {
      // Fall back to extension check
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
        return 'Invalid file type. Supported: PDF, PNG, JPEG, TIFF, WebP';
      }
    }

    // If no MIME type, check extension
    if (!file.type) {
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
        return 'Invalid file type. Supported: PDF, PNG, JPEG, TIFF, WebP';
      }
    }

    return null;
  }, [maxSize, allowedTypes]);

  const selectFile = useCallback((selectedFile: File) => {
    const validationResult = validateFile(selectedFile);

    if (validationResult) {
      setValidationError(validationResult);
      setFile(null);
      return;
    }

    setFile(selectedFile);
    setValidationError(null);
    setError(null);
    setDocument(null);
  }, [validateFile]);

  const clearFile = useCallback(() => {
    setFile(null);
    setValidationError(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const upload = useCallback(async (documentType: DocumentType): Promise<DocumentResponse | null> => {
    if (!file) {
      setError('No file selected');
      return null;
    }

    setUploading(true);
    setError(null);

    try {
      const result = await uploadDocument(file, documentType);
      setDocument(result);
      return result;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to upload document';
      setError(message);
      return null;
    } finally {
      setUploading(false);
    }
  }, [file]);

  const reset = useCallback(() => {
    setFile(null);
    setDocument(null);
    setUploading(false);
    setError(null);
    setValidationError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  return {
    file,
    document,
    uploading,
    error,
    selectFile,
    clearFile,
    upload,
    reset,
    validationError,
  };
}

/**
 * Format file size for display.
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
