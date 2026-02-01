"""Service Gateway interface for calling pipeline services.

This protocol defines the contract for calling individual pipeline services.
Implementations can be:
- HTTP client calling microservices
- Direct function calls for monolithic deployment
- Message queue producers for async processing
"""

from typing import Protocol

from app.models import JobContext
from app.models.orchestrator import StageResult


class ServiceGateway(Protocol):
    """Interface for calling pipeline services.

    Each method corresponds to a stage in the document processing pipeline.
    Implementations must return a StageResult containing:
    - success: whether the stage succeeded
    - issues: any issues detected
    - activities: activity records generated
    - updated_fields: fields modified by the stage

    All methods are async to support both sync and async implementations.
    """

    async def call_ingest(self, job_context: JobContext) -> StageResult:
        """Call ingest service for document normalization.

        The ingest service handles:
        - PDF normalization (page size, rotation, layers)
        - Initial text extraction
        - Document metadata extraction

        Args:
            job_context: Current job state.

        Returns:
            StageResult with ingestion results.
        """
        ...

    async def call_structure(self, job_context: JobContext) -> StageResult:
        """Call structure service for document structure analysis.

        The structure service handles:
        - Text/box/table detection
        - Form field detection
        - Layout analysis

        Args:
            job_context: Current job state.

        Returns:
            StageResult with detected structure.
        """
        ...

    async def call_labelling(self, job_context: JobContext) -> StageResult:
        """Call labelling service for label-to-position linking.

        The labelling service uses LangChain internally to:
        - Link labels to bounding boxes
        - Identify anchors for fields
        - Resolve label ambiguities

        Args:
            job_context: Current job state.

        Returns:
            StageResult with labelled fields.
        """
        ...

    async def call_map(self, job_context: JobContext) -> StageResult:
        """Call mapping service for source-target field mapping.

        The mapping service handles:
        - Source to target field correspondence
        - Transform definitions
        - Mapping ambiguity detection

        Args:
            job_context: Current job state.

        Returns:
            StageResult with field mappings.
        """
        ...

    async def call_extract(self, job_context: JobContext) -> StageResult:
        """Call extraction service for value extraction.

        The extraction service handles:
        - Native PDF text extraction
        - OCR for images/scanned documents
        - LLM-assisted extraction for ambiguous cases

        Args:
            job_context: Current job state.

        Returns:
            StageResult with extracted values.
        """
        ...

    async def call_adjust(self, job_context: JobContext) -> StageResult:
        """Call adjustment service for coordinate correction.

        The adjustment service handles:
        - Anchor-relative positioning
        - Year-to-year layout difference absorption
        - Overflow/overlap prevention

        Args:
            job_context: Current job state.

        Returns:
            StageResult with adjusted coordinates.
        """
        ...

    async def call_fill(self, job_context: JobContext) -> StageResult:
        """Call fill service for document filling.

        The fill service handles:
        - AcroForm field filling
        - Overlay drawing for non-AcroForm PDFs
        - Font embedding

        Args:
            job_context: Current job state.

        Returns:
            StageResult with filling results.
        """
        ...

    async def call_review(self, job_context: JobContext) -> StageResult:
        """Call review service for validation and visual inspection.

        The review service handles:
        - Visual diff generation
        - Overflow/overlap detection
        - Missing value detection
        - Final validation

        Args:
            job_context: Current job state.

        Returns:
            StageResult with review issues.
        """
        ...
