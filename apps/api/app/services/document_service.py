"""Document service for handling document operations."""

import io
from pathlib import Path
from uuid import uuid4

from app.infrastructure.observability import get_logger
from app.models import Document, DocumentMeta, DocumentResponse, DocumentType
from app.models.acroform import (
    AcroFormFieldInfo,
    AcroFormFieldsResponse,
    PageDimensions,
)
from app.models.common import BBox
from app.repositories import DocumentRepository, FileRepository
from app.infrastructure.repositories import (
    get_document_repository,
    get_file_repository,
)

logger = get_logger("document_service")


class DocumentService:
    """Service for document operations."""

    def __init__(
        self,
        document_repository: DocumentRepository | None = None,
        file_repository: FileRepository | None = None,
    ) -> None:
        self._document_repository = document_repository or get_document_repository()
        self._file_repository = file_repository or get_file_repository()

    async def upload_document(
        self,
        content: bytes,
        filename: str,
        document_type: DocumentType,
    ) -> DocumentResponse:
        """Upload and process a document."""
        # Generate unique ID for the file
        file_id = str(uuid4())

        logger.info(
            "Processing document upload",
            file_id=file_id,
            filename=filename,
            document_type=document_type.value,
            content_size_bytes=len(content),
        )

        # Store the file
        file_path = self._file_repository.store(file_id, content, filename)

        # Extract metadata (mock for MVP - would use PDF library in production)
        meta = self._extract_metadata(content, filename)

        logger.info(
            "Document metadata extracted",
            file_id=file_id,
            filename=filename,
            page_count=meta.page_count,
            mime_type=meta.mime_type,
            has_password=meta.has_password,
        )

        # Create document record
        document = self._document_repository.create(
            document_type=document_type,
            meta=meta,
            ref=str(file_path),
        )

        logger.debug(
            "Document record created",
            document_id=document.id,
            document_type=document_type.value,
        )

        # Generate page previews (mock for MVP)
        await self._generate_previews(document.id, content, meta.page_count)

        logger.info(
            "Document upload completed",
            document_id=document.id,
            filename=filename,
            document_type=document_type.value,
            page_count=meta.page_count,
            file_size_bytes=meta.file_size,
        )

        return DocumentResponse(
            document_id=document.id,
            document_ref=document.ref,
            meta=meta,
        )

    def get_document(self, document_id: str) -> Document | None:
        """Get a document by ID."""
        return self._document_repository.get(document_id)

    def get_preview_path(self, document_id: str, page: int) -> str | None:
        """Get the path to a page preview image."""
        document = self._document_repository.get(document_id)
        if document is None:
            return None
        if page < 1 or page > document.meta.page_count:
            return None
        return self._file_repository.get_preview_path(document_id, page)

    def get_preview_content(self, document_id: str, page: int) -> bytes | None:
        """Get the content of a page preview image."""
        document = self._document_repository.get(document_id)
        if document is None:
            return None
        if page < 1 or page > document.meta.page_count:
            return None
        return self._file_repository.get_preview_content(document_id, page)

    def get_acroform_fields(self, document_id: str) -> AcroFormFieldsResponse | None:
        """Extract AcroForm fields with screen-coordinate bboxes.

        Extracts AcroForm field information from a PDF document,
        transforming PDF coordinates (bottom-left origin) to screen
        coordinates (top-left origin) for overlay rendering.

        Args:
            document_id: The ID of the document to extract fields from.

        Returns:
            AcroFormFieldsResponse with field info and page dimensions,
            or None if document not found.
        """
        logger.debug(
            "Starting AcroForm extraction",
            document_id=document_id,
        )

        document = self._document_repository.get(document_id)
        if document is None:
            logger.debug(
                "Document not found for AcroForm extraction",
                document_id=document_id,
            )
            return None

        # Get the PDF content
        pdf_content = self._file_repository.get_content(document.ref)
        if pdf_content is None:
            logger.warning(
                "PDF content not found for AcroForm extraction",
                document_id=document_id,
                document_ref=document.ref,
            )
            return AcroFormFieldsResponse(
                has_acroform=False,
                page_dimensions=[],
                fields=[],
                preview_scale=2,
            )

        try:
            import fitz  # PyMuPDF

            logger.debug(
                "Opening PDF for AcroForm extraction",
                document_id=document_id,
                pdf_size_bytes=len(pdf_content),
            )

            doc = fitz.open(stream=pdf_content, filetype="pdf")

            # Extract page dimensions
            page_dimensions: list[PageDimensions] = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                rect = page.rect
                page_dimensions.append(
                    PageDimensions(
                        page=page_num + 1,
                        width=rect.width,
                        height=rect.height,
                    )
                )

            # Check if PDF has AcroForm
            # In PyMuPDF, we can check for form fields
            fields: list[AcroFormFieldInfo] = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_height = page.rect.height

                # Get form field widgets on this page
                for widget in page.widgets():
                    if widget is None:
                        continue

                    # Get field properties
                    field_name = widget.field_name or ""
                    field_type = self._get_widget_type_name(widget.field_type)
                    field_value = widget.field_value or ""
                    readonly = bool(widget.field_flags & 1)  # ReadOnly flag

                    # Get widget rectangle (PDF coordinates: bottom-left origin)
                    rect = widget.rect

                    # Transform to screen coordinates (top-left origin)
                    # PDF y-axis is inverted
                    pdf_y = rect.y0  # Top of the widget in PDF coords
                    screen_y = pdf_y  # Already correct for top-left origin in PyMuPDF

                    bbox = BBox(
                        x=rect.x0,
                        y=screen_y,
                        width=rect.width,
                        height=rect.height,
                        page=page_num + 1,
                    )

                    fields.append(
                        AcroFormFieldInfo(
                            field_name=field_name,
                            field_type=field_type,
                            value=field_value,
                            readonly=readonly,
                            bbox=bbox,
                        )
                    )

            doc.close()

            has_acroform = len(fields) > 0

            # Log extraction summary
            field_types_count: dict[str, int] = {}
            for field in fields:
                field_types_count[field.field_type] = (
                    field_types_count.get(field.field_type, 0) + 1
                )

            logger.info(
                "AcroForm extraction completed",
                document_id=document_id,
                has_acroform=has_acroform,
                total_fields=len(fields),
                page_count=len(page_dimensions),
                field_types=field_types_count,
                readonly_fields=sum(1 for f in fields if f.readonly),
                fields_with_value=sum(1 for f in fields if f.value),
            )

            return AcroFormFieldsResponse(
                has_acroform=has_acroform,
                page_dimensions=page_dimensions,
                fields=fields,
                preview_scale=2,
            )

        except ImportError:
            # PyMuPDF not available
            logger.error(
                "PyMuPDF not available for AcroForm extraction",
                document_id=document_id,
            )
            return AcroFormFieldsResponse(
                has_acroform=False,
                page_dimensions=[],
                fields=[],
                preview_scale=2,
            )
        except Exception as e:
            # Failed to extract fields
            logger.exception(
                "Failed to extract AcroForm fields",
                document_id=document_id,
                error=str(e),
            )
            return AcroFormFieldsResponse(
                has_acroform=False,
                page_dimensions=[],
                fields=[],
                preview_scale=2,
            )

    def extract_text_blocks(self, document_id: str) -> list[dict]:
        """Extract text blocks from a PDF document.

        Extracts native text blocks (not OCR) from the PDF, which can be used
        as label candidates for structure labelling.

        Args:
            document_id: The ID of the document to extract text from.

        Returns:
            List of text block dictionaries with id, text, page, bbox, font_name, font_size.
        """
        logger.debug(
            "Starting text block extraction",
            document_id=document_id,
        )

        document = self._document_repository.get(document_id)
        if document is None:
            logger.debug(
                "Document not found for text extraction",
                document_id=document_id,
            )
            return []

        # Get the PDF content
        pdf_content = self._file_repository.get_content(document.ref)
        if pdf_content is None:
            logger.warning(
                "PDF content not found for text extraction",
                document_id=document_id,
                document_ref=document.ref,
            )
            return []

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text_blocks: list[dict] = []
            block_counter = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_number = page_num + 1  # 1-indexed

                # Extract text blocks with position information
                # "dict" format gives us blocks with bbox and font info
                blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

                for block in blocks.get("blocks", []):
                    # Skip image blocks
                    if block.get("type") != 0:  # type 0 = text
                        continue

                    # Each block contains lines, each line contains spans
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if not text:
                                continue

                            # Get bounding box
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            x, y = bbox[0], bbox[1]
                            width = bbox[2] - bbox[0]
                            height = bbox[3] - bbox[1]

                            # Skip very small or likely decorative text
                            if width < 2 or height < 2:
                                continue

                            block_counter += 1
                            text_blocks.append({
                                "id": f"tb_{page_number}_{block_counter}",
                                "text": text,
                                "page": page_number,
                                "bbox": [x, y, width, height],
                                "font_name": span.get("font", None),
                                "font_size": span.get("size", None),
                            })

            page_count = len(doc)
            doc.close()

            logger.info(
                "Text block extraction completed",
                document_id=document_id,
                total_blocks=len(text_blocks),
                page_count=page_count,
            )

            return text_blocks

        except ImportError:
            logger.error(
                "PyMuPDF not available for text extraction",
                document_id=document_id,
            )
            return []
        except Exception as e:
            logger.exception(
                "Failed to extract text blocks",
                document_id=document_id,
                error=str(e),
            )
            return []

    def _get_widget_type_name(self, field_type: int) -> str:
        """Convert PyMuPDF widget field type to string name.

        Args:
            field_type: PyMuPDF field type constant.

        Returns:
            Human-readable field type name.
        """
        # PyMuPDF field type constants (fitz.PDF_WIDGET_TYPE_*)
        type_map = {
            0: "unknown",        # PDF_WIDGET_TYPE_UNKNOWN
            1: "button",         # PDF_WIDGET_TYPE_BUTTON
            2: "checkbox",       # PDF_WIDGET_TYPE_CHECKBOX
            3: "combobox",       # PDF_WIDGET_TYPE_COMBOBOX
            4: "listbox",        # PDF_WIDGET_TYPE_LISTBOX
            5: "radio",          # PDF_WIDGET_TYPE_RADIOBUTTON
            6: "signature",      # PDF_WIDGET_TYPE_SIGNATURE
            7: "text",           # PDF_WIDGET_TYPE_TEXT
        }
        return type_map.get(field_type, "unknown")

    def _extract_metadata(self, content: bytes, filename: str) -> DocumentMeta:
        """Extract metadata from a PDF or image document using PyMuPDF."""
        # Detect file type by signature
        is_pdf = content[:4] == b"%PDF"
        is_png = content[:8] == b"\x89PNG\r\n\x1a\n"
        is_jpeg = content[:3] == b"\xff\xd8\xff"
        is_tiff = content[:4] == b"II*\x00" or content[:4] == b"MM\x00*"
        is_webp = len(content) >= 12 and content[0:4] == b"RIFF" and content[8:12] == b"WEBP"

        # Determine MIME type, page count, and AcroForm presence
        has_acroform = False
        if is_pdf:
            mime_type = "application/pdf"
            # Use PyMuPDF to get actual page count and detect AcroForm
            try:
                import fitz
                doc = fitz.open(stream=content, filetype="pdf")
                page_count = len(doc)
                # Check for AcroForm fields (widgets) on any page
                for page in doc:
                    widgets = list(page.widgets())
                    if widgets:
                        has_acroform = True
                        break
                doc.close()
            except Exception:
                # Fallback to estimate if PyMuPDF fails
                page_count = max(1, len(content) // (50 * 1024))
        elif is_png:
            mime_type = "image/png"
            page_count = 1  # Images are single page
        elif is_jpeg:
            mime_type = "image/jpeg"
            page_count = 1
        elif is_tiff:
            mime_type = "image/tiff"
            page_count = 1  # Would need to parse TIFF for actual page count
        elif is_webp:
            mime_type = "image/webp"
            page_count = 1
        else:
            mime_type = "application/octet-stream"
            page_count = 1

        return DocumentMeta(
            page_count=page_count,
            file_size=len(content),
            mime_type=mime_type,
            filename=filename,
            has_password=False,  # Images don't have passwords
            has_acroform=has_acroform,
        )

    async def _generate_previews(
        self,
        document_id: str,
        content: bytes,
        page_count: int,
    ) -> None:
        """Generate preview images for document pages using PyMuPDF."""
        try:
            import fitz  # PyMuPDF

            # Open the PDF from bytes
            doc = fitz.open(stream=content, filetype="pdf")

            for page_num in range(min(page_count, len(doc))):
                page = doc[page_num]

                # Render page to image (2x zoom for better quality)
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PNG bytes
                png_bytes = pix.tobytes("png")

                # Store the preview (page numbers are 1-indexed)
                stored_path = self._file_repository.store_preview(
                    document_id, page_num + 1, png_bytes
                )

                if not stored_path:
                    raise IOError(f"Failed to store preview for page {page_num + 1}")

            doc.close()

        except ImportError:
            # Fallback to placeholder if PyMuPDF not available
            placeholder_png = self._create_placeholder_png()
            for page in range(1, page_count + 1):
                self._file_repository.store_preview(document_id, page, placeholder_png)
        except Exception as e:
            # On any error, generate placeholder
            placeholder_png = self._create_placeholder_png()
            for page in range(1, page_count + 1):
                self._file_repository.store_preview(document_id, page, placeholder_png)
            raise ValueError(f"Failed to generate PDF previews: {e}")

    def _create_placeholder_png(self) -> bytes:
        """Create a visible placeholder PNG image.

        Creates an 800x600 pixel image with a light gray background
        and placeholder text. This is a temporary implementation.
        Production would render actual PDF pages.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create an 800x600 image with light gray background
            width, height = 800, 600
            img = Image.new("RGB", (width, height), color="#f3f4f6")
            draw = ImageDraw.Draw(img)

            # Draw a border
            draw.rectangle([0, 0, width - 1, height - 1], outline="#d1d5db", width=2)

            # Try to use a default font, fallback to basic if not available
            try:
                # Try to use a system font
                font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            except (OSError, IOError):
                try:
                    # Try alternative font paths
                    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
                    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                except (OSError, IOError):
                    # Fallback to default font
                    font_large = ImageFont.load_default()
                    font_small = ImageFont.load_default()

            # Draw placeholder text
            text = "Document Preview"
            subtext = "Placeholder - Preview generation pending"
            
            # Get text dimensions for centering
            bbox = draw.textbbox((0, 0), text, font=font_large)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            bbox_sub = draw.textbbox((0, 0), subtext, font=font_small)
            subtext_width = bbox_sub[2] - bbox_sub[0]
            
            # Center the text
            x = (width - text_width) // 2
            y = (height - text_height) // 2 - 30
            x_sub = (width - subtext_width) // 2
            y_sub = y + text_height + 20

            # Draw text with shadow effect
            draw.text((x + 2, y + 2), text, fill="#9ca3af", font=font_large)
            draw.text((x, y), text, fill="#374151", font=font_large)
            
            draw.text((x_sub + 1, y_sub + 1), subtext, fill="#d1d5db", font=font_small)
            draw.text((x_sub, y_sub), subtext, fill="#6b7280", font=font_small)

            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            png_bytes = buffer.getvalue()
            
            if not png_bytes or len(png_bytes) == 0:
                raise ValueError("Generated PNG is empty")
            
            return png_bytes

        except ImportError:
            # PIL not available, fallback to minimal PNG
            import warnings
            warnings.warn("PIL not available, using minimal 1x1 placeholder")
            # Fallback to minimal PNG if PIL is not available
            # Minimal 1x1 white PNG
            return bytes([
                0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
                0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
                0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
                0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
                0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
                0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
                0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
                0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
                0x44, 0xAE, 0x42, 0x60, 0x82,
            ])
