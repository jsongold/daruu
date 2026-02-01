"""Adapter implementations for the Structure/Labelling service.

Concrete implementations of the Port interfaces:
- OpenCVStructureDetector: Deterministic structure detection using OpenCV
- LocalPageImageLoader: Load images from local file system

These adapters can be swapped out for different implementations
(e.g., S3 storage, different detection algorithms) without changing
the service code.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.common import BBox
from app.services.structure_labelling.domain.models import (
    BoxCandidate,
    DetectedStructures,
    LabelCandidate,
    TableCandidate,
    TableCell,
    TextBlock,
)
from app.services.structure_labelling.ports import (
    PageImageLoaderPort,
    StructureDetectorPort,
)


@dataclass
class OpenCVStructureDetector:
    """OpenCV-based structure detection implementation.

    Uses OpenCV for deterministic detection of:
    - Input boxes (line detection, contour analysis)
    - Tables (grid detection, cell extraction)
    - Text regions (for label candidates)

    This is a Service component (deterministic, no LLM).

    Configuration:
        min_box_area: Minimum area for box detection (pixels^2)
        max_box_area: Maximum area for box detection (pixels^2)
        line_threshold: Threshold for Hough line detection
        table_min_cells: Minimum cells to detect as table
        canny_low: Canny edge detection low threshold
        canny_high: Canny edge detection high threshold
        min_line_length: Minimum line length for table detection
        max_line_gap: Maximum gap between line segments
    """

    min_box_area: int = 400
    max_box_area: int = 500000
    line_threshold: int = 80
    table_min_cells: int = 4
    canny_low: int = 50
    canny_high: int = 150
    min_line_length: int = 50
    max_line_gap: int = 10
    _cv2_available: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Check if OpenCV is available and initialize."""
        try:
            import cv2  # noqa: F401
            import numpy as np  # noqa: F401

            self._cv2_available = True
        except ImportError:
            self._cv2_available = False

    def _decode_image(self, page_image: bytes) -> Any:
        """Decode image bytes to numpy array using Pillow.

        Uses Pillow (PIL) for robust image decoding that handles
        multiple formats (PNG, JPEG, TIFF, WebP, etc.) automatically.

        Args:
            page_image: Image bytes in any supported format

        Returns:
            OpenCV image (numpy array in BGR format)

        Raises:
            ValueError: If image cannot be decoded
        """
        import io
        import logging

        import numpy as np
        from PIL import Image

        logger = logging.getLogger(__name__)

        if not page_image or len(page_image) < 8:
            raise ValueError("Image data is empty or too small")

        try:
            # Use Pillow to decode the image (handles PNG, JPEG, etc.)
            pil_image = Image.open(io.BytesIO(page_image))
            # Convert to RGB if necessary (handles grayscale, RGBA, etc.)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            # Convert to numpy array
            img_rgb = np.array(pil_image)
            # Convert RGB to BGR for OpenCV compatibility
            img_bgr = img_rgb[:, :, ::-1].copy()
            return img_bgr
        except Exception as e:
            logger.warning(f"Pillow failed to decode image: {e}")
            raise ValueError(f"Failed to decode image: {e}")

    def _classify_box_type(
        self, width: float, height: float, aspect_ratio: float, area: float
    ) -> str:
        """Classify box type based on dimensions.

        Args:
            width: Box width in pixels
            height: Box height in pixels
            aspect_ratio: Width/height ratio
            area: Box area in pixels^2

        Returns:
            Box type string: "checkbox", "signature", or "input"
        """
        # Small square boxes are likely checkboxes
        if area < 2000 and 0.7 < aspect_ratio < 1.4:
            return "checkbox"

        # Large boxes with specific aspect ratios are likely signature fields
        if area > 10000 and 2.0 < aspect_ratio < 6.0:
            return "signature"

        # Default to input field
        return "input"

    def _filter_nested_boxes(
        self, boxes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter out boxes that are fully contained within other boxes.

        Keeps only outermost boxes to avoid duplicate detections.

        Args:
            boxes: List of box dictionaries with x, y, width, height

        Returns:
            Filtered list of non-nested boxes
        """
        filtered: list[dict[str, Any]] = []

        for box in boxes:
            is_nested = False
            box_x1 = box["x"]
            box_y1 = box["y"]
            box_x2 = box_x1 + box["width"]
            box_y2 = box_y1 + box["height"]

            for other in boxes:
                if box is other:
                    continue

                other_x1 = other["x"]
                other_y1 = other["y"]
                other_x2 = other_x1 + other["width"]
                other_y2 = other_y1 + other["height"]

                # Check if box is fully contained in other
                margin = 5
                if (
                    box_x1 >= other_x1 - margin
                    and box_y1 >= other_y1 - margin
                    and box_x2 <= other_x2 + margin
                    and box_y2 <= other_y2 + margin
                    and other["area"] > box["area"]
                ):
                    is_nested = True
                    break

            if not is_nested:
                filtered.append(box)

        return filtered

    async def detect_structures(
        self,
        page: int,
        page_image: bytes,
        text_blocks: list[TextBlock] | None = None,
        options: dict[str, Any] | None = None,
    ) -> DetectedStructures:
        """Detect all structures in a page image.

        Runs the full OpenCV detection pipeline:
        1. Decode image bytes to numpy array
        2. Run box detection for input fields
        3. Run table detection for grids
        4. Convert text blocks to label candidates

        Args:
            page: Page number
            page_image: PNG image bytes
            text_blocks: Optional native PDF text blocks
            options: Detection options

        Returns:
            DetectedStructures with all candidates
        """
        boxes = await self.detect_boxes(page, page_image, options)
        tables = await self.detect_tables(page, page_image, options)

        # Convert text blocks to label candidates
        labels: list[LabelCandidate] = []
        if text_blocks:
            for block in text_blocks:
                if len(block.text.strip()) > 0 and len(block.text) < 100:
                    labels.append(
                        LabelCandidate(
                            id=f"label_{block.id}",
                            text=block.text.strip(),
                            bbox=block.bbox,
                            source="pdf_text",
                            confidence=block.confidence,
                        )
                    )

        return DetectedStructures(
            page=page,
            text_blocks=tuple(text_blocks or []),
            box_candidates=tuple(boxes),
            table_candidates=tuple(tables),
            label_candidates=tuple(labels),
        )

    async def detect_boxes(
        self,
        page: int,
        page_image: bytes,
        options: dict[str, Any] | None = None,
    ) -> list[BoxCandidate]:
        """Detect input boxes in a page image using OpenCV.

        Uses edge detection and contour analysis to find rectangular regions
        that likely represent form input fields, checkboxes, or signature areas.

        Detection pipeline:
        1. Convert to grayscale
        2. Apply Gaussian blur to reduce noise
        3. Apply Canny edge detection
        4. Apply morphological operations to close gaps
        5. Find contours
        6. Filter by area, aspect ratio, and rectangularity
        7. Classify box types
        8. Filter nested boxes

        Args:
            page: Page number
            page_image: PNG image bytes
            options: Detection options (min_area, max_area, etc.)

        Returns:
            List of detected BoxCandidate objects
        """
        if not self._cv2_available:
            return []

        import cv2

        try:
            img = self._decode_image(page_image)
        except ValueError:
            return []

        # Get image dimensions
        img_height, img_width = img.shape[:2]

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Apply adaptive threshold to get binary image
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        # Apply Canny edge detection
        edges = cv2.Canny(blurred, self.canny_low, self.canny_high)

        # Combine edges with binary threshold
        combined = cv2.bitwise_or(edges, binary)

        # Apply morphological operations to close gaps in rectangles
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Get options
        opts = options or {}
        min_area = opts.get("min_area", self.min_box_area)
        max_area = opts.get("max_area", self.max_box_area)

        # Process contours
        raw_boxes: list[dict[str, Any]] = []

        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h

            # Filter by area
            if area < min_area or area > max_area:
                continue

            # Calculate aspect ratio
            aspect_ratio = w / max(h, 1)

            # Filter extreme aspect ratios (too thin or too tall)
            if aspect_ratio < 0.2 or aspect_ratio > 20:
                continue

            # Check rectangularity using contour approximation
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Accept quadrilaterals and shapes that approximate rectangles
            if len(approx) < 4 or len(approx) > 8:
                continue

            # Calculate rectangularity (how much the contour fills its bounding rect)
            contour_area = cv2.contourArea(contour)
            rect_area = w * h
            rectangularity = contour_area / max(rect_area, 1)

            # Accept shapes that are reasonably rectangular
            if rectangularity < 0.5:
                continue

            # Calculate confidence based on rectangularity
            confidence = min(1.0, rectangularity + 0.2)

            raw_boxes.append({
                "x": float(x),
                "y": float(y),
                "width": float(w),
                "height": float(h),
                "area": area,
                "aspect_ratio": aspect_ratio,
                "confidence": confidence,
            })

        # Filter nested boxes
        filtered_boxes = self._filter_nested_boxes(raw_boxes)

        # Create BoxCandidate objects
        candidates: list[BoxCandidate] = []
        for i, box_data in enumerate(filtered_boxes):
            box_type = self._classify_box_type(
                box_data["width"],
                box_data["height"],
                box_data["aspect_ratio"],
                box_data["area"],
            )

            candidate = BoxCandidate(
                id=f"box_{page}_{i}_{uuid4().hex[:6]}",
                bbox=BBox(
                    x=box_data["x"],
                    y=box_data["y"],
                    width=box_data["width"],
                    height=box_data["height"],
                    page=page,
                ),
                box_type=box_type,
                has_border=True,
                fill_color=None,
                confidence=box_data["confidence"],
                neighboring_text=[],
            )
            candidates.append(candidate)

        return candidates

    async def detect_tables(
        self,
        page: int,
        page_image: bytes,
        options: dict[str, Any] | None = None,
    ) -> list[TableCandidate]:
        """Detect tables in a page image using line detection.

        Uses Hough line detection to identify table structures:
        1. Detect horizontal and vertical lines
        2. Find intersections
        3. Build grid structure from intersections
        4. Extract cell boundaries

        Args:
            page: Page number
            page_image: PNG image bytes
            options: Detection options (min_cells, line_threshold, etc.)

        Returns:
            List of detected TableCandidate objects
        """
        if not self._cv2_available:
            return []

        import cv2
        import numpy as np

        try:
            img = self._decode_image(page_image)
        except ValueError:
            return []

        img_height, img_width = img.shape[:2]

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply binary threshold
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(40, img_width // 20), 1)
        )
        horizontal_lines = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2
        )

        # Detect vertical lines
        vertical_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (1, max(40, img_height // 30))
        )
        vertical_lines = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2
        )

        # Combine horizontal and vertical lines
        table_mask = cv2.add(horizontal_lines, vertical_lines)

        # Find contours of the combined mask (potential table regions)
        contours, _ = cv2.findContours(
            table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        opts = options or {}
        min_cells = opts.get("min_cells", self.table_min_cells)

        tables: list[TableCandidate] = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Filter small regions
            if w < 100 or h < 50:
                continue

            # Extract the table region
            table_region = table_mask[y : y + h, x : x + w]

            # Count horizontal and vertical lines in the region
            h_lines = self._count_lines(table_region, "horizontal")
            v_lines = self._count_lines(table_region, "vertical")

            # Need at least 2 horizontal and 2 vertical lines for a table
            if h_lines < 2 or v_lines < 2:
                continue

            # Estimate grid dimensions
            rows = max(1, h_lines - 1)
            cols = max(1, v_lines - 1)

            # Check minimum cells
            if rows * cols < min_cells:
                continue

            # Extract cell boundaries
            cells = self._extract_cells(
                table_region, x, y, rows, cols, page
            )

            if len(cells) < min_cells:
                continue

            # Calculate confidence based on grid regularity
            confidence = min(1.0, 0.6 + 0.1 * min(rows, cols))

            table = TableCandidate(
                id=f"table_{page}_{len(tables)}_{uuid4().hex[:6]}",
                bbox=BBox(
                    x=float(x),
                    y=float(y),
                    width=float(w),
                    height=float(h),
                    page=page,
                ),
                rows=rows,
                cols=cols,
                cells=tuple(cells),
                has_header_row=True,  # Assume first row is header
                has_header_col=False,
                confidence=confidence,
            )
            tables.append(table)

        return tables

    def _count_lines(self, region: Any, direction: str) -> int:
        """Count horizontal or vertical lines in a region.

        Args:
            region: Binary image region
            direction: "horizontal" or "vertical"

        Returns:
            Estimated number of lines
        """
        import cv2
        import numpy as np

        if direction == "horizontal":
            # Sum along columns, find peaks
            projection = np.sum(region, axis=1)
        else:
            # Sum along rows, find peaks
            projection = np.sum(region, axis=0)

        # Normalize
        projection = projection / (projection.max() + 1)

        # Count peaks (line positions)
        threshold = 0.3
        above_threshold = projection > threshold

        # Count transitions from below to above threshold
        transitions = np.diff(above_threshold.astype(int))
        line_count = np.sum(transitions == 1)

        return int(line_count)

    def _extract_cells(
        self,
        table_region: Any,
        offset_x: int,
        offset_y: int,
        rows: int,
        cols: int,
        page: int,
    ) -> list[TableCell]:
        """Extract cell boundaries from a table region.

        Uses projection analysis to find row and column boundaries.

        Args:
            table_region: Binary image of the table
            offset_x: X offset of table in original image
            offset_y: Y offset of table in original image
            rows: Estimated number of rows
            cols: Estimated number of columns
            page: Page number

        Returns:
            List of TableCell objects
        """
        import numpy as np

        h, w = table_region.shape[:2]

        # Find row boundaries
        row_projection = np.sum(table_region, axis=1)
        row_boundaries = self._find_boundaries(row_projection, rows + 1)
        if len(row_boundaries) < 2:
            row_boundaries = [0, h]

        # Find column boundaries
        col_projection = np.sum(table_region, axis=0)
        col_boundaries = self._find_boundaries(col_projection, cols + 1)
        if len(col_boundaries) < 2:
            col_boundaries = [0, w]

        cells: list[TableCell] = []

        for row_idx in range(len(row_boundaries) - 1):
            for col_idx in range(len(col_boundaries) - 1):
                y1 = row_boundaries[row_idx]
                y2 = row_boundaries[row_idx + 1]
                x1 = col_boundaries[col_idx]
                x2 = col_boundaries[col_idx + 1]

                cell = TableCell(
                    row=row_idx,
                    col=col_idx,
                    bbox=BBox(
                        x=float(offset_x + x1),
                        y=float(offset_y + y1),
                        width=float(x2 - x1),
                        height=float(y2 - y1),
                        page=page,
                    ),
                    text=None,  # Text extraction would require OCR
                    is_header=(row_idx == 0),
                    rowspan=1,
                    colspan=1,
                )
                cells.append(cell)

        return cells

    def _find_boundaries(self, projection: Any, num_boundaries: int) -> list[int]:
        """Find line boundaries from projection.

        Args:
            projection: 1D array of summed pixel values
            num_boundaries: Expected number of boundaries

        Returns:
            List of boundary positions
        """
        import numpy as np

        # Normalize
        projection = projection / (projection.max() + 1)

        # Find peaks (line positions)
        threshold = 0.3
        above_threshold = projection > threshold

        # Find boundary positions
        boundaries: list[int] = [0]

        # Find transitions
        transitions = np.where(np.diff(above_threshold.astype(int)) != 0)[0]

        for t in transitions:
            if len(boundaries) < num_boundaries - 1:
                boundaries.append(int(t))

        boundaries.append(len(projection) - 1)

        return boundaries


@dataclass
class LocalPageImageLoader:
    """Local file system page image loader.

    Loads page images from local storage for processing.

    Configuration:
        base_path: Base directory for image storage
    """

    base_path: str = "/data/artifacts"

    async def load_image(self, image_ref: str) -> bytes:
        """Load a page image from local storage.

        Args:
            image_ref: Path to the image (absolute or relative to base_path)

        Returns:
            Image bytes

        Raises:
            FileNotFoundError: If image not found
            IOError: If loading fails
        """
        # Handle absolute and relative paths
        if image_ref.startswith("/"):
            path = Path(image_ref)
        else:
            path = Path(self.base_path) / image_ref

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        return path.read_bytes()

    async def load_images(
        self, image_refs: list[str]
    ) -> dict[str, bytes]:
        """Load multiple page images.

        Loads images sequentially from local storage.
        TODO: Add parallel loading for better performance.

        Args:
            image_refs: List of image paths

        Returns:
            Dictionary mapping image_ref to image bytes

        Raises:
            FileNotFoundError: If any image not found
        """
        result: dict[str, bytes] = {}

        for ref in image_refs:
            result[ref] = await self.load_image(ref)

        return result


@dataclass
class MockStructureDetector:
    """Mock structure detector for testing.

    Returns predefined structures for testing purposes.
    """

    mock_boxes: list[BoxCandidate] = field(default_factory=list)
    mock_tables: list[TableCandidate] = field(default_factory=list)
    mock_labels: list[LabelCandidate] = field(default_factory=list)

    async def detect_structures(
        self,
        page: int,
        page_image: bytes,
        text_blocks: list[TextBlock] | None = None,
        options: dict[str, Any] | None = None,
    ) -> DetectedStructures:
        """Return predefined mock structures."""
        return DetectedStructures(
            page=page,
            text_blocks=tuple(text_blocks or []),
            box_candidates=tuple(self.mock_boxes),
            table_candidates=tuple(self.mock_tables),
            label_candidates=tuple(self.mock_labels),
        )

    async def detect_boxes(
        self,
        page: int,
        page_image: bytes,
        options: dict[str, Any] | None = None,
    ) -> list[BoxCandidate]:
        """Return mock boxes."""
        return self.mock_boxes

    async def detect_tables(
        self,
        page: int,
        page_image: bytes,
        options: dict[str, Any] | None = None,
    ) -> list[TableCandidate]:
        """Return mock tables."""
        return self.mock_tables


@dataclass
class MockPageImageLoader:
    """Mock page image loader for testing.

    Returns predefined image data for testing purposes.
    """

    mock_images: dict[str, bytes] = field(default_factory=dict)
    default_image: bytes = field(default=b"mock_image_data")

    async def load_image(self, image_ref: str) -> bytes:
        """Return mock image data."""
        if image_ref in self.mock_images:
            return self.mock_images[image_ref]
        return self.default_image

    async def load_images(
        self, image_refs: list[str]
    ) -> dict[str, bytes]:
        """Return mock images for all refs."""
        return {ref: await self.load_image(ref) for ref in image_refs}


# Protocol verification
def _verify_protocols() -> None:
    """Verify that adapters implement their protocols."""
    detector: StructureDetectorPort = OpenCVStructureDetector()  # noqa: F841
    loader: PageImageLoaderPort = LocalPageImageLoader()  # noqa: F841
    mock_detector: StructureDetectorPort = MockStructureDetector()  # noqa: F841
    mock_loader: PageImageLoaderPort = MockPageImageLoader()  # noqa: F841
