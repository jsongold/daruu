"""FillPlanner — wraps existing LLM autofill logic.

Reuses AUTOFILL_SYSTEM_PROMPT and build_autofill_prompt from
vision_autofill/prompts.py, plus the same OpenAI client pattern.
"""

import json
import logging
from typing import Any

from app.domain.models.fill_plan import FieldFillAction, FillActionType, FillPlan
from app.domain.models.form_context import FormContext
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    build_autofill_prompt,
    format_data_sources,
)

logger = logging.getLogger(__name__)


class FillPlanner:
    """Plans field fill actions using LLM.

    Wraps the LLM autofill logic from VisionAutofillService._llm_autofill().
    Falls back to mapping candidates when LLM is unavailable.
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        """Initialize the planner.

        Args:
            llm_client: Optional LLM client (same interface as OpenAIClient).
                       If None, falls back to mapping-candidate-based planning.
        """
        self._llm_client = llm_client

    async def plan(
        self,
        context: FormContext,
    ) -> FillPlan:
        """Create a fill plan from the given form context.

        Args:
            context: FormContext containing fields, data sources,
                     and mapping candidates.

        Returns:
            FillPlan with an action for each field.
        """
        if self._llm_client:
            return await self._llm_plan(context)
        return self._candidate_plan(context)

    async def _llm_plan(self, context: FormContext) -> FillPlan:
        """Use LLM to produce a fill plan."""
        fields_dicts = [
            {
                "field_id": f.field_id,
                "label": f.label,
                "type": f.field_type,
            }
            for f in context.fields
        ]
        fields_json = json.dumps(fields_dicts, indent=2)

        extractions = [
            {
                "source_name": ds.source_name,
                "source_type": ds.source_type,
                "extracted_fields": ds.extracted_fields,
                "raw_text": ds.raw_text,
            }
            for ds in context.data_sources
        ]
        data_sources_text = format_data_sources(extractions)
        user_rules = list(context.rules) if context.rules else None

        user_prompt = build_autofill_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            rules=user_rules,
        )

        try:
            response = await self._llm_client.complete(
                messages=[
                    {"role": "system", "content": AUTOFILL_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            raw_response = response.content
            result = json.loads(raw_response)
            actions = self._parse_llm_result(context, result)

            model_used = getattr(self._llm_client, "_model", None)

            return FillPlan(
                document_id=context.document_id,
                actions=tuple(actions),
                model_used=model_used,
                raw_llm_response=raw_response,
            )

        except Exception as e:
            logger.warning(f"LLM plan failed, falling back to candidates: {e}")
            return self._candidate_plan(context)

    def _parse_llm_result(
        self,
        context: FormContext,
        result: dict[str, Any],
    ) -> list[FieldFillAction]:
        """Parse LLM JSON response into FieldFillActions."""
        filled_map: dict[str, dict[str, Any]] = {}
        for f in result.get("filled_fields", []):
            filled_map[f["field_id"]] = f

        unfilled_set = set(result.get("unfilled_fields", []))
        actions: list[FieldFillAction] = []

        for field in context.fields:
            if field.field_id in filled_map:
                entry = filled_map[field.field_id]
                actions.append(FieldFillAction(
                    field_id=field.field_id,
                    action=FillActionType.FILL,
                    value=str(entry["value"]),
                    confidence=float(entry.get("confidence", 0.8)),
                    source=entry.get("source"),
                ))
            elif field.field_id in unfilled_set:
                actions.append(FieldFillAction(
                    field_id=field.field_id,
                    action=FillActionType.SKIP,
                    reason="LLM could not determine a value",
                ))
            else:
                actions.append(FieldFillAction(
                    field_id=field.field_id,
                    action=FillActionType.SKIP,
                    reason="Field not referenced in LLM response",
                ))

        return actions

    def _candidate_plan(self, context: FormContext) -> FillPlan:
        """Fall back to mapping-candidate-based planning when no LLM."""
        best_candidates: dict[str, tuple[str, float, str]] = {}

        for candidate in context.mapping_candidates:
            existing = best_candidates.get(candidate.field_id)
            if not existing or candidate.score > existing[1]:
                best_candidates[candidate.field_id] = (
                    candidate.source_value,
                    candidate.score,
                    candidate.source_name,
                )

        actions: list[FieldFillAction] = []
        for field in context.fields:
            match = best_candidates.get(field.field_id)
            if match and match[1] >= 0.5:
                actions.append(FieldFillAction(
                    field_id=field.field_id,
                    action=FillActionType.FILL,
                    value=match[0],
                    confidence=match[1],
                    source=match[2],
                ))
            else:
                actions.append(FieldFillAction(
                    field_id=field.field_id,
                    action=FillActionType.SKIP,
                    reason="No matching data source entry found",
                ))

        return FillPlan(
            document_id=context.document_id,
            actions=tuple(actions),
        )
