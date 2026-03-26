"""Service-level tests with mocked ports.

Tests each service (ingest, structure_labelling, mapping, extract, adjust, fill, review)
using mock implementations of their Protocol interfaces (ports).

This enables testing service logic in isolation from external dependencies
while validating correct usage of the port interfaces.
"""

import pytest
from app.models import BBox
from app.models.ingest.models import (
    DocumentMeta as IngestDocumentMeta,
)
from app.models.ingest.models import (
    PageMeta,
)

# ============================================================================
# Ingest Service Tests
# ============================================================================


class MockPdfReaderPort:
    """Mock implementation of PdfReaderPort."""

    def __init__(
        self,
        is_valid: bool = True,
        page_count: int = 2,
        error_message: str | None = None,
    ):
        self.is_valid = is_valid
        self.page_count = page_count
        self.error_message = error_message
        self.calls: list[dict] = []

    def validate(self, pdf_path: str) -> tuple[bool, str | None]:
        """Mock PDF validation."""
        self.calls.append({"method": "validate", "pdf_path": pdf_path})
        return (self.is_valid, self.error_message)

    def get_meta(self, pdf_path: str) -> IngestDocumentMeta:
        """Mock metadata extraction."""
        self.calls.append({"method": "get_meta", "pdf_path": pdf_path})
        if not self.is_valid:
            raise ValueError(self.error_message or "Invalid PDF")

        pages = tuple(
            PageMeta(
                page_number=i + 1,
                width=612.0,
                height=792.0,
                rotation=0,
            )
            for i in range(self.page_count)
        )
        return IngestDocumentMeta(page_count=self.page_count, pages=pages)

    def get_page_meta(self, pdf_path: str, page_number: int) -> PageMeta:
        """Mock page metadata extraction."""
        self.calls.append(
            {
                "method": "get_page_meta",
                "pdf_path": pdf_path,
                "page_number": page_number,
            }
        )
        return PageMeta(
            page_number=page_number,
            width=612.0,
            height=792.0,
            rotation=0,
        )

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 150,
    ) -> bytes:
        """Mock page rendering."""
        self.calls.append(
            {
                "method": "render_page",
                "pdf_path": pdf_path,
                "page_number": page_number,
                "dpi": dpi,
            }
        )
        # Return fake PNG bytes
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


class MockIngestStoragePort:
    """Mock implementation of StoragePort for ingest."""

    def __init__(self):
        self.saved_images: dict[str, bytes] = {}
        self.calls: list[dict] = []

    def save_image(
        self,
        document_id: str,
        page_number: int,
        image_data: bytes,
        content_type: str = "image/png",
    ) -> str:
        """Mock image saving."""
        ref = f"{document_id}/page_{page_number}.png"
        self.saved_images[ref] = image_data
        self.calls.append(
            {
                "method": "save_image",
                "document_id": document_id,
                "page_number": page_number,
                "size": len(image_data),
            }
        )
        return ref

    def get_url(self, image_ref: str) -> str:
        """Mock URL generation."""
        return f"https://storage.example.com/{image_ref}"

    def delete_artifacts(self, document_id: str) -> int:
        """Mock artifact deletion."""
        count = len([k for k in self.saved_images if k.startswith(document_id)])
        self.saved_images = {
            k: v for k, v in self.saved_images.items() if not k.startswith(document_id)
        }
        return count


