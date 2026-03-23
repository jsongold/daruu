"""FillPlanner — plans field fill actions using LiteLLM + Instructor.

Uses Instructor for structured output with Pydantic validation and
automatic retries. Falls back to mapping-candidate-based planning
when no LLM client is available.
"""

import json
import logging
import time
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
from app.domain.models.form_context import FormContext, FormFieldSpec
from app.services.fill_planner.schemas import (
    LLMDetailedFillResponse,
    LLMDetailedQuestionsResponse,
    LLMFilledField,
    LLMFillResponse,
    LLMReasoningResponse,
)
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    DETAILED_MODE_SYSTEM_PROMPT,
    REASONING_SYSTEM_PROMPT,
    build_autofill_prompt,
    build_detailed_prompt,
    build_reasoning_prompt,
    format_data_sources,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnResult:
    """Result of a single turn in detailed mode.

    Either questions (type="questions") or a fill plan (type="fill_plan").
    """

    type: str  # "questions" or "fill_plan"
    questions: tuple[FieldQuestion, ...] = ()
    plan: FillPlan | None = None
    raw_llm_response: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    model_used: str | None = None
    reasoning: str | None = None
    reasoning_decision: str | None = None
    reasoning_duration_ms: int = 0


class FillPlanner:
    """Plans field fill actions using LLM.

    Accepts any client that implements:
    - complete(messages, response_format) for raw completions
    - create(response_model, messages) for Instructor structured output
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm_client = llm_client

    def _has_instructor(self) -> bool:
        """Check if the client supports Instructor's create() method."""
        return hasattr(self._llm_client, "create")

    async def plan(self, context: FormContext) -> FillPlan:
        if self._llm_client:
            return await self._llm_plan(context)
        return self._candidate_plan(context)

    async def _llm_plan(self, context: FormContext) -> FillPlan:
        """Use LLM to produce a fill plan."""
        fields_json, data_sources_text, user_rules = self._prepare_prompt_inputs(context)

        user_prompt = build_autofill_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            rules=user_rules,
        )

        messages = [
            {"role": "system", "content": AUTOFILL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        model_used = getattr(self._llm_client, "model", None) or getattr(
            self._llm_client, "_model", None
        )
        prompt_chars = len(AUTOFILL_SYSTEM_PROMPT) + len(user_prompt)
        logger.info(
            f"[fill_plan] model={model_used} | "
            f"prompt={prompt_chars:,} chars (~{prompt_chars // 4:,} tokens) | "
            f"fields={len(context.fields)} | "
            f"path={'instructor' if self._has_instructor() else 'raw'}"
        )

        try:
            t0 = time.perf_counter()
            if self._has_instructor():
                result = await self._llm_client.create(
                    response_model=LLMFillResponse,
                    messages=messages,
                    max_retries=2,
                )
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                logger.info(
                    f"[fill_plan] instructor create done in {elapsed_ms:,}ms | "
                    f"filled={len(result.filled_fields)} unfilled={len(result.unfilled_fields)}"
                )
                actions = self._convert_fill_response(context, result)
                return FillPlan(
                    document_id=context.document_id,
                    actions=tuple(actions),
                    model_used=model_used,
                    system_prompt=AUTOFILL_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
            else:
                return await self._llm_plan_raw(context, messages, user_prompt)

        except Exception as e:
            logger.warning(f"LLM plan failed, falling back to candidates: {e}")
            return self._candidate_plan(context)

    async def _llm_plan_raw(
        self,
        context: FormContext,
        messages: list[dict[str, str]],
        user_prompt: str,
    ) -> FillPlan:
        """Fallback: raw JSON completion without Instructor."""
        response = await self._llm_client.complete(
            messages=messages,
            response_format={"type": "json_object"},
        )

        raw_response = response.content
        result = json.loads(raw_response)
        actions = self._parse_llm_result(context, result)
        model_used = getattr(self._llm_client, "model", None) or getattr(
            self._llm_client, "_model", None
        )

        return FillPlan(
            document_id=context.document_id,
            actions=tuple(actions),
            model_used=model_used,
            raw_llm_response=raw_response,
            system_prompt=AUTOFILL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

    def _convert_fill_response(
        self,
        context: FormContext,
        result: LLMFillResponse,
    ) -> list[FieldFillAction]:
        """Convert Instructor-validated LLMFillResponse to FieldFillActions."""
        filled_map: dict[str, LLMFilledField] = {
            f.field_id: f for f in result.filled_fields
        }
        unfilled_set = set(result.unfilled_fields)
        actions: list[FieldFillAction] = []

        for field in context.fields:
            if field.field_id in filled_map:
                entry = filled_map[field.field_id]
                actions.append(FieldFillAction(
                    field_id=field.field_id,
                    action=FillActionType.FILL,
                    value=entry.value,
                    confidence=entry.confidence,
                    source=entry.source,
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

    def _parse_llm_result(
        self,
        context: FormContext,
        result: dict[str, Any],
    ) -> list[FieldFillAction]:
        """Parse raw LLM JSON response into FieldFillActions (fallback path)."""
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

    # ─── Detailed mode ───

    MAX_QUESTION_ROUNDS = 10

    async def plan_turn(
        self,
        context: FormContext,
        conversation_history: list[dict[str, Any]] | None = None,
        just_fill: bool = False,
    ) -> TurnResult:
        if not self._llm_client:
            plan = self._candidate_plan(context)
            return TurnResult(type="fill_plan", plan=plan)

        # Force fill after too many questions to prevent infinite Q&A loops
        history = conversation_history or []
        questions_asked = sum(
            1
            for turn in history
            if turn.get("role") == "assistant"
            and turn.get("type") in ("question", "questions")
        )
        if just_fill or questions_asked >= self.MAX_QUESTION_ROUNDS:
            if questions_asked >= self.MAX_QUESTION_ROUNDS:
                logger.info(
                    f"[plan_turn] forcing fill — {questions_asked} questions reached limit"
                )
            plan = await self._llm_plan(context)
            return TurnResult(type="fill_plan", plan=plan)

        # Reasoning pre-check: skip on first turn (no history to reason about)
        reasoning_meta: tuple[str, str, int] | None = None
        if questions_asked > 0 and self._has_instructor():
            decision, reasoning, reasoning_ms = await self._should_continue_asking(
                context, history, questions_asked
            )
            reasoning_meta = (decision, reasoning, reasoning_ms)
            if decision == "fill":
                logger.info(
                    f"[plan_turn] reasoning pre-check decided 'fill': {reasoning}"
                )
                plan = await self._llm_plan(context)
                return TurnResult(
                    type="fill_plan",
                    plan=plan,
                    reasoning=reasoning,
                    reasoning_decision="fill",
                    reasoning_duration_ms=reasoning_ms,
                )
            # decision == "ask": fall through to _detailed_turn
            logger.info(
                f"[plan_turn] reasoning pre-check decided 'ask': {reasoning}"
            )

        turn_result = await self._detailed_turn(context, history)

        # Attach reasoning metadata if pre-check ran
        if reasoning_meta is not None:
            decision, reasoning, reasoning_ms = reasoning_meta
            turn_result = TurnResult(
                type=turn_result.type,
                questions=turn_result.questions,
                plan=turn_result.plan,
                raw_llm_response=turn_result.raw_llm_response,
                system_prompt=turn_result.system_prompt,
                user_prompt=turn_result.user_prompt,
                model_used=turn_result.model_used,
                reasoning=reasoning,
                reasoning_decision="ask",
                reasoning_duration_ms=reasoning_ms,
            )

        return turn_result

    async def _should_continue_asking(
        self,
        context: FormContext,
        conversation_history: list[dict[str, Any]],
        questions_asked: int,
    ) -> tuple[str, str, int]:
        """Cheap LLM pre-check: should we ask more questions or fill now?

        Returns:
            (decision, reasoning, duration_ms) — decision is "ask" or "fill".
            Falls back to ("ask", "...", 0) on any exception (conservative).
        """
        # Build compact conversation summary
        summary_lines: list[str] = []
        for turn in conversation_history:
            role = turn.get("role", "")
            turn_type = turn.get("type", "")
            if role == "assistant" and turn_type in ("question", "questions"):
                q = turn.get("question", "")
                if q:
                    summary_lines.append(f"Asked: {q}")
            elif role == "user" and turn_type == "answer":
                selected = turn.get("selected_option_ids", [])
                free = turn.get("free_text")
                parts: list[str] = []
                if selected:
                    parts.append(f"selected={', '.join(selected)}")
                if free:
                    parts.append(f'"{free}"')
                if parts:
                    summary_lines.append(f"Answered: {'; '.join(parts)}")

        conversation_summary = "\n".join(summary_lines) if summary_lines else ""

        # Collect data source keys
        data_source_keys: list[str] = []
        for ds in context.data_sources:
            data_source_keys.extend(ds.extracted_fields.keys())

        user_prompt = build_reasoning_prompt(
            total_fields=len(context.fields),
            data_source_keys=data_source_keys,
            questions_asked=questions_asked,
            conversation_summary=conversation_summary,
        )

        messages = [
            {"role": "system", "content": REASONING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        prompt_chars = len(REASONING_SYSTEM_PROMPT) + len(user_prompt)
        logger.info(
            f"[reasoning_precheck] prompt={prompt_chars:,} chars "
            f"(~{prompt_chars // 4:,} tokens) | questions_asked={questions_asked}"
        )

        try:
            t0 = time.perf_counter()
            result = await self._llm_client.create(
                response_model=LLMReasoningResponse,
                messages=messages,
                max_retries=1,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                f"[reasoning_precheck] done in {elapsed_ms:,}ms | "
                f"decision={result.decision} | reasoning={result.reasoning}"
            )
            return (result.decision, result.reasoning, elapsed_ms)
        except Exception as e:
            logger.warning(f"[reasoning_precheck] failed, defaulting to 'ask': {e}")
            return ("ask", f"Pre-check failed: {e}", 0)

    async def _detailed_turn(
        self,
        context: FormContext,
        conversation_history: list[dict[str, Any]],
    ) -> TurnResult:
        """Execute a detailed mode LLM turn."""
        fields_json, data_sources_text, user_rules = self._prepare_prompt_inputs(context)

        history_text = self._format_conversation_history(conversation_history)
        questions_asked = sum(
            1
            for turn in conversation_history
            if turn.get("role") == "assistant"
            and turn.get("type") in ("question", "questions")
        )

        user_prompt = build_detailed_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            conversation_history=history_text,
            rules=user_rules,
            questions_asked=questions_asked,
        )

        messages = [
            {"role": "system", "content": DETAILED_MODE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        model_used = getattr(self._llm_client, "model", None) or getattr(
            self._llm_client, "_model", None
        )
        prompt_chars = len(DETAILED_MODE_SYSTEM_PROMPT) + len(user_prompt)
        logger.info(
            f"[detailed_turn] model={model_used} | "
            f"prompt={prompt_chars:,} chars (~{prompt_chars // 4:,} tokens) | "
            f"fields={len(context.fields)} | "
            f"history_turns={len(conversation_history)} | "
            f"questions_asked={questions_asked}"
        )

        prompt_fields = {
            "system_prompt": DETAILED_MODE_SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "model_used": model_used,
        }

        try:
            # Detailed mode returns either questions or a fill plan.
            # We first try raw completion to inspect the "type" field,
            # then parse with the appropriate schema.
            t0 = time.perf_counter()
            response = await self._llm_client.complete(
                messages=messages,
                response_format={"type": "json_object"},
            )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            raw_response = response.content
            logger.info(
                f"[detailed_turn] LLM done in {elapsed_ms:,}ms | "
                f"response={len(raw_response)} chars | "
                f"tokens: {response.prompt_tokens:,} in + "
                f"{response.completion_tokens:,} out = "
                f"{response.total_tokens:,} total"
            )
            result = json.loads(raw_response)

            if result.get("type") == "questions":
                parsed = LLMDetailedQuestionsResponse(**result)
                questions = self._convert_questions(parsed)
                return TurnResult(
                    type="questions",
                    questions=questions,
                    raw_llm_response=raw_response,
                    **prompt_fields,
                )
            elif result.get("type") == "question":
                parsed_q = LLMDetailedQuestionsResponse(
                    type="questions",
                    questions=[result],
                )
                questions = self._convert_questions(parsed_q)
                return TurnResult(
                    type="questions",
                    questions=questions,
                    raw_llm_response=raw_response,
                    **prompt_fields,
                )
            else:
                parsed_fill = LLMDetailedFillResponse(**result)
                fill_resp = LLMFillResponse(
                    filled_fields=parsed_fill.filled_fields,
                    unfilled_fields=parsed_fill.unfilled_fields,
                    warnings=parsed_fill.warnings,
                )
                actions = self._convert_fill_response(context, fill_resp)
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
                    **prompt_fields,
                )

        except Exception as e:
            logger.warning(f"Detailed turn failed, falling back to fill plan: {e}")
            plan = self._candidate_plan(context)
            return TurnResult(type="fill_plan", plan=plan)

    @staticmethod
    def _convert_questions(
        parsed: LLMDetailedQuestionsResponse,
    ) -> tuple[FieldQuestion, ...]:
        """Convert Instructor-validated questions to domain models."""
        questions: list[FieldQuestion] = []
        for i, q in enumerate(parsed.questions):
            try:
                q_type = QuestionType(q.question_type)
            except ValueError:
                q_type = QuestionType.FREE_TEXT

            options = tuple(
                QuestionOption(id=opt.id, label=opt.label)
                for opt in q.options
            )

            questions.append(FieldQuestion(
                id=q.id or f"q{i}",
                text=q.question,
                type=q_type,
                options=options,
                context=q.context,
            ))

        return tuple(questions)

    # ─── Helpers ───

    @staticmethod
    def _select_relevant_fields(
        context: FormContext,
    ) -> tuple[list[FormFieldSpec], list[FormFieldSpec]]:
        """Partition fields into relevant (full detail) vs rest (compact).

        A field is relevant when its label or any nearby_label text
        overlaps with a data source key (case-insensitive substring).
        """
        ds_keys: set[str] = set()
        for ds in context.data_sources:
            for key in ds.extracted_fields:
                ds_keys.add(key.lower())

        relevant: list[FormFieldSpec] = []
        rest: list[FormFieldSpec] = []

        for field in context.fields:
            label_lower = field.label.lower()
            matched = any(k in label_lower or label_lower in k for k in ds_keys)

            if not matched and field.label_candidates:
                for lc in field.label_candidates:
                    lc_lower = lc.text.lower()
                    if any(k in lc_lower or lc_lower in k for k in ds_keys):
                        matched = True
                        break

            if not matched:
                for mc in context.mapping_candidates:
                    if mc.field_id == field.field_id and mc.score > 0.3:
                        matched = True
                        break

            if matched:
                relevant.append(field)
            else:
                rest.append(field)

        return relevant, rest

    @staticmethod
    def _prepare_prompt_inputs(
        context: FormContext,
    ) -> tuple[str, str, list[str] | None]:
        """Extract prompt inputs from FormContext.

        Uses hybrid format: full detail for fields that match data source
        keys, compact one-liners for the rest (~60% prompt reduction).
        """
        relevant, rest = FillPlanner._select_relevant_fields(context)

        # Full detail for relevant fields (with nearby_labels)
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
            for f in relevant
        ]

        # Compact one-liner list for remaining fields
        compact_lines: list[str] = []
        for f in rest:
            nearby = ""
            if f.label_candidates:
                nearby = " [" + ", ".join(lc.text for lc in f.label_candidates[:1]) + "]"
            compact_lines.append(f"{f.field_id} ({f.field_type}){nearby}")

        fields_json = json.dumps(fields_dicts, indent=2)
        if compact_lines:
            fields_json += (
                "\n\n## Other Fields (fill only if data clearly matches)\n\n"
                + "\n".join(compact_lines)
            )

        # Data sources (unchanged)
        extractions = []
        for ds in context.data_sources:
            entry: dict[str, Any] = {
                "source_name": ds.source_name,
                "source_type": ds.source_type,
                "extracted_fields": ds.extracted_fields,
            }
            if len(ds.extracted_fields) < 3 and ds.raw_text:
                entry["raw_text"] = ds.raw_text
            extractions.append(entry)
        data_sources_text = format_data_sources(extractions)
        user_rules = list(context.rules) if context.rules else None

        return fields_json, data_sources_text, user_rules

    @staticmethod
    def _format_conversation_history(
        conversation: list[dict[str, Any]],
        max_entries: int = 40,
    ) -> str:
        if not conversation:
            return "No previous conversation."

        lines: list[str] = []
        if len(conversation) > max_entries:
            # Truncate from the start but keep complete Q&A pairs.
            # Find the first "assistant" turn after the cut point so we
            # don't start mid-pair (user answer without its question).
            cut = len(conversation) - max_entries
            while cut < len(conversation) and conversation[cut].get("role") != "assistant":
                cut += 1
            if cut > 0:
                lines.append(f"[{cut} earlier Q&A entries omitted]")
                conversation = conversation[cut:]

        for turn in conversation:
            role = turn.get("role", "unknown")
            turn_type = turn.get("type", "unknown")

            if role == "assistant" and turn_type == "question":
                q_id = turn.get("question_id", "")
                q = turn.get("question", "")
                prefix = f"[{q_id}] " if q_id else ""
                lines.append(f"Assistant asked: {prefix}{q}")
                opts = turn.get("options", [])
                if opts:
                    for opt in opts:
                        lines.append(f"  - {opt.get('label', opt.get('id', ''))}")
            elif role == "user" and turn_type == "answer":
                q_id = turn.get("question_id", "")
                prefix = f"[{q_id}] " if q_id else ""
                selected = turn.get("selected_option_ids", [])
                free = turn.get("free_text")
                if selected:
                    lines.append(f"User selected: {prefix}{', '.join(selected)}")
                if free:
                    lines.append(f"User answered: {prefix}{free}")

        return "\n".join(lines) if lines else "No previous conversation."
