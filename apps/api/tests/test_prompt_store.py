"""Tests for PromptStore."""

from __future__ import annotations

import json
import tempfile

import pytest

from app.domain.models.form_context import FormFieldSpec
from app.services.prompt_generator.store import PromptStore


def _make_fields() -> tuple[FormFieldSpec, ...]:
    return (
        FormFieldSpec(
            field_id="Text1",
            label="Text1",
            field_type="text",
            page=1,
        ),
        FormFieldSpec(
            field_id="Text2",
            label="Text2",
            field_type="text",
            page=1,
        ),
        FormFieldSpec(
            field_id="Check1",
            label="Check1",
            field_type="checkbox",
            page=1,
        ),
    )


def test_compute_form_hash_deterministic() -> None:
    """Same fields should always produce the same hash."""
    fields = _make_fields()
    store = PromptStore(storage_dir=tempfile.mkdtemp())

    hash1 = store.compute_form_hash(fields)
    hash2 = store.compute_form_hash(fields)

    assert hash1 == hash2
    assert len(hash1) == 16  # sha256 truncated to 16 chars


def test_compute_form_hash_order_independent() -> None:
    """Hash should be the same regardless of field order."""
    fields = _make_fields()
    reversed_fields = tuple(reversed(fields))
    store = PromptStore(storage_dir=tempfile.mkdtemp())

    hash1 = store.compute_form_hash(fields)
    hash2 = store.compute_form_hash(reversed_fields)

    assert hash1 == hash2


def test_compute_form_hash_different_for_different_fields() -> None:
    """Different field structures should produce different hashes."""
    fields1 = _make_fields()
    fields2 = (
        FormFieldSpec(field_id="Field_A", label="A", field_type="text", page=1),
        FormFieldSpec(field_id="Field_B", label="B", field_type="number", page=1),
    )
    store = PromptStore(storage_dir=tempfile.mkdtemp())

    hash1 = store.compute_form_hash(fields1)
    hash2 = store.compute_form_hash(fields2)

    assert hash1 != hash2


def test_store_and_find_roundtrip() -> None:
    """Stored prompt should be retrievable via find_similar()."""
    store = PromptStore(storage_dir=tempfile.mkdtemp())
    fields = _make_fields()
    form_hash = store.compute_form_hash(fields)

    prompt = "This is a specialized prompt for testing."
    store.store(form_hash, prompt, form_title="Test Form", field_count=3)

    result = store.find_similar(form_hash)

    assert result is not None
    assert len(result) == 1
    assert result[0] == prompt


def test_find_similar_cache_miss() -> None:
    """Non-existent hash should return None."""
    store = PromptStore(storage_dir=tempfile.mkdtemp())

    result = store.find_similar("nonexistent_hash")

    assert result is None


def test_store_writes_valid_json() -> None:
    """Stored file should contain valid JSON with expected fields."""
    tmpdir = tempfile.mkdtemp()
    store = PromptStore(storage_dir=tmpdir)
    fields = _make_fields()
    form_hash = store.compute_form_hash(fields)

    store.store(form_hash, "Test prompt", form_title="Tax Form", field_count=3)

    path = store._storage_dir / f"{form_hash}.json"
    assert path.exists()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["form_hash"] == form_hash
    assert data["specialized_prompt"] == "Test prompt"
    assert data["field_count"] == 3
    assert data["form_title"] == "Tax Form"
    assert "created_at" in data


def test_store_overwrites_existing() -> None:
    """Storing with same hash should overwrite the previous entry."""
    store = PromptStore(storage_dir=tempfile.mkdtemp())
    fields = _make_fields()
    form_hash = store.compute_form_hash(fields)

    store.store(form_hash, "Old prompt", field_count=3)
    store.store(form_hash, "New prompt", field_count=3)

    result = store.find_similar(form_hash)
    assert result is not None
    assert result[0] == "New prompt"
