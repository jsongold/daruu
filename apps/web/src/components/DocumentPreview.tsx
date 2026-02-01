import { useState, useEffect } from "react";
import { getPagePreview } from "../api/jobClient";
import "./DocumentPreview.css";

interface DocumentPreviewProps {
  documentId: string;
  pageCount: number;
  title: string;
  highlightedPage?: number;
}

export function DocumentPreview({
  documentId,
  pageCount,
  title,
  highlightedPage,
}: DocumentPreviewProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (highlightedPage && highlightedPage >= 1 && highlightedPage <= pageCount) {
      setCurrentPage(highlightedPage);
    }
  }, [highlightedPage, pageCount]);

  useEffect(() => {
    let mounted = true;

    async function loadPreview() {
      if (!documentId || currentPage < 1) {
        console.warn("DocumentPreview: Missing documentId or invalid page", { documentId, currentPage });
        return;
      }

      setLoading(true);
      setError(null);

      try {
        console.log("DocumentPreview: Loading preview", { documentId, currentPage });
        const url = await getPagePreview(documentId, currentPage);
        if (mounted) {
          // Clean up previous URL
          if (imageUrl) {
            URL.revokeObjectURL(imageUrl);
          }
          console.log("DocumentPreview: Preview loaded successfully", { url: url.substring(0, 50) + "..." });
          setImageUrl(url);
        }
      } catch (err) {
        console.error("DocumentPreview: Failed to load preview", { documentId, currentPage, error: err });
        if (mounted) {
          const errorMessage = err instanceof Error ? err.message : String(err);
          setError(errorMessage);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadPreview();

    return () => {
      mounted = false;
    };
  }, [documentId, currentPage]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, []);

  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < pageCount) {
      setCurrentPage(currentPage + 1);
    }
  };

  return (
    <div className="document-preview">
      <div className="document-preview-header">
        <h3 className="document-preview-title">{title}</h3>
        <div className="document-preview-pagination">
          <button
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            className="pagination-btn"
            aria-label="Previous page"
          >
            &lt;
          </button>
          <span className="pagination-info">
            Page {currentPage} of {pageCount}
          </span>
          <button
            onClick={handleNextPage}
            disabled={currentPage >= pageCount}
            className="pagination-btn"
            aria-label="Next page"
          >
            &gt;
          </button>
        </div>
      </div>

      <div className="document-preview-container">
        {loading && (
          <div className="document-preview-loading">
            <span>Loading page preview...</span>
          </div>
        )}

        {error && !loading && (
          <div className="document-preview-error">
            <span>Failed to load preview: {error}</span>
            <div style={{ fontSize: "12px", marginTop: "8px", color: "#6b7280" }}>
              Document ID: {documentId}, Page: {currentPage}
            </div>
            <button
              onClick={() => {
                setError(null);
                setLoading(true);
                getPagePreview(documentId, currentPage)
                  .then((url) => {
                    if (imageUrl) {
                      URL.revokeObjectURL(imageUrl);
                    }
                    setImageUrl(url);
                  })
                  .catch((err) => {
                    console.error("DocumentPreview: Retry failed", err);
                    setError(err instanceof Error ? err.message : "Failed to load");
                  })
                  .finally(() => setLoading(false));
              }}
              className="retry-btn"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && imageUrl && (
          <img
            src={imageUrl}
            alt={`${title} - Page ${currentPage}`}
            className="document-preview-image"
            onError={() => {
              console.error("DocumentPreview: Image failed to load", { imageUrl, documentId, currentPage });
              setError("Image failed to load");
              setImageUrl(null);
            }}
          />
        )}

        {!loading && !error && !imageUrl && (
          <div className="document-preview-loading">
            <span>No preview available</span>
            <div style={{ fontSize: "12px", marginTop: "8px", color: "#6b7280" }}>
              Document ID: {documentId}, Page: {currentPage}
            </div>
          </div>
        )}
      </div>

      {pageCount > 1 && (
        <div className="document-preview-thumbnails">
          {Array.from({ length: Math.min(pageCount, 10) }, (_, i) => i + 1).map(
            (page) => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`thumbnail-btn ${currentPage === page ? "active" : ""}`}
              >
                {page}
              </button>
            )
          )}
          {pageCount > 10 && <span className="thumbnail-more">...</span>}
        </div>
      )}
    </div>
  );
}
