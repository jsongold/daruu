/**
 * Bottom bar with document upload and document list.
 * Combines upload dropzone with horizontal document list.
 * Extended to support data sources for AI form filling.
 */

import { useCallback, useRef, useState } from 'react';
import type { DataSourceResponse } from '../../lib/api-types';
import { DataSourceChip } from './DataSourceChip';
import { TextInputModal } from './TextInputModal';
import { getAcceptedFileTypes, isSupportedFileType } from '../../api/dataSourceClient';

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
  // Data sources props (optional for backwards compatibility)
  dataSources?: DataSourceResponse[];
  onDataSourceUpload?: (files: File[]) => void;
  onDataSourceTextAdd?: (name: string, content: string) => void;
  onDataSourceRemove?: (id: string) => void;
  isDataSourceUploading?: boolean;
}

export function DocumentBar({
  documents,
  activeDocumentId,
  onUpload,
  onSelect,
  onRemove,
  onClearAll,
  isUploading,
  // Data sources
  dataSources = [],
  onDataSourceUpload,
  onDataSourceTextAdd,
  onDataSourceRemove,
  isDataSourceUploading = false,
}: DocumentBarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dataSourceInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isDataSourceDragOver, setIsDataSourceDragOver] = useState(false);
  const [isTextModalOpen, setIsTextModalOpen] = useState(false);

  // Check if data sources feature is enabled
  const hasDataSourcesFeature = Boolean(onDataSourceUpload || onDataSourceTextAdd);

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

  // Data source handlers
  const handleDataSourceFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0 && onDataSourceUpload) {
        const validFiles = Array.from(files).filter((f) => isSupportedFileType(f.name));
        if (validFiles.length > 0) {
          onDataSourceUpload(validFiles);
        }
        e.target.value = '';
      }
    },
    [onDataSourceUpload]
  );

  const handleDataSourceDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDataSourceDragOver(true);
  }, []);

  const handleDataSourceDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDataSourceDragOver(false);
  }, []);

  const handleDataSourceDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDataSourceDragOver(false);

      if (onDataSourceUpload) {
        const files = Array.from(e.dataTransfer.files).filter((f) =>
          isSupportedFileType(f.name)
        );
        if (files.length > 0) {
          onDataSourceUpload(files);
        }
      }
    },
    [onDataSourceUpload]
  );

  const handleDataSourceUploadClick = useCallback(() => {
    dataSourceInputRef.current?.click();
  }, []);

  const handleTextModalSubmit = useCallback(
    (name: string, content: string) => {
      if (onDataSourceTextAdd) {
        onDataSourceTextAdd(name, content);
        setIsTextModalOpen(false);
      }
    },
    [onDataSourceTextAdd]
  );

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

      {/* Data Sources Section */}
      {hasDataSourcesFeature && (
        <>
          {/* Section Divider */}
          <div className="w-px h-16 bg-gray-300 mx-2" />

          {/* Data Sources Label */}
          <div className="flex flex-col items-center shrink-0">
            <span className="text-xs font-medium text-gray-500 mb-1">YOUR DATA</span>

            {/* Data Source Upload Buttons */}
            <div className="flex gap-2">
              {/* File Upload */}
              <div
                onClick={handleDataSourceUploadClick}
                onDragOver={handleDataSourceDragOver}
                onDragLeave={handleDataSourceDragLeave}
                onDrop={handleDataSourceDrop}
                className={`
                  w-16 h-10 border-2 border-dashed rounded-lg flex flex-col items-center justify-center
                  cursor-pointer transition-colors
                  ${isDataSourceDragOver
                    ? 'border-green-500 bg-green-50'
                    : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
                  }
                  ${isDataSourceUploading ? 'opacity-50 pointer-events-none' : ''}
                `}
                title="Upload files (PDF, images, text, CSV)"
              >
                <input
                  ref={dataSourceInputRef}
                  type="file"
                  accept={getAcceptedFileTypes()}
                  onChange={handleDataSourceFileChange}
                  multiple
                  className="hidden"
                />
                {isDataSourceUploading ? (
                  <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                )}
              </div>

              {/* Text Input Button */}
              {onDataSourceTextAdd && (
                <button
                  onClick={() => setIsTextModalOpen(true)}
                  className="
                    w-16 h-10 border-2 border-dashed border-gray-300 rounded-lg
                    flex flex-col items-center justify-center
                    cursor-pointer transition-colors
                    hover:border-gray-400 hover:bg-gray-50
                  "
                  title="Add text data"
                >
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Data Source List */}
          {dataSources.length > 0 && (
            <>
              <div className="w-px h-12 bg-gray-200" />
              <div className="flex items-center gap-2 overflow-x-auto py-2">
                {dataSources.map((ds) => (
                  <DataSourceChip
                    key={ds.id}
                    dataSource={ds}
                    onRemove={() => onDataSourceRemove?.(ds.id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}

      {/* Text Input Modal */}
      <TextInputModal
        isOpen={isTextModalOpen}
        onClose={() => setIsTextModalOpen(false)}
        onSubmit={handleTextModalSubmit}
        isSubmitting={isDataSourceUploading}
      />
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
