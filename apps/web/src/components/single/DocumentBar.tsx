/**
 * Bottom bar with document upload and document list.
 * Combines upload dropzone with horizontal document list.
 */

import { useCallback, useRef, useState } from 'react';

interface DocumentWithPages {
  document_id: string;
  filename: string;
  page_count: number;
  pageUrls: string[];
}

interface DocumentBarProps {
  documents: DocumentWithPages[];
  activeDocumentId: string | null;
  onUpload: (file: File) => void;
  onSelect: (documentId: string) => void;
  onRemove: (documentId: string) => void;
  onClearAll: () => void;
  isUploading: boolean;
}

export function DocumentBar({
  documents,
  activeDocumentId,
  onUpload,
  onSelect,
  onRemove,
  onClearAll,
  isUploading,
}: DocumentBarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onUpload(file);
      e.target.value = ''; // Reset input
    }
  }, [onUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      onUpload(file);
    }
  }, [onUpload]);

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className="h-24 bg-white border-t border-gray-200 flex items-center px-4 gap-4 shrink-0">
      {/* Upload Button/Dropzone */}
      <div
        onClick={handleUploadClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          w-40 h-16 border-2 border-dashed rounded-lg flex flex-col items-center justify-center
          cursor-pointer transition-colors shrink-0
          ${isDragOver
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        {isUploading ? (
          <>
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-gray-500 mt-1">Uploading...</span>
          </>
        ) : (
          <>
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="text-xs text-gray-500 mt-1">Upload PDF</span>
          </>
        )}
      </div>

      {/* Divider */}
      <div className="w-px h-12 bg-gray-200" />

      {/* Document List */}
      <div className="flex-1 flex items-center gap-2 overflow-x-auto py-2">
        {documents.length === 0 ? (
          <span className="text-sm text-gray-400 italic">No documents uploaded</span>
        ) : (
          documents.map((doc) => (
            <DocumentChip
              key={doc.document_id}
              document={doc}
              isActive={doc.document_id === activeDocumentId}
              onSelect={() => onSelect(doc.document_id)}
              onRemove={() => onRemove(doc.document_id)}
            />
          ))
        )}
      </div>

      {/* Clear All */}
      {documents.length > 0 && (
        <>
          <div className="w-px h-12 bg-gray-200" />
          <button
            onClick={onClearAll}
            className="px-3 py-2 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors shrink-0"
          >
            Clear All
          </button>
        </>
      )}
    </div>
  );
}

interface DocumentChipProps {
  document: DocumentWithPages;
  isActive: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

function DocumentChip({ document, isActive, onSelect, onRemove }: DocumentChipProps) {
  const handleRemove = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onRemove();
  }, [onRemove]);

  // Truncate filename if too long
  const displayName = document.filename.length > 20
    ? document.filename.substring(0, 17) + '...'
    : document.filename;

  return (
    <div
      onClick={onSelect}
      className={`
        group relative flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer
        transition-colors shrink-0
        ${isActive
          ? 'bg-blue-100 text-blue-700 border border-blue-300'
          : 'bg-gray-100 text-gray-700 border border-transparent hover:bg-gray-200'
        }
      `}
    >
      {/* PDF Icon */}
      <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>

      {/* Filename */}
      <span className="text-sm font-medium" title={document.filename}>
        {displayName}
      </span>

      {/* Page count */}
      <span className="text-xs text-gray-500">
        {document.page_count}p
      </span>

      {/* Remove button */}
      <button
        onClick={handleRemove}
        className="
          absolute -top-1 -right-1 w-5 h-5 rounded-full bg-gray-500 text-white
          flex items-center justify-center opacity-0 group-hover:opacity-100
          hover:bg-red-500 transition-all
        "
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Active indicator */}
      {isActive && (
        <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-blue-600" />
      )}
    </div>
  );
}
