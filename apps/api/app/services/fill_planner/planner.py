"""FillPlanner — wraps existing LLM autofill logic.

Reuses AUTOFILL_SYSTEM_PROMPT and build_autofill_prompt from
vision_autofill/prompts.py, plus the same OpenAI client pattern.
Supports both Quick mode (one-shot fill) and Detailed mode (multi-turn Q&A).
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.domain.models.fill_plan import (
    FieldFillAction,
    FieldQuestion,
    FillActionType,
    FillPlan,
    QuestionOption,
    QuestionType,
)
from app.domain.models.form_context import FormContext
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    DETAILED_MODE_SYSTEM_PROMPT,
    build_autofill_prompt,
    build_detailed_prompt,
    format_data_sources,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnResult:
    """Result of a single turn in detailed mode.

    Either a question (type="question") or a fill plan (type="fill_plan").
    """

    type: str  # "question" or "fill_plan"
    question: FieldQuestion | None = None
    plan: FillPlan | None = None
    raw_llm_response: str | None = None


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
                **(
                    {"nearby_labels": [lc.text for lc in f.label_candidates]}
                    if f.label_candidates
                    else {}
                ),
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

    async def plan_turn(
        self,
        context: FormContext,
        conversation_history: list[dict[str, Any]] | None = None,
        just_fill: bool = False,
    ) -> TurnResult:
        """Execute a single turn in detailed mode.

        Args:
            context: FormContext with fields, data sources, etc.
            conversation_history: Previous Q&A turns (list of dicts).
            just_fill: If True, skip questions and return fill plan.

        Returns:
            TurnResult with either a question or a fill plan.
        """
        if not self._llm_client:
            plan = self._candidate_plan(context)
            return TurnResult(type="fill_plan", plan=plan)

        if just_fill:
            plan = await self._llm_plan(context)
            return TurnResult(type="fill_plan", plan=plan)

        return await self._detailed_turn(context, conversation_history or [])

    async def _detailed_turn(
        self,
        context: FormContext,
        conversation_history: list[dict[str, Any]],
    ) -> TurnResult:
        """Execute a detailed mode LLM turn."""
        fields_dicts = [
            {
                "field_id": f.field_id,
                "label": f.label,
                "type": f.field_type,
                **(
                    {"nearby_labels": [lc.text for lc in f.label_candidates]}
                    if f.label_candidates
                    else {}
                ),
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

        history_text = self._format_conversation_history(conversation_history)

        user_prompt = build_detailed_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            conversation_history=history_text,
            rules=user_rules,
        )

        try:
            response = await self._llm_client.complete(
                messages=[
                    {"role": "system", "content": DETAILED_MODE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            raw_response = response.content
            result = json.loads(raw_response)

            if result.get("type") == "question":
                question = self._parse_question(result)
                return TurnResult(
                    type="question",
                    question=question,
                    raw_llm_response=raw_response,
                )
            else:
                actions = self._parse_llm_result(context, result)
                model_used = getattr(self._llm_client, "_model", None)
                plan = FillPlan(
                    document_id=context.document_id,
                    actions=tuple(actions),
                    model_used=model_used,
                    raw_llm_response=raw_response,
                )
                return TurnResult(
                    type="fill_plan",
                    plan=plan,
                    raw_llm_response=raw_response,
                )

        except Exception as e:
            logger.warning(f"Detailed turn failed, falling back to fill plan: {e}")
            plan = self._candidate_plan(context)
            return TurnResult(type="fill_plan", plan=plan)

    @staticmethod
    def _parse_question(result: dict[str, Any]) -> FieldQuestion:
        """Parse a question response from the LLM."""
        question_type_str = result.get("question_type", "free_text")
        try:
            question_type = QuestionType(question_type_str)
        except ValueError:
            question_type = QuestionType.FREE_TEXT

        options = tuple(
            QuestionOption(
                id=opt.get("id", f"opt{i}"),
                label=opt.get("label", ""),
            )
            for i, opt in enumerate(result.get("options", []))
        )

        return FieldQuestion(
            text=result.get("question", ""),
            type=question_type,
            options=options,
            context=result.get("context"),
        )

    @staticmethod
    def _format_conversation_history(
        conversation: list[dict[str, Any]],
    ) -> str:
        """Format conversation history for the LLM prompt."""
        if not conversation:
            return "No previous conversation."

        lines: list[str] = []
        for turn in conversation:
            role = turn.get("role", "unknown")
            turn_type = turn.get("type", "unknown")

            if role == "assistant" and turn_type == "question":
                q = turn.get("question", "")
                lines.append(f"Assistant asked: {q}")
                opts = turn.get("options", [])
                if opts:
                    for opt in opts:
                        lines.append(f"  - {opt.get('label', opt.get('id', ''))}")
            elif role == "user" and turn_type == "answer":
                selected = turn.get("selected_option_ids", [])
                free = turn.get("free_text")
                if selected:
                    lines.append(f"User selected: {', '.join(selected)}")
                if free:
                    lines.append(f"User answered: {free}")

        return "\n".join(lines) if lines else "No previous conversation."
