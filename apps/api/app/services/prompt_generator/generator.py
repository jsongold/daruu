"""PromptGenerator — generates form-specific system prompts via LLM.

Uses a meta-prompt to instruct the LLM to analyze form fields with
their spatial context (nearby_labels from DirectionalFieldEnricher)
and produce a structured JSON mapping. The mapping is then used to
build a deterministic system prompt for downstream fill planning.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.domain.models.form_context import FormContext
from app.services.document_service import DocumentService
from app.services.prompt_generator.meta_prompt import (
    PROMPT_GENERATION_SYSTEM_PROMPT,
    build_prompt_generation_user_prompt,
)
from app.services.prompt_generator.models import PromptGenerationResult
from app.services.prompt_generator.prompt_builder import build_specialized_prompt

logger = logging.getLogger(__name__)


class PromptGenerator:
    """Generates form-specific system prompts using LLM analysis.

    Takes a FormContext (with nearby_labels from DirectionalFieldEnricher)
    and PDF text blocks, then calls the LLM with a meta-prompt to produce
    a structured JSON mapping. The mapping is converted into a deterministic
    system prompt via prompt_builder.
    """

    def __init__(
        self,
        llm_client: Any,
        document_service: DocumentService,
    ) -> None:
        self._llm_client = llm_client
        self._document_service = document_service

    async def generate(
        self,
        document_id: str,
        context: FormContext,
        similar_prompts: list[str] | None = None,
    ) -> PromptGenerationResult:
        """Generate a form-specific system prompt.

        Args:
            document_id: Target document ID for text block extraction.
            context: FormContext with fields and label_candidates.
            similar_prompts: Previously generated prompts for similar forms.

        Returns:
            PromptGenerationResult with the specialized prompt and metadata.
        """
        t0 = time.perf_counter()

        # 1. Extract text blocks from PDF
        text_blocks = self._extract_text_blocks(document_id, context)

        # 2. Build user prompt
        user_prompt = build_prompt_generation_user_prompt(
            context, text_blocks, similar_prompts
        )

        # 3. Call LLM with meta-prompt requesting JSON output
        messages: list[dict[str, str]] = [
            {"role": "system", "content": PROMPT_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        model_used = getattr(self._llm_client, "model", None) or getattr(
            self._llm_client, "_model", "unknown"
        )
        prompt_chars = len(PROMPT_GENERATION_SYSTEM_PROMPT) + len(user_prompt)
        logger.info(
            f"[prompt_generate] model={model_used} | "
            f"prompt={prompt_chars:,} chars (~{prompt_chars // 4:,} tokens) | "
            f"fields={len(context.fields)}"
        )

        response = await self._llm_client.complete(
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw_content = response.content.strip()

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            f"[prompt_generate] done in {elapsed_ms:,}ms | "
            f"response_length={len(raw_content)} chars"
        )

        # 4. Parse JSON mapping
        try:
            mapping = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning(
                "[prompt_generate] LLM returned non-JSON, falling back to raw text"
            )
            # Fallback: treat raw text as a legacy prompt
            field_mapping = self._extract_field_mapping(context)
            return PromptGenerationResult(
                specialized_prompt=raw_content,
                field_mapping=field_mapping,
                form_title=None,
                sections=None,
                format_rules=None,
                fill_rules=None,
                key_field_mappings=None,
                generation_time_ms=elapsed_ms,
                model_used=model_used or "unknown",
                validation_passed=False,
                missing_field_ids=(),
            )

        # 5. Validate: check all field_ids are present in field_labels
        field_ids = {f.field_id for f in context.fields}
        field_labels = mapping.get("field_labels", {})
        missing = field_ids - set(field_labels.keys())

        if missing:
            logger.warning(
                f"[prompt_generate] {len(missing)} field_ids missing from "
                f"mapping, appending fallbacks: {sorted(missing)}"
            )
            # Append fallback labels from context
            for fid in sorted(missing):
                field = next((f for f in context.fields if f.field_id == fid), None)
                if field and field.label_candidates:
                    field_labels[fid] = field.label_candidates[0].text
                elif field and field.label and field.label != fid:
                    field_labels[fid] = field.label
                else:
                    field_labels[fid] = fid
            mapping["field_labels"] = field_labels

        # 6. Build specialized prompt from mapping
        specialized_prompt = build_specialized_prompt(mapping)

        # Extract key_field_mappings
        raw_mappings = mapping.get("key_field_mappings", [])
        key_field_mappings = tuple(raw_mappings) if raw_mappings else None

        if key_field_mappings:
            mapped_count = sum(1 for m in key_field_mappings if m.get("field_id"))
            logger.info(
                f"[prompt_generate] key_field_mappings: "
                f"{mapped_count}/{len(key_field_mappings)} keys mapped to fields"
            )

        return PromptGenerationResult(
            specialized_prompt=specialized_prompt,
            field_mapping=field_labels,
            form_title=mapping.get("form_title"),
            sections=mapping.get("sections"),
            format_rules=mapping.get("format_rules"),
            fill_rules=mapping.get("fill_rules"),
            key_field_mappings=key_field_mappings,
            generation_time_ms=elapsed_ms,
            model_used=model_used or "unknown",
            validation_passed=len(missing) == 0,
            missing_field_ids=tuple(sorted(missing)),
        )

    def _extract_text_blocks(
        self,
        document_id: str,
        context: FormContext,
    ) -> list[dict[str, Any]]:
        """Extract text blocks from PDF for the relevant pages."""
        field_pages = sorted({f.page for f in context.fields if f.page is not None})
        try:
            return self._document_service.extract_text_blocks(
                document_id, pages=field_pages or None
            )
        except Exception as e:
            logger.warning(f"Failed to extract text blocks: {e}")
            return []

    @staticmethod
    def _extract_field_mapping(context: FormContext) -> dict[str, str]:
        """Build a best-effort field_id -> label mapping from context."""
        mapping: dict[str, str] = {}
        for field in context.fields:
            if field.label_candidates:
                mapping[field.field_id] = field.label_candidates[0].text
            elif field.label and field.label != field.field_id:
                mapping[field.field_id] = field.label
            else:
                mapping[field.field_id] = field.field_id
        return mapping