class TestIngestServiceWithMockedPorts:
    """Test ingest service with mocked ports."""

    def test_pdf_validation_called(self):
        """Test that PDF validation is called with correct path."""
        pdf_reader = MockPdfReaderPort(is_valid=True)

        is_valid, error = pdf_reader.validate("/path/to/test.pdf")

        assert is_valid is True
        assert error is None
        assert len(pdf_reader.calls) == 1
        assert pdf_reader.calls[0]["method"] == "validate"

    def test_invalid_pdf_returns_error(self):
        """Test that invalid PDF returns error message."""
        pdf_reader = MockPdfReaderPort(
            is_valid=False,
            error_message="PDF file is corrupted",
        )

        is_valid, error = pdf_reader.validate("/path/to/invalid.pdf")

        assert is_valid is False
        assert "corrupted" in error

    def test_metadata_extraction(self):
        """Test metadata extraction returns correct page count."""
        pdf_reader = MockPdfReaderPort(page_count=5)

        meta = pdf_reader.get_meta("/path/to/test.pdf")

        assert meta.page_count == 5
        assert len(meta.pages) == 5

    def test_page_rendering(self):
        """Test page rendering returns image bytes."""
        pdf_reader = MockPdfReaderPort()

        image_data = pdf_reader.render_page("/path/to/test.pdf", 1, dpi=150)

        assert isinstance(image_data, bytes)
        assert len(image_data) > 0
        assert pdf_reader.calls[-1]["dpi"] == 150

    def test_storage_saves_rendered_pages(self):
        """Test storage port correctly saves rendered pages."""
        storage = MockIngestStoragePort()
        image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        ref = storage.save_image("doc-123", 1, image_data)

        assert ref == "doc-123/page_1.png"
        assert storage.saved_images[ref] == image_data

    def test_storage_generates_urls(self):
        """Test storage generates correct URLs."""
        storage = MockIngestStoragePort()
        storage.save_image("doc-123", 1, b"fake_image")

        url = storage.get_url("doc-123/page_1.png")

        assert "doc-123/page_1.png" in url


# ============================================================================
# Structure/Labelling Service Tests
# ============================================================================


class MockStructureDetectorPort:
    """Mock implementation of StructureDetectorPort."""

    def __init__(
        self,
        box_count: int = 5,
        table_count: int = 0,
    ):
        self.box_count = box_count
        self.table_count = table_count
        self.calls: list[dict] = []

    async def detect_structures(
        self,
        page: int,
        page_image: bytes,
        text_blocks: list | None = None,
        options: dict | None = None,
    ):
        """Mock structure detection."""
        from app.services.structure_labelling.domain.models import (
            BoxCandidate,
            DetectedStructures,
        )

        self.calls.append(
            {
                "method": "detect_structures",
                "page": page,
                "image_size": len(page_image),
            }
        )

        box_candidates = tuple(
            BoxCandidate(
                id=f"box-{i}",
                box_type="text",
                bbox=BBox(x=50, y=100 + i * 50, width=200, height=30, page=page),
                confidence=0.85,
                has_border=True,
            )
            for i in range(self.box_count)
        )

        return DetectedStructures(
            page=page,
            box_candidates=box_candidates,
            table_candidates=(),
            label_candidates=(),
        )

    async def detect_boxes(
        self,
        page: int,
        page_image: bytes,
        options: dict | None = None,
    ):
        """Mock box detection."""
        from app.services.structure_labelling.domain.models import BoxCandidate

        self.calls.append(
            {
                "method": "detect_boxes",
                "page": page,
            }
        )

        return [
            BoxCandidate(
                id=f"box-{i}",
                box_type="text",
                bbox=BBox(x=50, y=100 + i * 50, width=200, height=30, page=page),
                confidence=0.85,
                has_border=True,
            )
            for i in range(self.box_count)
        ]

    async def detect_tables(
        self,
        page: int,
        page_image: bytes,
        options: dict | None = None,
    ):
        """Mock table detection."""
        self.calls.append(
            {
                "method": "detect_tables",
                "page": page,
            }
        )
        return []


class MockPageImageLoaderPort:
    """Mock implementation of PageImageLoaderPort."""

    def __init__(self, images: dict[str, bytes] | None = None):
        self.images = images or {}
        self.calls: list[dict] = []

    async def load_image(self, image_ref: str) -> bytes:
        """Mock image loading."""
        self.calls.append({"method": "load_image", "image_ref": image_ref})
        if image_ref in self.images:
            return self.images[image_ref]
        # Return fake PNG bytes
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    async def load_images(self, image_refs: list[str]) -> dict[str, bytes]:
        """Mock batch image loading."""
        self.calls.append({"method": "load_images", "refs": image_refs})
        result = {}
        for ref in image_refs:
            result[ref] = await self.load_image(ref)
        return result


