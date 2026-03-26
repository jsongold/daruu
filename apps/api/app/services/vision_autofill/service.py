"""Vision Autofill Service.

Uses LLM to intelligently match data from user-provided sources
to form fields for automatic filling.
"""

import json
import logging
import time
from typing import Any

from app.agents.llm_wrapper import log_llm_io
from app.models.data_source import DataSource
from app.repositories import DataSourceRepository
from app.services.text_extraction_service import TextExtractionService
from app.services.vision_autofill.models import (
    FieldInfo,
    FilledField,
    VisionAutofillRequest,
    VisionAutofillResponse,
)
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    build_autofill_prompt,
    format_data_sources,
)

logger = logging.getLogger(__name__)


class VisionAutofillService:
    """LLM Vision-based form autofill service.

    This service:
    1. Gathers all data sources for a conversation
    2. Extracts text/data from each source
    3. Builds a prompt with field definitions + extracted data
    4. Calls LLM to match data to fields
    5. Returns structured fill results
    """

    def __init__(
        self,
        data_source_repo: DataSourceRepository,
        extraction_service: TextExtractionService,
        llm_client: Any | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            data_source_repo: Repository for accessing data sources.
            extraction_service: Service for extracting text from sources.
            llm_client: Optional LLM client for AI processing.
                       If None, falls back to rule-based matching.
        """
        self._data_source_repo = data_source_repo
        self._extraction_service = extraction_service
        self._llm_client = llm_client

    async def autofill(
        self,
        request: VisionAutofillRequest,
    ) -> VisionAutofillResponse:
        """Perform autofill using LLM vision.

        Args:
            request: Autofill request with document and field info.

        Returns:
            VisionAutofillResponse with filled values.
        """
        start_time = time.time()

        try:
            # Step 1: Get all data sources for the conversation
            data_sources = self._data_source_repo.list_by_conversation(request.conversation_id)

            if not data_sources:
                return VisionAutofillResponse(
                    success=True,
                    filled_fields=[],
                    unfilled_fields=[f.field_id for f in request.fields],
                    warnings=["No data sources available for autofill"],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )

            # Step 2: Extract data from each source
            extractions = await self._extract_from_sources(data_sources)

            # Step 3: Try LLM-based matching if available
            if self._llm_client:
                result = await self._llm_autofill(
                    request,
                    extractions,
                    system_prompt_override=request.system_prompt,
                )
            else:
                # Fall back to rule-based matching
                result = self._rule_based_autofill(request, extractions)

            result_dict = result.model_dump()
            result_dict["processing_time_ms"] = int((time.time() - start_time) * 1000)

            return VisionAutofillResponse(**result_dict)

        except Exception as e:
            logger.exception(f"Autofill failed: {e}")
            return VisionAutofillResponse(
                success=False,
                filled_fields=[],
                unfilled_fields=[f.field_id for f in request.fields],
                warnings=[],
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )

    async def _extract_from_sources(
        self,
        data_sources: list[DataSource],
    ) -> list[dict[str, Any]]:
        """Extract data from all data sources.

        Args:
            data_sources: List of data sources to extract from.

        Returns:
            List of extraction results with source metadata.
        """
        extractions = []

        for source in data_sources:
            # Use cached extraction if available
            if source.extracted_data:
                extractions.append(
                    {
                        "source_name": source.name,
                        "source_type": source.type.value,
                        "extracted_fields": source.extracted_data,
                        "raw_text": source.text_content or source.content_preview,
                    }
                )
            else:
                # Extract fresh data
                result = self._extraction_service.extract_from_data_source(source)
                extractions.append(
                    {
                        "source_name": source.name,
                        "source_type": source.type.value,
                        "extracted_fields": result.extracted_fields,
                        "raw_text": result.raw_text,
                        "confidence": result.confidence,
                    }
                )

                # Cache the extraction
                if result.extracted_fields:
                    self._data_source_repo.update_extracted_data(source.id, result.extracted_fields)

        return extractions

    async def preview_prompt(
        self,
        request: VisionAutofillRequest,
    ) -> dict[str, Any]:
        """Build and return the prompts without calling the LLM.

        Reuses the same extraction and prompt-building logic as autofill
        so the user can inspect and tune the prompt before running.

        Args:
            request: Autofill request with document and field info.

        Returns:
            Dict with system_prompt, user_prompt, data_source_count,
            and extractions_summary.
        """
        data_sources = self._data_source_repo.list_by_conversation(request.conversation_id)

        extractions: list[dict[str, Any]] = []
        if data_sources:
            extractions = await self._extract_from_sources(data_sources)

        fields_json = json.dumps(
            [f.model_dump() for f in request.fields],
            indent=2,
        )
        data_sources_text = format_data_sources(extractions)
        user_prompt = build_autofill_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            rules=request.rules,
        )

        system_prompt = request.system_prompt or AUTOFILL_SYSTEM_PROMPT

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "data_source_count": len(data_sources),
            "extractions_summary": [
                {
                    "source_name": e.get("source_name", "unknown"),
                    "source_type": e.get("source_type", "unknown"),
                    "field_count": len(e.get("extracted_fields", {})),
                }
                for e in extractions
            ],
        }

    @log_llm_io
    async def _invoke_llm(
        self,
        messages: list[dict[str, str]],
        agent_name: str = "VisionAutofillService",
        operation: str = "autofill",
    ) -> Any:
        """Call LLM. Decorated with log_llm_io for debug prompt logging."""
        return await self._llm_client.complete(
            messages=messages,
            response_format={"type": "json_object"},
        )

    async def _llm_autofill(
        self,
        request: VisionAutofillRequest,
        extractions: list[dict[str, Any]],
        system_prompt_override: str | None = None,
    ) -> VisionAutofillResponse:
        """Use LLM to match extracted data to fields.

        Args:
            request: Autofill request.
            extractions: Extracted data from sources.
            system_prompt_override: Optional system prompt to use instead of default.

        Returns:
            VisionAutofillResponse with LLM-matched values.
        """
        # Build the prompt
        fields_json = json.dumps(
            [f.model_dump() for f in request.fields],
            indent=2,
        )
        data_sources_text = format_data_sources(extractions)
        user_prompt = build_autofill_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            rules=request.rules,
        )

        system_prompt = system_prompt_override or AUTOFILL_SYSTEM_PROMPT
        start_time = time.time()

        try:
            # Call LLM
            response = await self._invoke_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            raw_response = response.content
            # Parse response
            result = json.loads(raw_response)

            filled_fields = [FilledField(**f) for f in result.get("filled_fields", [])]
            unfilled_fields = result.get("unfilled_fields", [])
            warnings = result.get("warnings", [])

            return VisionAutofillResponse(
                success=True,
                filled_fields=filled_fields,
                unfilled_fields=unfilled_fields,
                warnings=warnings,
                raw_response=raw_response,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

        except Exception as e:
            logger.warning(f"LLM autofill failed, falling back to rules: {e}")
            return self._rule_based_autofill(request, extractions)

    def _rule_based_autofill(
        self,
        request: VisionAutofillRequest,
        extractions: list[dict[str, Any]],
    ) -> VisionAutofillResponse:
        """Fall-back rule-based matching when LLM is unavailable.

        Uses simple string matching between field labels and extracted keys.

        Args:
            request: Autofill request.
            extractions: Extracted data from sources.

        Returns:
            VisionAutofillResponse with rule-matched values.
        """
        # Combine all extracted fields
        combined_data: dict[str, tuple[str, str, float]] = {}  # key -> (value, source, confidence)

        for extraction in extractions:
            source_name = extraction.get("source_name", "unknown")
            confidence = extraction.get("confidence", 0.5)
            extracted = extraction.get("extracted_fields", {})

            for key, value in extracted.items():
                if isinstance(value, str):
                    # Normalize the key for matching
                    normalized_key = self._normalize_key(key)
                    existing = combined_data.get(normalized_key)
                    if not existing or confidence > existing[2]:
                        combined_data[normalized_key] = (str(value), source_name, confidence)

        # Match fields to extracted data
        filled_fields: list[FilledField] = []
        unfilled_fields: list[str] = []
        warnings: list[str] = []

        for field in request.fields:
            matched = self._match_field(field, combined_data)
            if matched:
                filled_fields.append(matched)
            else:
                unfilled_fields.append(field.field_id)

        if not filled_fields and extractions:
            warnings.append(
                "No fields could be matched automatically. "
                "Consider adding more descriptive data sources."
            )

        return VisionAutofillResponse(
            success=True,
            filled_fields=filled_fields,
            unfilled_fields=unfilled_fields,
            warnings=warnings,
        )

    def _normalize_key(self, key: str) -> str:
        """Normalize a key for matching.

        Args:
            key: Original key string.

        Returns:
            Normalized lowercase key with no special chars.
        """
        # Convert to lowercase and remove special characters
        normalized = key.lower()
        for char in "._-/\\:":
            normalized = normalized.replace(char, " ")
        # Collapse multiple spaces
        return " ".join(normalized.split())

    def _match_field(
        self,
        field: FieldInfo,
        combined_data: dict[str, tuple[str, str, float]],
    ) -> FilledField | None:
        """Try to match a field to extracted data.

        Args:
            field: Field to match.
            combined_data: Combined extracted data.

        Returns:
            FilledField if matched, None otherwise.
        """
        # Normalize field label and ID
        normalized_label = self._normalize_key(field.label)
        normalized_id = self._normalize_key(field.field_id)

        # Try exact matches first
        for normalized_key, (value, source, confidence) in combined_data.items():
            if normalized_key == normalized_label or normalized_key == normalized_id:
                return FilledField(
                    field_id=field.field_id,
                    value=value,
                    confidence=min(confidence, 0.9),  # Cap at 0.9 for rule-based
                    source=source,
                )

        # Try partial matches
        for normalized_key, (value, source, confidence) in combined_data.items():
            # Check if key is contained in label or vice versa
            if normalized_key in normalized_label or normalized_label in normalized_key:
                return FilledField(
                    field_id=field.field_id,
                    value=value,
                    confidence=min(confidence * 0.7, 0.7),  # Lower confidence for partial
                    source=source,
                )

        return None


def get_vision_autofill_service(
    data_source_repo: DataSourceRepository,
    extraction_service: TextExtractionService,
    llm_client: Any | None = None,
) -> VisionAutofillService:
    """Factory function to create VisionAutofillService.

    Args:
        data_source_repo: Repository for data sources.
        extraction_service: Text extraction service.
        llm_client: Optional LLM client.

    Returns:
        Configured VisionAutofillService instance.
    """
    return VisionAutofillService(
        data_source_repo=data_source_repo,
        extraction_service=extraction_service,
        llm_client=llm_client,
    )
