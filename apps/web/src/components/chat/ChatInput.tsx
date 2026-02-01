/**
 * Chat input component with text input and file drop zone.
 * Supports drag-and-drop file uploads and keyboard shortcuts.
 */

import { useState, useRef, useCallback, type CSSProperties, type DragEvent, type KeyboardEvent, type ChangeEvent } from 'react';
import { Button } from '../ui/Button';

export interface ChatInputProps {
  onSend: (message: string, files?: File[]) => void;
  onFilesSelected?: (files: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
  maxFiles?: number;
  acceptedFileTypes?: string[];
}

const DEFAULT_ACCEPTED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/jpg',
];

const MAX_FILE_SIZE_MB = 10;

export function ChatInput({
  onSend,
  onFilesSelected,
  disabled = false,
  placeholder = 'Type a message or drop files here...',
  maxFiles = 5,
  acceptedFileTypes = DEFAULT_ACCEPTED_TYPES,
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFiles = useCallback((files: File[]): { valid: File[]; error: string | null } => {
    const valid: File[] = [];
    let error: string | null = null;

    for (const file of files) {
      if (!acceptedFileTypes.includes(file.type)) {
        error = `File type not supported: ${file.name}`;
        continue;
      }

      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        error = `File too large (max ${MAX_FILE_SIZE_MB}MB): ${file.name}`;
        continue;
      }

      valid.push(file);
    }

    if (valid.length + pendingFiles.length > maxFiles) {
      error = `Maximum ${maxFiles} files allowed`;
      return { valid: valid.slice(0, maxFiles - pendingFiles.length), error };
    }

    return { valid, error };
  }, [acceptedFileTypes, maxFiles, pendingFiles.length]);

  const handleFilesAdded = useCallback((files: File[]) => {
    const { valid, error } = validateFiles(files);
    setFileError(error);

    if (valid.length > 0) {
      const newPendingFiles = [...pendingFiles, ...valid];
      setPendingFiles(newPendingFiles);
      onFilesSelected?.(newPendingFiles);
    }
  }, [validateFiles, pendingFiles, onFilesSelected]);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
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

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    handleFilesAdded(files);
  }, [disabled, handleFilesAdded]);

  const handleFileInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    handleFilesAdded(files);
    // Reset input so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [handleFilesAdded]);

  const handleRemoveFile = useCallback((index: number) => {
    const newFiles = pendingFiles.filter((_, i) => i !== index);
    setPendingFiles(newFiles);
    onFilesSelected?.(newFiles);
    setFileError(null);
  }, [pendingFiles, onFilesSelected]);

  const handleSend = useCallback(() => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage && pendingFiles.length === 0) return;

    onSend(trimmedMessage, pendingFiles.length > 0 ? pendingFiles : undefined);
    setMessage('');
    setPendingFiles([]);
    setFileError(null);
  }, [message, pendingFiles, onSend]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const handleTextareaChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '16px',
    borderTop: '1px solid #e5e7eb',
    backgroundColor: 'white',
  };

  const dropZoneStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '12px',
    borderRadius: '12px',
    border: isDragging ? '2px dashed #3b82f6' : '2px dashed transparent',
    backgroundColor: isDragging ? '#eff6ff' : 'transparent',
    transition: 'all 0.15s ease',
  };

  const inputRowStyle: CSSProperties = {
    display: 'flex',
    gap: '8px',
    alignItems: 'flex-end',
  };

  const textareaStyle: CSSProperties = {
    flex: 1,
    minHeight: '44px',
    maxHeight: '200px',
    padding: '12px',
    fontSize: '14px',
    lineHeight: '1.5',
    border: '1px solid #d1d5db',
    borderRadius: '12px',
    resize: 'none',
    outline: 'none',
    fontFamily: 'inherit',
  };

  const fileListStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  };

  const fileChipStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 10px',
    backgroundColor: '#eff6ff',
    borderRadius: '6px',
    fontSize: '13px',
    color: '#1e40af',
  };

  const removeButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '16px',
    height: '16px',
    padding: 0,
    border: 'none',
    borderRadius: '50%',
    backgroundColor: 'transparent',
    color: '#6b7280',
    cursor: 'pointer',
  };

  const attachButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '44px',
    height: '44px',
    padding: 0,
    border: '1px solid #d1d5db',
    borderRadius: '12px',
    backgroundColor: 'white',
    color: '#6b7280',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
  };

  const errorStyle: CSSProperties = {
    fontSize: '12px',
    color: '#dc2626',
    padding: '4px 0',
  };

  return (
    <div style={containerStyle}>
      <div
        style={dropZoneStyle}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {pendingFiles.length > 0 && (
          <div style={fileListStyle}>
            {pendingFiles.map((file, index) => (
              <div key={`${file.name}-${index}`} style={fileChipStyle}>
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                  />
                </svg>
                <span>{file.name}</span>
                <button
                  style={removeButtonStyle}
                  onClick={() => handleRemoveFile(index)}
                  type="button"
                  aria-label={`Remove ${file.name}`}
                >
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {fileError && <div style={errorStyle}>{fileError}</div>}

        <div style={inputRowStyle}>
          <button
            style={attachButtonStyle}
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            type="button"
            aria-label="Attach files"
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          </button>

          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            style={textareaStyle}
            rows={1}
          />

          <Button
            variant="primary"
            onClick={handleSend}
            disabled={disabled || (!message.trim() && pendingFiles.length === 0)}
            style={{ height: '44px', minWidth: '44px', padding: '0 16px' }}
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </Button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={acceptedFileTypes.join(',')}
        onChange={handleFileInputChange}
        style={{ display: 'none' }}
      />

      {isDragging && (
        <div
          style={{
            textAlign: 'center',
            color: '#3b82f6',
            fontSize: '13px',
            fontWeight: 500,
          }}
        >
          Drop files here to upload
        </div>
      )}
    </div>
  );
}