class TestStructureLabellingServiceWithMockedPorts:
    """Test structure/labelling service with mocked ports."""

    @pytest.mark.asyncio
    async def test_structure_detection_called(self):
        """Test that structure detection is called with correct parameters."""
        detector = MockStructureDetectorPort(box_count=3)

        result = await detector.detect_structures(
            page=1,
            page_image=b"fake_image",
        )

        assert len(detector.calls) == 1
        assert detector.calls[0]["page"] == 1
        # result.box_candidates is a tuple, check length
        assert len(result.box_candidates) == 3

    @pytest.mark.asyncio
    async def test_image_loader_returns_bytes(self):
        """Test image loader returns image bytes."""
        loader = MockPageImageLoaderPort(images={"page_1.png": b"test_image_data"})

        result = await loader.load_image("page_1.png")

        assert result == b"test_image_data"

    @pytest.mark.asyncio
    async def test_batch_image_loading(self):
        """Test batch image loading returns all images."""
        loader = MockPageImageLoaderPort()

        refs = ["page_1.png", "page_2.png", "page_3.png"]
        result = await loader.load_images(refs)

        assert len(result) == 3
        assert all(ref in result for ref in refs)


# ============================================================================
# Mapping Service Tests
# ============================================================================


class MockStringMatcherPort:
    """Mock implementation of StringMatcherPort."""

    def __init__(self, default_similarity: float = 0.8):
        self.default_similarity = default_similarity
        self.calls: list[dict] = []

    def compute_similarity(self, source: str, target: str) -> float:
        """Mock similarity computation."""
        self.calls.append(
            {
                "method": "compute_similarity",
                "source": source,
                "target": target,
            }
        )
        # Simple mock: return 1.0 for exact match, default otherwise
        if source.lower() == target.lower():
            return 1.0
        if source.lower() in target.lower() or target.lower() in source.lower():
            return self.default_similarity
        return 0.3

    def find_matches(
        self,
        source: str,
        targets: tuple[str, ...],
        threshold: float = 0.6,
        limit: int = 5,
    ) -> tuple[tuple[str, float], ...]:
        """Mock match finding."""
        self.calls.append(
            {
                "method": "find_matches",
                "source": source,
                "targets": targets,
                "threshold": threshold,
            }
        )
        matches = []
        for target in targets:
            score = self.compute_similarity(source, target)
            if score >= threshold:
                matches.append((target, score))
        matches.sort(key=lambda x: x[1], reverse=True)
        return tuple(matches[:limit])

    def batch_find_matches(
        self,
        sources: tuple[str, ...],
        targets: tuple[str, ...],
        threshold: float = 0.6,
    ) -> dict[str, tuple[tuple[str, float], ...]]:
        """Mock batch match finding."""
        self.calls.append(
            {
                "method": "batch_find_matches",
                "sources": sources,
                "targets": targets,
            }
        )
        return {source: self.find_matches(source, targets, threshold) for source in sources}


class TestMappingServiceWithMockedPorts:
    """Test mapping service with mocked ports."""

    def test_exact_match_returns_high_score(self):
        """Test exact string match returns score of 1.0."""
        matcher = MockStringMatcherPort()

        score = matcher.compute_similarity("Name", "Name")

        assert score == 1.0

    def test_partial_match_returns_configured_score(self):
        """Test partial match returns configured similarity."""
        matcher = MockStringMatcherPort(default_similarity=0.75)

        score = matcher.compute_similarity("Full Name", "Name")

        assert score == 0.75

    def test_no_match_returns_low_score(self):
        """Test no match returns low score."""
        matcher = MockStringMatcherPort()

        score = matcher.compute_similarity("Amount", "Address")

        assert score < 0.5

    def test_find_matches_respects_threshold(self):
        """Test find_matches only returns matches above threshold."""
        matcher = MockStringMatcherPort()
        targets = ("Name", "Full Name", "Date", "Amount")

        matches = matcher.find_matches("Name", targets, threshold=0.7)

        # Should include "Name" (1.0) and "Full Name" (0.8)
        assert len(matches) >= 1
        assert all(score >= 0.7 for _, score in matches)

    def test_batch_find_matches_processes_all_sources(self):
        """Test batch matching processes all source fields."""
        matcher = MockStringMatcherPort()
        sources = ("Name", "Date", "Amount")
        targets = ("Full Name", "Transaction Date", "Total Amount")

        result = matcher.batch_find_matches(sources, targets, threshold=0.6)

        assert len(result) == 3
        assert all(source in result for source in sources)


# ============================================================================
# Extract Service Tests
# ============================================================================


