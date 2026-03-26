"""Document chunker for splitting rule documents before LLM analysis.

Uses Docling for layout-aware parsing (preserves headings, tables, sections)
when available. Falls back to simple paragraph-based splitting.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHUNK_CHARS = 6000
DEFAULT_OVERLAP_CHARS = 200


def chunk_document(
    text: str,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split a document text into chunks on paragraph boundaries.

    For pre-extracted text (strings). Uses simple paragraph splitting.

    Args:
        text: The document text to split.
        max_chars: Maximum characters per chunk.
        overlap: Number of overlap characters between chunks.

    Returns:
        List of text chunks. Empty list if text is empty/whitespace.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    if len(text) <= max_chars:
        return [text]

    return _split_paragraphs(text, max_chars, overlap)


def chunk_document_file(
    file_path: str | Path,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Parse and chunk a document file using Docling.

    Docling provides layout-aware parsing with heading detection,
    table structure, and section hierarchy — producing cleaner chunks
    than raw text splitting.

    Falls back to simple text extraction + paragraph splitting
    if Docling is not installed.

    Args:
        file_path: Path to the document (PDF, DOCX, HTML, etc.).
        max_chars: Maximum characters per chunk.
        overlap: Number of overlap characters between chunks.

    Returns:
        List of text chunks with section context.
    """
    file_path = Path(file_path)

    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        markdown = result.document.export_to_markdown()

        if not markdown or not markdown.strip():
            return []

        return _split_by_headings(markdown, max_chars, overlap)

    except ImportError:
        logger.info("Docling not installed, falling back to text extraction")
        return _fallback_extract_and_chunk(file_path, max_chars, overlap)
    except Exception as e:
        logger.warning(f"Docling parsing failed for {file_path}: {e}")
        return _fallback_extract_and_chunk(file_path, max_chars, overlap)


def _split_by_headings(
    markdown: str,
    max_chars: int,
    overlap: int,
) -> list[str]:
    """Split Docling-produced markdown by heading boundaries.

    Keeps heading context with each chunk so the LLM knows
    which section a rule belongs to.
    """
    lines = markdown.split("\n")
    sections: list[str] = []
    current_section: list[str] = []
    for line in lines:
        if line.startswith("#"):
            if current_section:
                sections.append("\n".join(current_section))
            current_section = [line]
        else:
            current_section.append(line)

    if current_section:
        sections.append("\n".join(current_section))

    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
        else:
            sub_chunks = _split_paragraphs(section, max_chars, overlap)
            chunks.extend(sub_chunks)

    return chunks


def _split_paragraphs(
    text: str,
    max_chars: int,
    overlap: int,
) -> list[str]:
    """Split text into chunks on paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        added_len = len(para) + (2 if current_parts else 0)
        if current_parts and current_len + added_len > max_chars:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(chunk_text)

            overlap_text = chunk_text[-overlap:] if overlap > 0 else ""
            if overlap_text:
                current_parts = [overlap_text]
                current_len = len(overlap_text)
            else:
                current_parts = []
                current_len = 0

        current_parts.append(para)
        current_len += added_len if current_parts else len(para)

    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        chunks.append(chunk_text)

    return chunks


def _fallback_extract_and_chunk(
    file_path: Path,
    max_chars: int,
    overlap: int,
) -> list[str]:
    """Extract text with PyMuPDF and chunk by paragraphs."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        text_parts = [page.get_text() for page in doc]
        doc.close()
        text = "\n\n".join(text_parts).strip()

        if not text:
            return []
        return _split_paragraphs(text, max_chars, overlap)

    except Exception as e:
        logger.warning(f"Fallback text extraction failed for {file_path}: {e}")
        return []
