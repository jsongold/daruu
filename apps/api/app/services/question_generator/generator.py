"""QuestionGenerator — inspects fill results and generates questions about gaps.

Analyzes a FillPlan for skipped fields and low-confidence fills, then uses
an LLM to generate targeted questions for the user.
"""

import json
import logging
import time
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
from app.services.question_generator.prompts import (
    QUESTION_GENERATION_SYSTEM_PROMPT,
    QUESTION_GENERATION_USER_TEMPLATE,
)
from app.services.vision_autofill.prompts import format_data_sources

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates questions from fill plan gaps (skipped / low-confidence fields)."""

    MAX_QUESTIONS = 5
    LOW_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm_client = llm_client

    async def generate(
        self,
        plan: FillPlan,
        context: FormContext,
    ) -> tuple[FieldQuestion, ...]:
        """Inspect fill result and generate questions about gaps.

        Args:
            plan: The draft FillPlan from FillPlanner.
            context: The FormContext with field specs and data sources.

        Returns:
            Tuple of FieldQuestion models (may be empty if no gaps).
        """
        if not self._llm_client:
            return ()

        skipped, low_confidence, good_fills = self._partition_actions(plan.actions)

        if not skipped and not low_confidence:
            return ()

        user_prompt = self._build_user_prompt(
            skipped, low_confidence, good_fills, context
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": QUESTION_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        prompt_chars = len(QUESTION_GENERATION_SYSTEM_PROMPT) + len(user_prompt)
        logger.info(
            f"[question_gen] prompt={prompt_chars:,} chars "
            f"(~{prompt_chars // 4:,} tokens) | "
            f"skipped={len(skipped)} low_conf={len(low_confidence)}"
        )

        try:
            t0 = time.perf_counter()
            response = await self._llm_client.complete(
                messages=messages,
                response_format={"type": "json_object"},
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            raw = response.content
            logger.info(f"[question_gen] done in {elapsed_ms:,}ms | {len(raw)} chars")

            result = json.loads(raw)
            return self._parse_questions(result)

        except Exception as e:
            logger.warning(f"[question_gen] failed: {e}")
            return ()

    def _partition_actions(
        self,
        actions: tuple[FieldFillAction, ...],
    ) -> tuple[list[FieldFillAction], list[FieldFillAction], list[FieldFillAction]]:
        """Partition actions into skipped, low_confidence, and good_fills."""
        skipped: list[FieldFillAction] = []
        low_confidence: list[FieldFillAction] = []
        good_fills: list[FieldFillAction] = []

        for action in actions:
            if action.action == FillActionType.SKIP:
                skipped.append(action)
            elif (
                action.action == FillActionType.FILL
                and action.confidence < self.LOW_CONFIDENCE_THRESHOLD
            ):
                low_confidence.append(action)
            elif action.action == FillActionType.FILL:
                good_fills.append(action)

        return skipped, low_confidence, good_fills

    def _build_user_prompt(
        self,
        skipped: list[FieldFillAction],
        low_confidence: list[FieldFillAction],
        good_fills: list[FieldFillAction],
        context: FormContext,
    ) -> str:
        """Build the user prompt for the question generation LLM call."""
        field_map = {f.field_id: f for f in context.fields}

        # Already filled fields (so LLM knows NOT to ask about these)
        if good_fills:
            filled_lines = []
            for a in good_fills:
                field = field_map.get(a.field_id)
                label = self._get_field_label(field) if field else a.field_id
                filled_lines.append(
                    f"- {a.field_id}: {label} = \"{a.value}\" "
                    f"(confidence={a.confidence:.2f})"
                )
            filled_text = "\n".join(filled_lines)
        else:
            filled_text = "None"

        # Skipped fields text
        if skipped:
            skipped_lines = []
            for a in skipped:
                field = field_map.get(a.field_id)
                label = self._get_field_label(field) if field else a.field_id
                reason = a.reason or "no data found"
                skipped_lines.append(f"- {a.field_id}: {label} ({reason})")
            skipped_text = "\n".join(skipped_lines)
        else:
            skipped_text = "None"

        # Low confidence fields text
        if low_confidence:
            low_conf_lines = []
            for a in low_confidence:
                field = field_map.get(a.field_id)
                label = self._get_field_label(field) if field else a.field_id
                low_conf_lines.append(
                    f"- {a.field_id}: {label} = \"{a.value}\" "
                    f"(confidence={a.confidence:.2f}, source={a.source})"
                )
            low_conf_text = "\n".join(low_conf_lines)
        else:
            low_conf_text = "None"

        # Data sources
        extractions = []
        for ds in context.data_sources:
            entry: dict[str, Any] = {
                "source_name": ds.source_name,
                "source_type": ds.source_type,
                "extracted_fields": ds.extracted_fields,
            }
            extractions.append(entry)
        data_sources_text = format_data_sources(extractions)

        # Field context (labels for all fields)
        field_context_lines = []
        for field in context.fields:
            label = self._get_field_label(field)
            field_context_lines.append(
                f"- {field.field_id}: {label} ({field.field_type})"
            )
        fields_context = "\n".join(field_context_lines)

        return QUESTION_GENERATION_USER_TEMPLATE.format(
            filled_fields_text=filled_text,
            skipped_fields_text=skipped_text,
            low_confidence_fields_text=low_conf_text,
            data_sources_text=data_sources_text,
            fields_context=fields_context,
            max_questions=self.MAX_QUESTIONS,
        )

    @staticmethod
    def _get_field_label(field: Any) -> str:
        """Get the best label for a field."""
        if field.label_candidates:
            return field.label_candidates[0].text
        if field.label and field.label != field.field_id:
            return field.label
        return field.field_id

    @staticmethod
    def _parse_questions(result: dict[str, Any]) -> tuple[FieldQuestion, ...]:
        """Parse LLM JSON response into FieldQuestion domain models.

        Validates that choice/confirm questions have options.
        Falls back to free_text if a choice question has no options.
        """
        raw_questions = result.get("questions", [])
        questions: list[FieldQuestion] = []

        for i, q in enumerate(raw_questions):
            try:
                q_type = QuestionType(q.get("question_type", "free_text"))
            except ValueError:
                q_type = QuestionType.FREE_TEXT

            options = tuple(
                QuestionOption(id=opt["id"], label=opt["label"])
                for opt in q.get("options", [])
                if "id" in opt and "label" in opt
            )

            # Validate: choice/confirm must have options, otherwise downgrade
            needs_options = q_type in (
                QuestionType.SINGLE_CHOICE,
                QuestionType.MULTIPLE_CHOICE,
                QuestionType.CONFIRM,
            )
            if needs_options and len(options) < 2:
                if q_type == QuestionType.CONFIRM:
                    # Auto-add yes/no for confirm questions
                    options = (
                        QuestionOption(id="yes", label="はい"),
                        QuestionOption(id="no", label="いいえ"),
                    )
                else:
                    # Downgrade single/multiple choice to free_text
                    q_type = QuestionType.FREE_TEXT
                    options = ()

            text = q.get("question", "")
            if not text:
                continue

            questions.append(FieldQuestion(
                id=q.get("id", f"q{i}"),
                text=text,
                type=q_type,
                options=options,
                context=q.get("context"),
            ))

        return tuple(questions)