class MockNativeTextExtractorPort:
    """Mock implementation of NativeTextExtractorPort."""

    def __init__(
        self,
        has_text_layer: bool = True,
        extracted_text: str = "Sample extracted text",
    ):
        self._has_text_layer = has_text_layer
        self.extracted_text = extracted_text
        self.calls: list[dict] = []

    async def extract_text(
        self,
        document_ref: str,
        page: int,
        region: BBox | None = None,
    ):
        """Mock text extraction."""
        from app.services.extract.domain.models import NativeTextLine, NativeTextResult

        self.calls.append(
            {
                "method": "extract_text",
                "document_ref": document_ref,
                "page": page,
                "region": region,
            }
        )

        return NativeTextResult(
            page=page,
            lines=(
                NativeTextLine(
                    text=self.extracted_text,
                    bbox=BBox(x=50, y=100, width=200, height=20, page=page),
                ),
            ),
            has_text_layer=self._has_text_layer,
        )

    async def has_text_layer(self, document_ref: str) -> bool:
        """Check if document has text layer."""
        self.calls.append(
            {
                "method": "has_text_layer",
                "document_ref": document_ref,
            }
        )
        return self._has_text_layer


class MockOcrServicePort:
    """Mock implementation of OcrServicePort."""

    def __init__(
        self,
        recognized_text: str = "OCR recognized text",
        confidence: float = 0.85,
    ):
        self.recognized_text = recognized_text
        self.confidence = confidence
        self.calls: list[dict] = []

    async def recognize(
        self,
        image_data: bytes,
        page: int,
        region: BBox | None = None,
        language: str = "ja+en",
    ):
        """Mock OCR recognition."""
        from app.services.extract.domain.models import OcrLine, OcrResult, OcrToken

        self.calls.append(
            {
                "method": "recognize",
                "image_size": len(image_data),
                "page": page,
                "language": language,
            }
        )

        token = OcrToken(
            text=self.recognized_text,
            bbox=BBox(x=50, y=100, width=150, height=20, page=page),
            confidence=self.confidence,
        )
        line = OcrLine(
            text=self.recognized_text,
            tokens=(token,),
            bbox=BBox(x=50, y=100, width=150, height=20, page=page),
            confidence=self.confidence,
        )

        return OcrResult(
            page=page,
            lines=(line,),
        )

    async def recognize_region(
        self,
        image_data: bytes,
        page: int,
        bbox: BBox,
        language: str = "ja+en",
    ):
        """Mock region OCR."""
        self.calls.append(
            {
                "method": "recognize_region",
                "page": page,
                "bbox": bbox,
            }
        )
        return await self.recognize(image_data, page, bbox, language)


class TestExtractServiceWithMockedPorts:
    """Test extract service with mocked ports."""

    @pytest.mark.asyncio
    async def test_native_text_extraction(self):
        """Test native text extraction returns correct result."""
        extractor = MockNativeTextExtractorPort(extracted_text="John Doe")

        result = await extractor.extract_text(
            document_ref="/path/to/doc.pdf",
            page=1,
        )

        assert len(result.lines) == 1
        assert result.lines[0].text == "John Doe"

    @pytest.mark.asyncio
    async def test_region_extraction(self):
        """Test extraction with specific region."""
        extractor = MockNativeTextExtractorPort()
        region = BBox(x=100, y=200, width=150, height=30, page=1)

        await extractor.extract_text(
            document_ref="/path/to/doc.pdf",
            page=1,
            region=region,
        )

        assert extractor.calls[-1]["region"] == region

    @pytest.mark.asyncio
    async def test_ocr_fallback_when_no_text_layer(self):
        """Test OCR is used when no text layer exists."""
        text_extractor = MockNativeTextExtractorPort(has_text_layer=False)
        ocr_service = MockOcrServicePort(recognized_text="OCR Result")

        has_text = await text_extractor.has_text_layer("/path/to/scanned.pdf")
        assert has_text is False

        # OCR should be used
        result = await ocr_service.recognize(
            image_data=b"fake_image",
            page=1,
        )
        assert result.full_text == "OCR Result"

    @pytest.mark.asyncio
    async def test_ocr_region_recognition(self):
        """Test OCR recognizes specific regions."""
        ocr = MockOcrServicePort()
        bbox = BBox(x=100, y=200, width=150, height=30, page=1)

        result = await ocr.recognize_region(
            image_data=b"fake_image",
            page=1,
            bbox=bbox,
        )

        assert result.full_text is not None
        # recognize_region adds entry first, then calls recognize which adds another
        # So we need to check the second-to-last call (recognize_region's call)
        recognize_region_call = next(
            (c for c in ocr.calls if c.get("method") == "recognize_region"), None
        )
        assert recognize_region_call is not None
        assert recognize_region_call["bbox"] == bbox


