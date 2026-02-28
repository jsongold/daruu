"""FormContextBuilder — wraps existing VisionAutofillService extraction logic.

Extracts data from conversation data sources and builds a FormContext
with field specs, data source entries, and fuzzy mapping candidates.
Enriches fields with label candidates via injected FieldEnricher strategy.
"""

import asyncio
import logging
from typing import Any

from app.infrastructure.observability.stopwatch import StopWatch

from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
    MappingCandidate,
)
from app.models.data_source import DataSource
from app.repositories import DataSourceRepository
from app.services.form_context.enricher import FieldEnricher
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
        enricher: FieldEnricher,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._extraction_service = extraction_service
        self._enricher = enricher
        # Cache enriched fields per document_id to avoid repeated enrichment
        self._enriched_fields_cache: dict[str, tuple[FormFieldSpec, ...]] = {}

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
        with StopWatch("FormContextBuilder.build", logger) as sw:
            with sw.lap("list_sources"):
                data_sources = self._data_source_repo.list_by_conversation(
                    conversation_id
                )
            logger.info(
                "FormContextBuilder: %d sources",
                len(data_sources),
            )

            with sw.lap("enrich_fields+extract_sources"):
                enriched_fields, entries = await asyncio.gather(
                    self._enrich_fields_async(document_id, field_hints),
                    self._extract_from_sources(data_sources),
                )
            logger.info(
                "FormContextBuilder: enrich+extract done in %dms",
                sw.laps["enrich_fields+extract_sources"],
            )

            with sw.lap("match_candidates"):
                candidates = self._build_mapping_candidates(enriched_fields, entries)

            sw.set(
                document_id=document_id,
                sources_count=len(data_sources),
                fields_count=len(field_hints),
            )

        return FormContext(
            document_id=document_id,
            conversation_id=conversation_id,
            fields=enriched_fields,
            data_sources=tuple(entries),
            mapping_candidates=tuple(candidates),
            rules=user_rules,
        )

    async def _enrich_fields_async(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]:
        """Enrich fields with label candidates.

        Caches results per document_id since the target document's field
        labels don't change between pipeline runs or Q&A turns.
        """
        cached = self._enriched_fields_cache.get(document_id)
        if cached is not None:
            logger.info("Field enrichment: CACHED for document %s (%d fields)", document_id, len(cached))
            return cached

        logger.info("Field enrichment: enriching %d fields for document %s", len(fields), document_id)
        result = await self._enricher.enrich(document_id, fields)

        self._enriched_fields_cache[document_id] = result
        return result

    async def _extract_from_sources(
        self,
        data_sources: list[DataSource],
    ) -> list[DataSourceEntry]:
        """Extract data from all data sources in parallel.

        Mirrors VisionAutofillService._extract_from_sources() logic.
        Sources with cached extracted_data are resolved immediately;
        sources requiring extraction are parallelized via asyncio.gather().
        """
        loop = asyncio.get_running_loop()

        async def _extract_single(source: DataSource) -> DataSourceEntry:
            if source.extracted_data is not None:
                # Eager extraction stored fields + _raw_text at upload time
                cached = dict(source.extracted_data)
                raw_text = cached.pop("_raw_text", None)
                logger.info(
                    "Source '%s' (%s): FAST PATH — cached %d fields, raw_text=%s",
                    source.name,
                    source.type.value,
                    len(cached),
                    "yes" if raw_text else "no",
                )
                return DataSourceEntry(
                    source_name=source.name,
                    source_type=source.type.value,
                    extracted_fields=cached,
                    raw_text=raw_text or source.text_content or source.content_preview,
                )

            logger.info(
                "Source '%s' (%s): SLOW PATH — extracting now (extracted_data is None)",
                source.name,
                source.type.value,
            )
            result = await loop.run_in_executor(
                None,
                self._extraction_service.extract_from_data_source,
                source,
            )
            if result.extracted_fields:
                await loop.run_in_executor(
                    None,
                    self._data_source_repo.update_extracted_data,
                    source.id,
                    result.extracted_fields,
                )
            return DataSourceEntry(
                source_name=source.name,
                source_type=source.type.value,
                extracted_fields=dict(result.extracted_fields),
                raw_text=result.raw_text,
                confidence=result.confidence,
            )

        entries = list(await asyncio.gather(
            *(_extract_single(s) for s in data_sources)
        ))
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
                if not isinstance(value, str):
                    continue
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
        """Compute a match score between a data key and field identifiers.

        Uses RapidFuzz for fuzzy matching when available, falling back
        to substring containment checks.
        """
        if normalized_key == normalized_label or normalized_key == normalized_id:
            return 0.95

        try:
            from rapidfuzz import fuzz

            label_score = fuzz.token_sort_ratio(normalized_key, normalized_label) / 100.0
            id_score = fuzz.token_sort_ratio(normalized_key, normalized_id) / 100.0
            best = max(label_score, id_score)

            if best >= 0.85:
                return round(best, 3)
            if best >= 0.6:
                return round(best * 0.9, 3)
            if normalized_key in normalized_label or normalized_label in normalized_key:
                return max(0.6, round(best, 3))
            if normalized_key in normalized_id or normalized_id in normalized_key:
                return max(0.5, round(best, 3))
            return 0.0

        except ImportError:
            if normalized_key in normalized_label or normalized_label in normalized_key:
                return 0.6
            if normalized_key in normalized_id or normalized_id in normalized_key:
                return 0.5
            return 0.0
