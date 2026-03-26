"""Port interfaces for the Structure/Labelling service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.

Ports:
- FieldLabellingAgentPort: LLM-based label-to-position linking
- StructureDetectorPort: Deterministic structure detection (OpenCV, etc.)
- PageImageLoaderPort: Load page images for analysis
"""

from typing import Any, Protocol

from app.services.structure_labelling.domain.models import (
    BoxCandidate,
    DetectedStructures,
    LabelCandidate,
    LinkedField,
    StructureEvidence,
    TableCandidate,
    TextBlock,
)


class FieldLabellingAgentPort(Protocol):
    """Port for LLM-based field labelling agent.

    This agent uses LLM reasoning to link labels to field positions.
    This is the CRITICAL component that performs semantic understanding
    and cannot be replaced with rule-based logic per PRD requirements.

    Implementations:
    - LangChainFieldLabellingAgent: Uses LangChain for LLM abstraction
    - MockFieldLabellingAgent: For testing

    The agent should:
    - Analyze page images for visual context
    - Match label candidates to box candidates
    - Determine field types based on context
    - Provide confidence scores and evidence
    """

    async def link_labels_to_boxes(
        self,
        page: int,
        page_image: bytes | None,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
        table_candidates: list[TableCandidate],
        text_blocks: list[TextBlock],
        context: dict[str, Any] | None = None,
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Link labels to field positions using LLM reasoning.

        This is the core function that performs label-to-position linking.
        MUST use LLM for reasoning - rules alone cannot determine linkages.

        Args:
            page: Page number being processed
            page_image: Rendered page image bytes for visual analysis
            label_candidates: Potential label texts with positions
            box_candidates: Detected input boxes/fields
            table_candidates: Detected table structures
            text_blocks: Native PDF text blocks for context
            context: Additional context (document type, language, etc.)

        Returns:
            Tuple of:
            - List of LinkedField with confirmed label-to-box linkages
            - List of StructureEvidence documenting the decisions

        Raises:
            ValueError: If input validation fails
            RuntimeError: If LLM call fails after retries
        """
        ...


class StructureDetectorPort(Protocol):
    """Port for deterministic structure detection.

    Performs rule-based/algorithmic detection of document structures:
    - Input boxes (rectangles, form fields)
    - Tables (grid lines, cell structures)
    - Text regions (for potential labels)

    Implementations:
    - OpenCVStructureDetector: Uses OpenCV for detection
    - PdfFormDetector: Extracts AcroForm fields
    - MockStructureDetector: For testing

    This is a deterministic Service component (not an Agent).
    """

    async def detect_structures(
        self,
        page: int,
        page_image: bytes,
        text_blocks: list[TextBlock] | None = None,
        options: dict[str, Any] | None = None,
    ) -> DetectedStructures:
        """Detect structures in a page image.

        Performs deterministic detection of boxes, tables, and labels.
        Does NOT perform semantic interpretation (that's the Agent's job).

        Args:
            page: Page number being processed
            page_image: Rendered page image bytes
            text_blocks: Native PDF text blocks to incorporate
            options: Detection options (thresholds, modes, etc.)

        Returns:
            DetectedStructures containing all candidates found

        Raises:
            ValueError: If image is invalid or corrupted
        """
        ...

    async def detect_boxes(
        self,
        page: int,
        page_image: bytes,
        options: dict[str, Any] | None = None,
    ) -> list[BoxCandidate]:
        """Detect input boxes in a page image.

        Uses line detection and contour analysis to find potential
        input fields, checkboxes, signature areas, etc.

        Args:
            page: Page number being processed
            page_image: Rendered page image bytes
            options: Detection options (min_area, aspect_ratio, etc.)

        Returns:
            List of detected BoxCandidate objects
        """
        ...

    async def detect_tables(
        self,
        page: int,
        page_image: bytes,
        options: dict[str, Any] | None = None,
    ) -> list[TableCandidate]:
        """Detect tables in a page image.

        Uses grid line detection to identify table structures and
        extract cell boundaries.

        Args:
            page: Page number being processed
            page_image: Rendered page image bytes
            options: Detection options (min_cells, line_threshold, etc.)

        Returns:
            List of detected TableCandidate objects
        """
        ...


class PageImageLoaderPort(Protocol):
    """Port for loading page images.

    Abstracts the source of page images (local storage, S3, etc.)
    so the service doesn't depend on specific storage implementations.

    Implementations:
    - LocalPageImageLoader: Load from local file system
    - S3PageImageLoader: Load from S3 bucket
    - MockPageImageLoader: For testing
    """

    async def load_image(self, image_ref: str) -> bytes:
        """Load a page image from storage.

        Args:
            image_ref: Reference/path to the image

        Returns:
            Image bytes (PNG format expected)

        Raises:
            FileNotFoundError: If image not found
            IOError: If loading fails
        """
        ...

    async def load_images(self, image_refs: list[str]) -> dict[str, bytes]:
        """Load multiple page images.

        Optimized for batch loading with potential parallelization.

        Args:
            image_refs: List of image references

        Returns:
            Dictionary mapping image_ref to image bytes

        Raises:
            FileNotFoundError: If any image not found
            IOError: If loading fails
        """
        ...