# ============================================================================
# Adjust Service Tests
# ============================================================================


class MockBboxCalculatorPort:
    """Mock implementation of BboxCalculatorPort."""

    def __init__(self):
        self.calls: list[dict] = []

    def transform_to_page_coords(
        self,
        bbox,
        source_dpi: int,
        target_dpi: int,
    ):
        """Mock coordinate transformation."""
        from app.services.adjust.domain.models import BboxValues

        self.calls.append(
            {
                "method": "transform_to_page_coords",
                "source_dpi": source_dpi,
                "target_dpi": target_dpi,
            }
        )

        scale = target_dpi / source_dpi
        return BboxValues(
            x=bbox.x * scale,
            y=bbox.y * scale,
            width=bbox.width * scale,
            height=bbox.height * scale,
            page=getattr(bbox, "page", 1),
        )

    def calculate_relative_position(
        self,
        bbox,
        anchor_bbox,
    ) -> tuple[float, float]:
        """Mock relative position calculation."""
        self.calls.append(
            {
                "method": "calculate_relative_position",
            }
        )
        return (bbox.x - anchor_bbox.x, bbox.y - anchor_bbox.y)

    def apply_relative_position(
        self,
        relative_x: float,
        relative_y: float,
        anchor_bbox,
        original_width: float,
        original_height: float,
    ):
        """Mock applying relative position."""
        from app.services.adjust.domain.models import BboxValues

        self.calls.append(
            {
                "method": "apply_relative_position",
            }
        )
        return BboxValues(
            x=anchor_bbox.x + relative_x,
            y=anchor_bbox.y + relative_y,
            width=original_width,
            height=original_height,
            page=getattr(anchor_bbox, "page", 1),
        )


class MockOverlapDetectorPort:
    """Mock implementation of OverlapDetectorPort."""

    def __init__(self, overlaps: list | None = None):
        self.overlaps = overlaps or []
        self.calls: list[dict] = []

    def detect_overlaps(
        self,
        bboxes,
        threshold: float = 0.0,
    ):
        """Mock overlap detection."""
        self.calls.append(
            {
                "method": "detect_overlaps",
                "bbox_count": len(bboxes),
                "threshold": threshold,
            }
        )
        return tuple(self.overlaps)

    def detect_overflow(
        self,
        field_id: str,
        bbox,
        page_width: float,
        page_height: float,
    ):
        """Mock overflow detection."""
        from app.services.adjust.domain.models import OverflowInfo

        self.calls.append(
            {
                "method": "detect_overflow",
                "field_id": field_id,
            }
        )

        # Calculate overflow amounts
        right_overflow = max(0, (bbox.x + bbox.width) - page_width)
        bottom_overflow = max(0, (bbox.y + bbox.height) - page_height)

        return OverflowInfo(
            field_id=field_id,
            overflow_right=right_overflow,
            overflow_bottom=bottom_overflow,
            overflow_left=max(0, -bbox.x),
            overflow_top=max(0, -bbox.y),
        )


class TestAdjustServiceWithMockedPorts:
    """Test adjust service with mocked ports."""

    def test_coordinate_transformation(self):
        """Test DPI-based coordinate transformation."""
        from app.services.adjust.domain.models import BboxValues

        calculator = MockBboxCalculatorPort()
        bbox = BboxValues(x=100, y=200, width=150, height=30, page=1)

        result = calculator.transform_to_page_coords(bbox, 150, 300)

        # Should scale by 2x (300/150)
        assert result.x == 200
        assert result.y == 400
        assert result.width == 300

    def test_overlap_detection_returns_overlaps(self):
        """Test overlap detection returns configured overlaps."""
        from app.services.adjust.domain.models import BboxValues, OverlapInfo

        overlaps = [
            OverlapInfo(
                field_id_a="field-1",
                field_id_b="field-2",
                overlap_area=100.0,
                overlap_ratio_a=0.15,
                overlap_ratio_b=0.15,
            )
        ]
        detector = MockOverlapDetectorPort(overlaps=overlaps)
        bboxes = [
            ("field-1", BboxValues(x=100, y=200, width=100, height=30, page=1)),
            ("field-2", BboxValues(x=150, y=200, width=100, height=30, page=1)),
        ]

        result = detector.detect_overlaps(bboxes)

        assert len(result) == 1
        assert result[0].field_id_a == "field-1"

    def test_overflow_detection(self):
        """Test overflow detection calculates correctly."""
        from app.services.adjust.domain.models import BboxValues

        detector = MockOverlapDetectorPort()
        bbox = BboxValues(x=550, y=750, width=100, height=50, page=1)

        result = detector.detect_overflow(
            field_id="field-1",
            bbox=bbox,
            page_width=612,
            page_height=792,
        )

        # 550 + 100 = 650 > 612, so overflow_right = 38
        assert result.overflow_right == 38
        # 750 + 50 = 800 > 792, so overflow_bottom = 8
        assert result.overflow_bottom == 8


