"""Text extraction service for data sources.

Extracts text and structured data from various file types:
- Text files: Plain text extraction
- CSV files: Parse into structured data
- PDF files: Use existing document service (text blocks)
"""

import csv
import io
import logging
from typing import Any

from app.models.data_source import DataSource, DataSourceType, ExtractionResult
from app.repositories import DataSourceRepository
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class TextExtractionService:
    """Service for extracting text and data from data sources."""

    def __init__(
        self,
        data_source_repo: DataSourceRepository | None = None,
        document_service: DocumentService | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            data_source_repo: Repository for data source operations.
            document_service: Service for document operations.
        """
        self._data_source_repo = data_source_repo
        self._document_service = document_service

    def extract_from_text(self, content: str) -> dict[str, Any]:
        """Extract structured data from plain text.

        For now, returns the raw text. Future: Use AI to extract key-value pairs.

        Args:
            content: Plain text content.

        Returns:
            Dictionary with extracted data.
        """
        # Basic extraction: look for common patterns
        extracted = {}

        # Look for email-like patterns
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try to find key: value patterns
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    # Only extract if key looks like a field name
                    if key and len(key) < 50 and not key.startswith("#"):
                        extracted[key] = value

        return extracted

    def extract_from_csv(self, content: str) -> dict[str, Any]:
        """Extract structured data from CSV content.

        Assumes first row is headers. Returns data as list of dicts.

        Args:
            content: CSV content as string.

        Returns:
            Dictionary with extracted data.
        """
        try:
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)

            if not rows:
                return {"rows": [], "headers": []}

            # Get headers
            headers = list(rows[0].keys()) if rows else []

            return {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
            }
        except csv.Error as e:
            logger.warning(f"Failed to parse CSV: {e}")
            return {"error": str(e), "rows": [], "headers": []}

    def extract_from_data_source(
        self,
        data_source: DataSource,
    ) -> ExtractionResult:
        """Extract data from a data source.

        Args:
            data_source: The data source to extract from.

        Returns:
            ExtractionResult with extracted fields.
        """
        extracted_fields: dict[str, Any] = {}
        raw_text: str | None = None
        confidence = 0.0

        if data_source.type == DataSourceType.TEXT:
            if data_source.text_content:
                raw_text = data_source.text_content
                extracted_fields = self.extract_from_text(data_source.text_content)
                confidence = 0.5 if extracted_fields else 0.1

        elif data_source.type == DataSourceType.CSV:
            if data_source.text_content:
                raw_text = data_source.text_content
                extracted_fields = self.extract_from_csv(data_source.text_content)
                confidence = 0.8 if extracted_fields.get("rows") else 0.1

        elif data_source.type in (DataSourceType.PDF, DataSourceType.IMAGE):
            # For PDFs and images, we need the document service
            if self._document_service and data_source.document_id:
                try:
                    text_blocks = self._document_service.extract_text_blocks(
                        data_source.document_id
                    )
                    if text_blocks:
                        # Combine all text blocks
                        raw_text = "\n".join(block.get("text", "") for block in text_blocks)
                        extracted_fields = self.extract_from_text(raw_text)
                        confidence = 0.3 if extracted_fields else 0.1
                except Exception as e:
                    logger.warning(
                        f"Failed to extract from document {data_source.document_id}: {e}"
                    )

        return ExtractionResult(
            data_source_id=data_source.id,
            extracted_fields=extracted_fields,
            confidence=confidence,
            raw_text=raw_text,
        )

    def combine_extractions(
        self,
        extractions: list[ExtractionResult],
    ) -> dict[str, Any]:
        """Combine extracted data from multiple sources.

        When the same field appears in multiple sources, uses the one with
        higher confidence.

        Args:
            extractions: List of extraction results.

        Returns:
            Combined dictionary of all extracted fields.
        """
        combined: dict[str, Any] = {}
        field_confidence: dict[str, float] = {}

        for extraction in extractions:
            for key, value in extraction.extracted_fields.items():
                existing_confidence = field_confidence.get(key, 0.0)
                if extraction.confidence > existing_confidence:
                    combined[key] = value
                    field_confidence[key] = extraction.confidence

        return combined


def get_text_extraction_service(
    data_source_repo: DataSourceRepository | None = None,
    document_service: DocumentService | None = None,
) -> TextExtractionService:
    """Factory function to create TextExtractionService.

    Args:
        data_source_repo: Optional data source repository.
        document_service: Optional document service.

    Returns:
        TextExtractionService instance.
    """
    return TextExtractionService(
        data_source_repo=data_source_repo,
        document_service=document_service,
    )
