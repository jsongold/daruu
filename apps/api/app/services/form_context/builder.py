"""FormContextBuilder — wraps existing VisionAutofillService extraction logic.

Extracts data from conversation data sources and builds a FormContext
with field specs, data source entries, and fuzzy mapping candidates.
Optionally enriches fields with nearby PDF text labels via proximity matching.
"""

import logging
import math
from typing import Any

from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
    LabelCandidate,
    MappingCandidate,
)
from app.models.data_source import DataSource
from app.repositories import DataSourceRepository
from app.services.document_service import DocumentService
from app.services.text_extraction_service import TextExtractionService

logger = logging.getLogger(__name__)

_MAX_LABEL_DISTANCE = 150.0
_MAX_LABEL_CANDIDATES = 3


class FormContextBuilder:
    """Builds FormContext by extracting and matching data from sources.

    Wraps the extraction logic from VisionAutofillService._extract_from_sources()
    and the fuzzy matching logic from VisionAutofillService._rule_based_autofill().
    """

    def __init__(
        self,
        data_source_repo: DataSourceRepository,
        extraction_service: TextExtractionService,
        document_service: DocumentService | None = None,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._extraction_service = extraction_service
        self._document_service = document_service

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

        enriched_fields = self._enrich_fields_with_labels(document_id, field_hints)

        entries = await self._extract_from_sources(data_sources)
        candidates = self._build_mapping_candidates(enriched_fields, entries)

        return FormContext(
            document_id=document_id,
            conversation_id=conversation_id,
            fields=enriched_fields,
            data_sources=tuple(entries),
            mapping_candidates=tuple(candidates),
            rules=user_rules,
        )

    def _enrich_fields_with_labels(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]:
        """Enrich fields with nearby PDF text labels using proximity matching.

        For each field with bbox coordinates, finds nearby text blocks
        from the target PDF and attaches them as label_candidates.
        This is language-agnostic — pure geometry.
        """
        if self._document_service is None:
            return fields

        try:
            text_blocks = self._document_service.extract_text_blocks(document_id)
        except Exception as e:
            logger.warning(f"Failed to extract text blocks for label enrichment: {e}")
            return fields

        if not text_blocks:
            return fields

        enriched: list[FormFieldSpec] = []
        for field in fields:
            if field.x is None or field.y is None:
                enriched.append(field)
                continue

            candidates = self._find_nearby_text(field, text_blocks)
            if candidates:
                enriched.append(field.model_copy(update={"label_candidates": tuple(candidates)}))
            else:
                enriched.append(field)

        return tuple(enriched)

    @staticmethod
    def _find_nearby_text(
        field: FormFieldSpec,
        text_blocks: list[dict[str, Any]],
    ) -> list[LabelCandidate]:
        """Find text blocks near a field using center-to-center Euclidean distance.

        Args:
            field: Field with bbox coordinates.
            text_blocks: Text blocks from DocumentService.extract_text_blocks().
                Each has: text, page, bbox=[x, y, width, height].

        Returns:
            Top-N nearest LabelCandidates within max distance, sorted by distance.
        """
        field_cx = field.x + (field.width or 0) / 2
        field_cy = field.y + (field.height or 0) / 2
        field_page = field.page

        scored: list[tuple[float, str, int | None]] = []
        for block in text_blocks:
            text = block.get("text", "")
            if not text or not text.strip():
                continue

            block_page = block.get("page")
            if field_page is not None and block_page is not None and field_page != block_page:
                continue

            bbox = block.get("bbox")
            if not bbox or len(bbox) < 4:
                continue

            block_cx = bbox[0] + bbox[2] / 2
            block_cy = bbox[1] + bbox[3] / 2

            dist = math.sqrt((field_cx - block_cx) ** 2 + (field_cy - block_cy) ** 2)
            if dist <= _MAX_LABEL_DISTANCE:
                scored.append((dist, text.strip(), block_page))

        scored.sort(key=lambda x: x[0])
        seen_texts: set[str] = set()
        candidates: list[LabelCandidate] = []
        for dist, text, page in scored:
            if text in seen_texts:
                continue
            seen_texts.add(text)
            confidence = max(0.0, 1.0 - dist / _MAX_LABEL_DISTANCE)
            candidates.append(LabelCandidate(
                text=text,
                confidence=round(confidence, 3),
                page=page,
            ))
            if len(candidates) >= _MAX_LABEL_CANDIDATES:
                break

        return candidates

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
