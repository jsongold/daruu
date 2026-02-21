/**
 * Chat input component using AI Elements styling.
 * Supports drag-and-drop file uploads and keyboard shortcuts.
 *
 * Uses Tailwind CSS for styling (AI Elements pattern)
 */

import { useState, useRef, useCallback, type DragEvent, type KeyboardEvent, type ChangeEvent } from 'react';
import { cn } from '@/lib/utils';
import { SendIcon, PaperclipIcon, XIcon, FileIcon, Loader2Icon } from 'lucide-react';

export interface ChatInputProps {
  onSend: (message: string, files?: File[]) => void;
  onFilesSelected?: (files: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
  maxFiles?: number;
  acceptedFileTypes?: string[];
  loading?: boolean;
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
  loading = false,
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
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  const isDisabled = disabled || loading;
  const canSend = !isDisabled && (message.trim() || pendingFiles.length > 0);

  return (
    <div className="border-t border-border bg-background p-4">
      <div
        className={cn(
          "flex flex-col gap-3 rounded-lg p-3 transition-colors",
          isDragging && "border-2 border-dashed border-primary bg-primary/5"
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Pending files */}
        {pendingFiles.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {pendingFiles.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center gap-2 rounded-md bg-muted px-3 py-1.5 text-sm"
              >
                <FileIcon className="h-4 w-4 text-muted-foreground" />
                <span className="max-w-[150px] truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(index)}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={`Remove ${file.name}`}
                >
                  <XIcon className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Error message */}
        {fileError && (
          <p className="text-sm text-destructive">{fileError}</p>
        )}

        {/* Input row */}
        <div className="flex items-end gap-2">
          {/* Attach button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isDisabled}
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
              "border border-input bg-background",
              "text-muted-foreground hover:bg-muted hover:text-foreground",
              "transition-colors",
              "disabled:pointer-events-none disabled:opacity-50"
            )}
            aria-label="Attach files"
          >
            <PaperclipIcon className="h-5 w-5" />
          </button>

          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isDisabled}
            rows={1}
            className={cn(
              "flex-1 min-h-[44px] max-h-[200px] resize-none rounded-lg",
              "border border-input bg-background px-4 py-2.5",
              "text-sm placeholder:text-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50"
            )}
          />

          {/* Send button */}
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
              "bg-primary text-primary-foreground",
              "hover:bg-primary/90 transition-colors",
              "disabled:pointer-events-none disabled:opacity-50"
            )}
            aria-label="Send message"
          >
            {loading ? (
              <Loader2Icon className="h-5 w-5 animate-spin" />
            ) : (
              <SendIcon className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={acceptedFileTypes.join(',')}
        onChange={handleFileInputChange}
        className="hidden"
      />

      {/* Drop indicator */}
      {isDragging && (
        <p className="mt-2 text-center text-sm font-medium text-primary">
          Drop files here to upload
        </p>
      )}
    </div>
  );
}
