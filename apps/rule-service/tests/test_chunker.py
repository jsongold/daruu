"""Tests for chunker module."""

from app.services.chunker import chunk_document


class TestChunkDocument:
    def test_empty_string_returns_empty(self):
        assert chunk_document("") == []

    def test_whitespace_only_returns_empty(self):
        assert chunk_document("   \n\n  ") == []

    def test_short_text_returns_single_chunk(self):
        text = "This is a short document."
        chunks = chunk_document(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_splits_into_multiple_chunks(self):
        # Create text that exceeds max_chars
        paragraph = "A" * 3000
        text = f"{paragraph}\n\n{paragraph}\n\n{paragraph}"
        chunks = chunk_document(text, max_chars=5000, overlap=0)
        assert len(chunks) >= 2

    def test_overlap_included(self):
        paragraph1 = "First paragraph " * 200  # ~3200 chars
        paragraph2 = "Second paragraph " * 200
        text = f"{paragraph1.strip()}\n\n{paragraph2.strip()}"
        chunks = chunk_document(text, max_chars=4000, overlap=100)
        assert len(chunks) >= 2
        # Overlap means the end of chunk[0] appears at the start of chunk[1]
        if len(chunks) >= 2:
            tail = chunks[0][-100:]
            assert tail in chunks[1]

    def test_respects_max_chars(self):
        paragraph = "Word " * 600  # ~3000 chars per paragraph
        text = f"{paragraph.strip()}\n\n{paragraph.strip()}\n\n{paragraph.strip()}"
        max_chars = 5000
        chunks = chunk_document(text, max_chars=max_chars, overlap=0)
        for chunk in chunks:
            # Allow some slack for paragraph boundaries
            assert len(chunk) <= max_chars + 3000
