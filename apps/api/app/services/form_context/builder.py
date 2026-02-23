"""FormContextBuilder — wraps existing VisionAutofillService extraction logic.

Extracts data from conversation data sources and builds a FormContext
with field specs, data source entries, and fuzzy mapping candidates.
"""

import logging
from typing import Any

from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
    MappingCandidate,
)
from app.models.data_source import DataSource
from app.repositories import DataSourceRepository
from app.services.text_extraction_service import TextExtractionService

logger = logging.getLogger(__name__)


class FormContextBuilder:
    """Builds FormContext by extracting and matching data from sources.

    Wraps the extraction logic from VisionAutofillService._extract_from_sources()
    and the fuzzy matching logic from VisionAutofillService._rule_based_autofill().
    """

    def __init__(
        self,
        data_source_repo: DataSourceRepository,
        extraction_service: TextExtractionService,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._extraction_service = extraction_service

    async def build(
        self,
        document_id: str,
        conversation_id: str,
        field_hints: tuple[FormFieldSpec, ...],
        user_rules: tuple[str, ...] = (),
    ) -> FormContext:
        """Build a FormContext from document fields and conversation data sources.

        Args:
            document_id: Target document ID.
            conversation_id: Conversation ID containing data sources.
            field_hints: Form field specifications to match against.
            user_rules: Optional user-provided filling rules.

        Returns:
            FormContext with fields, data sources, and mapping candidates.
        """
        data_sources = self._data_source_repo.list_by_conversation(conversation_id)

        entries = await self._extract_from_sources(data_sources)
        candidates = self._build_mapping_candidates(field_hints, entries)

        return FormContext(
            document_id=document_id,
            conversation_id=conversation_id,
            fields=field_hints,
            data_sources=tuple(entries),
            mapping_candidates=tuple(candidates),
            rules=user_rules,
        )

    async def _extract_from_sources(
        self,
        data_sources: list[DataSource],
    ) -> list[DataSourceEntry]:
        """Extract data from all data sources.

        Mirrors VisionAutofillService._extract_from_sources() logic.
        """
        entries: list[DataSourceEntry] = []

        for source in data_sources:
            if source.extracted_data:
                entries.append(DataSourceEntry(
                    source_name=source.name,
                    source_type=source.type.value,
                    extracted_fields={
                        k: str(v) for k, v in source.extracted_data.items()
                        if isinstance(v, str)
                    },
                    raw_text=source.text_content or source.content_preview,
                ))
            else:
                result = self._extraction_service.extract_from_data_source(source)
                entries.append(DataSourceEntry(
                    source_name=source.name,
                    source_type=source.type.value,
                    extracted_fields={
                        k: str(v) for k, v in result.extracted_fields.items()
                        if isinstance(v, str)
                    },
                    raw_text=result.raw_text,
                    confidence=result.confidence,
                ))
                if result.extracted_fields:
                    self._data_source_repo.update_extracted_data(
                        source.id, result.extracted_fields
                    )

        return entries

    def _build_mapping_candidates(
        self,
        fields: tuple[FormFieldSpec, ...],
        entries: list[DataSourceEntry],
    ) -> list[MappingCandidate]:
        """Build fuzzy mapping candidates between fields and data source entries.

        Mirrors VisionAutofillService._rule_based_autofill() matching logic.
        """
        combined: dict[str, tuple[str, str, float]] = {}

        for entry in entries:
            for key, value in entry.extracted_fields.items():
                normalized_key = self._normalize_key(key)
                existing = combined.get(normalized_key)
                if not existing or entry.confidence > existing[2]:
                    combined[normalized_key] = (value, entry.source_name, entry.confidence)

        candidates: list[MappingCandidate] = []
        for field in fields:
            normalized_label = self._normalize_key(field.label)
            normalized_id = self._normalize_key(field.field_id)

            for normalized_key, (value, source_name, confidence) in combined.items():
                score = self._compute_match_score(
                    normalized_key, normalized_label, normalized_id
                )
                if score > 0.0:
                    candidates.append(MappingCandidate(
                        field_id=field.field_id,
                        source_key=normalized_key,
                        source_value=value,
                        source_name=source_name,
                        score=score,
                    ))

        return candidates

    @staticmethod
    def _normalize_key(key: str) -> str:
        """Normalize a key for matching.

        Mirrors VisionAutofillService._normalize_key().
        """
        normalized = key.lower()
        for char in "._-/\\:":
            normalized = normalized.replace(char, " ")
        return " ".join(normalized.split())

    @staticmethod
    def _compute_match_score(
        normalized_key: str,
        normalized_label: str,
        normalized_id: str,
    ) -> float:
        """Compute a match score between a data key and field identifiers."""
        if normalized_key == normalized_label or normalized_key == normalized_id:
            return 0.9
        if normalized_key in normalized_label or normalized_label in normalized_key:
            return 0.6
        if normalized_key in normalized_id or normalized_id in normalized_key:
            return 0.5
        return 0.0