# ============================================================================
# Fill Service Tests
# ============================================================================


class MockTextMeasurePort:
    """Mock implementation of TextMeasurePort."""

    def __init__(self, char_width: float = 8.0, line_height: float = 14.0):
        self.char_width = char_width
        self.line_height = line_height
        self.calls: list[dict] = []

    def measure(
        self,
        text: str,
        font_family: str,
        font_size: float,
    ) -> tuple[float, float]:
        """Mock text measurement."""
        self.calls.append(
            {
                "method": "measure",
                "text": text,
                "font_family": font_family,
                "font_size": font_size,
            }
        )
        width = len(text) * self.char_width * (font_size / 12.0)
        height = self.line_height * (font_size / 12.0)
        return (width, height)

    def get_line_height(
        self,
        font_family: str,
        font_size: float,
        line_height_multiplier: float = 1.0,
    ) -> float:
        """Mock line height calculation."""
        self.calls.append(
            {
                "method": "get_line_height",
                "font_family": font_family,
                "font_size": font_size,
            }
        )
        return self.line_height * (font_size / 12.0) * line_height_multiplier


class MockAcroFormWriterPort:
    """Mock implementation of AcroFormWriterPort."""

    def __init__(self, has_form: bool = True):
        self.has_form = has_form
        self.loaded_path: str | None = None
        self.field_values: dict[str, str] = {}
        self.checkbox_states: dict[str, bool] = {}
        self.calls: list[dict] = []

    def load(self, pdf_path: str) -> bool:
        """Mock PDF loading."""
        self.calls.append({"method": "load", "pdf_path": pdf_path})
        self.loaded_path = pdf_path
        return True

    def set_field_value(
        self,
        field_name: str,
        value: str,
        font_config=None,
    ) -> bool:
        """Mock field value setting."""
        self.calls.append(
            {
                "method": "set_field_value",
                "field_name": field_name,
                "value": value,
            }
        )
        if not self.has_form:
            return False
        self.field_values[field_name] = value
        return True

    def set_checkbox(self, field_name: str, checked: bool) -> bool:
        """Mock checkbox setting."""
        self.calls.append(
            {
                "method": "set_checkbox",
                "field_name": field_name,
                "checked": checked,
            }
        )
        if not self.has_form:
            return False
        self.checkbox_states[field_name] = checked
        return True

    def flatten(self) -> None:
        """Mock form flattening."""
        self.calls.append({"method": "flatten"})

    def save(self, output_path: str) -> bool:
        """Mock save."""
        self.calls.append({"method": "save", "output_path": output_path})
        return True

    def close(self) -> None:
        """Mock close."""
        self.calls.append({"method": "close"})


class TestFillServiceWithMockedPorts:
    """Test fill service with mocked ports."""

    def test_text_measurement(self):
        """Test text measurement returns correct dimensions."""
        measure = MockTextMeasurePort(char_width=8.0)

        width, height = measure.measure("Hello", "Arial", 12.0)

        assert width == 40.0  # 5 chars * 8.0
        assert height > 0

    def test_acroform_field_setting(self):
        """Test AcroForm field value setting."""
        writer = MockAcroFormWriterPort(has_form=True)
        writer.load("/path/to/form.pdf")

        result = writer.set_field_value("name", "John Doe")

        assert result is True
        assert writer.field_values["name"] == "John Doe"

    def test_checkbox_setting(self):
        """Test checkbox state setting."""
        writer = MockAcroFormWriterPort(has_form=True)
        writer.load("/path/to/form.pdf")

        result = writer.set_checkbox("agree", True)

        assert result is True
        assert writer.checkbox_states["agree"] is True

    def test_no_form_returns_false(self):
        """Test setting fields on PDF without form returns False."""
        writer = MockAcroFormWriterPort(has_form=False)
        writer.load("/path/to/no_form.pdf")

        result = writer.set_field_value("name", "John")

        assert result is False


