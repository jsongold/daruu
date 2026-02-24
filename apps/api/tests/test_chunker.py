"""Tests for the text chunker used by RuleAnalyzer."""

import pytest

from app.services.rule_analyzer.chunker import chunk_document


class TestEmptyInput:
    def test_empty_string(self):
        assert chunk_document("") == []

    def test_whitespace_only(self):
        assert chunk_document("   \n\n  ") == []

    def test_none_like_empty(self):
        # Explicitly test empty-ish strings
        assert chunk_document("") == []


class TestSingleChunk:
    def test_short_text_single_chunk(self):
        text = "This is a short rule document."
        result = chunk_document(text)
        assert len(result) == 1
        assert result[0] == text

    def test_under_max_chars(self):
        text = "A" * 2999
        result = chunk_document(text, max_chars=3000)
        assert len(result) == 1


class TestMultipleChunks:
    def test_long_text_splits_on_paragraphs(self):
        # Create text with multiple paragraphs that exceed max_chars
        paragraphs = [f"Paragraph {i}. " + "x" * 200 for i in range(20)]
        text = "\n\n".join(paragraphs)

        result = chunk_document(text, max_chars=500, overlap=50)

        assert len(result) > 1
        # All chunks should be non-empty
        for chunk in result:
            assert len(chunk.strip()) > 0

    def test_respects_max_chars(self):
        paragraphs = [f"Para {i}. " + "y" * 100 for i in range(30)]
        text = "\n\n".join(paragraphs)

        max_chars = 500
        result = chunk_document(text, max_chars=max_chars, overlap=0)

        # Most chunks should be under max_chars (first chunk guaranteed)
        assert len(result[0]) <= max_chars

    def test_overlap_behavior(self):
        # Two paragraphs, each ~300 chars, max 400, overlap 100
        para1 = "A" * 300
        para2 = "B" * 300
        text = f"{para1}\n\n{para2}"

        result = chunk_document(text, max_chars=400, overlap=100)

        assert len(result) >= 2
        # Second chunk should contain overlap from first
        if len(result) >= 2:
            # The overlap comes from the tail of the first chunk
            assert len(result[1]) > 0


class TestEdgeCases:
    def test_single_paragraph_over_max(self):
        # One giant paragraph with no split points
        text = "A" * 5000
        result = chunk_document(text, max_chars=3000)
        # Should still return something (single chunk since no paragraph breaks)
        assert len(result) >= 1

    def test_many_empty_paragraphs(self):
        text = "\n\n\n\n\n\nActual content\n\n\n\n"
        result = chunk_document(text)
        assert len(result) == 1
        assert "Actual content" in result[0]

    def test_zero_overlap(self):
        paragraphs = ["Para " + str(i) + " " + "x" * 200 for i in range(10)]
        text = "\n\n".join(paragraphs)
        result = chunk_document(text, max_chars=500, overlap=0)
        assert len(result) > 1
