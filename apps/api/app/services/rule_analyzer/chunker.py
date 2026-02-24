"""Text chunker for splitting rule documents before LLM analysis.

Splits documents on paragraph boundaries with configurable max chunk size
and overlap for context continuity.
"""

DEFAULT_MAX_CHUNK_CHARS = 3000
DEFAULT_OVERLAP_CHARS = 200


def chunk_document(
    text: str,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split a document into chunks on paragraph boundaries.

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

    # If the text fits in one chunk, return as-is
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Adding this paragraph (plus separator) would exceed max
        added_len = len(para) + (2 if current_parts else 0)
        if current_parts and current_len + added_len > max_chars:
            # Flush current chunk
            chunk_text = "\n\n".join(current_parts)
            chunks.append(chunk_text)

            # Build overlap from the tail of the current chunk
            overlap_text = chunk_text[-overlap:] if overlap > 0 else ""
            if overlap_text:
                current_parts = [overlap_text]
                current_len = len(overlap_text)
            else:
                current_parts = []
                current_len = 0

        current_parts.append(para)
        current_len += added_len if current_parts else len(para)

    # Flush remaining
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        chunks.append(chunk_text)

    return chunks