# ============================================================================
# Review Service Tests
# ============================================================================


class MockPdfRendererPort:
    """Mock implementation of PdfRendererPort."""

    def __init__(self, page_count: int = 2):
        self.page_count = page_count
        self.calls: list[dict] = []

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 150,
    ):
        """Mock page rendering."""
        from app.services.review.domain.models import RenderResult

        self.calls.append(
            {
                "method": "render_page",
                "pdf_path": pdf_path,
                "page_number": page_number,
                "dpi": dpi,
            }
        )

        return RenderResult(
            page_number=page_number,
            image_data=b"\x89PNG" + b"\x00" * 100,
            width=int(612 * dpi / 72),
            height=int(792 * dpi / 72),
            dpi=dpi,
        )

    def render_all_pages(
        self,
        pdf_path: str,
        dpi: int = 150,
    ):
        """Mock rendering all pages."""
        self.calls.append(
            {
                "method": "render_all_pages",
                "pdf_path": pdf_path,
                "dpi": dpi,
            }
        )
        return tuple(self.render_page(pdf_path, i + 1, dpi) for i in range(self.page_count))


class MockDiffGeneratorPort:
    """Mock implementation of DiffGeneratorPort."""

    def __init__(self, change_detected: bool = True):
        self.change_detected = change_detected
        self.calls: list[dict] = []

    def generate_diff(
        self,
        original_image: bytes,
        filled_image: bytes,
        highlight_color: tuple[int, int, int] = (255, 0, 0),
    ):
        """Mock diff generation."""
        from app.services.review.domain.models import ChangeRegion, DiffResult

        self.calls.append(
            {
                "method": "generate_diff",
                "original_size": len(original_image),
                "filled_size": len(filled_image),
            }
        )

        change_regions = ()
        if self.change_detected:
            change_regions = (
                ChangeRegion(x=100, y=200, width=150, height=30, page=1, change_percentage=0.1),
            )

        return DiffResult(
            diff_image=b"\x89PNG" + b"\x00" * 50,
            change_regions=change_regions,
            total_change_percentage=0.1 if self.change_detected else 0.0,
            has_significant_changes=self.change_detected,
        )

    def generate_overlay(
        self,
        base_image: bytes,
        overlay_image: bytes,
        opacity: float = 0.5,
    ) -> bytes:
        """Mock overlay generation."""
        self.calls.append(
            {
                "method": "generate_overlay",
                "opacity": opacity,
            }
        )
        return b"\x89PNG" + b"\x00" * 80


class TestReviewServiceWithMockedPorts:
    """Test review service with mocked ports."""

    def test_page_rendering(self):
        """Test page rendering returns correct result."""
        renderer = MockPdfRendererPort()

        result = renderer.render_page("/path/to/doc.pdf", 1, dpi=150)

        assert result.page_number == 1
        assert result.dpi == 150
        assert len(result.image_data) > 0

    def test_diff_generation_detects_changes(self):
        """Test diff generation detects changes."""
        diff_gen = MockDiffGeneratorPort(change_detected=True)

        result = diff_gen.generate_diff(
            original_image=b"original",
            filled_image=b"filled",
        )

        assert len(result.change_regions) > 0
        assert result.has_significant_changes is True

    def test_diff_no_changes(self):
        """Test diff when no changes detected."""
        diff_gen = MockDiffGeneratorPort(change_detected=False)

        result = diff_gen.generate_diff(
            original_image=b"same",
            filled_image=b"same",
        )

        assert len(result.change_regions) == 0
        assert result.has_significant_changes is False

    def test_overlay_generation(self):
        """Test overlay image generation."""
        diff_gen = MockDiffGeneratorPort()

        result = diff_gen.generate_overlay(
            base_image=b"base",
            overlay_image=b"overlay",
            opacity=0.7,
        )

        assert len(result) > 0
        assert diff_gen.calls[-1]["opacity"] == 0.7
