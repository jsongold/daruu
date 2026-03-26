"""FillPlanner — plans field fill actions using LiteLLM + Instructor.

Uses Instructor for structured output with Pydantic validation and
automatic retries. Falls back to mapping-candidate-based planning
when no LLM client is available.

Supports two modes:
- plan(): Quick fill using data sources
- plan_with_answers(): Re-fill incorporating user answers
"""

import json
import logging
import time
from typing import Any

from app.domain.models.fill_plan import (
    FieldFillAction,
    FillActionType,
    FillPlan,
)
from app.domain.models.form_context import FormContext, FormFieldSpec
from app.services.fill_planner.schemas import (
    LLMFilledField,
    LLMFillResponse,
)
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    build_autofill_prompt,
    build_refill_prompt,
    format_data_sources,
)

logger = logging.getLogger(__name__)


class FillPlanner:
    """Plans field fill actions using LLM.

    Accepts any client that implements:
    - complete(messages, response_format) for raw completions
    - create(response_model, messages) for Instructor structured output
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm_client = llm_client
        self._specialized_prompt: str | None = None

    def set_specialized_prompt(self, prompt: str | None) -> None:
        """Set a form-specific prompt for field identification context.

        When set, the specialized prompt IS the system prompt (no bridge).
        """
        self._specialized_prompt = prompt

    def _has_instructor(self) -> bool:
        """Check if the client supports Instructor's create() method."""
        return hasattr(self._llm_client, "create")

    async def plan(self, context: FormContext) -> FillPlan:
        if self._llm_client:
            return await self._llm_plan(context)
        return self._candidate_plan(context)

    async def plan_with_answers(
        self,
        context: FormContext,
        answers: list[dict[str, Any]],
    ) -> FillPlan:
        """Re-fill with user answers as high-confidence overrides.

        Same as _llm_plan() but the user prompt includes an extra section
        with user-provided answers at high confidence (>= 0.95).
        """
        if not self._llm_client:
            return self._candidate_plan(context)

        fields_json, data_sources_text, user_rules = self._prepare_prompt_inputs(context)

        # Format answers text
        answers_lines: list[str] = []
        for a in answers:
            q_text = a.get("question_text", a.get("question_id", ""))
            selected = a.get("selected_option_ids", [])
            free_text = a.get("free_text")
            parts: list[str] = []
            if selected:
                parts.append(f"selected: {', '.join(selected)}")
            if free_text:
                parts.append(f'"{free_text}"')
            answer_str = "; ".join(parts) if parts else "(no answer)"
            answers_lines.append(f"- Q: {q_text} -> A: {answer_str}")
        answers_text = "\n".join(answers_lines) if answers_lines else "No answers provided."

        user_prompt = build_refill_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            answers_text=answers_text,
            rules=user_rules,
        )

        system_prompt = self._specialized_prompt or AUTOFILL_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        model_used = getattr(self._llm_client, "model", None) or getattr(
            self._llm_client, "_model", None
        )
        prompt_chars = len(system_prompt) + len(user_prompt)
        logger.info(
            f"[refill_plan] model={model_used} | "
            f"prompt={prompt_chars:,} chars (~{prompt_chars // 4:,} tokens) | "
            f"fields={len(context.fields)} | answers={len(answers)}"
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
                    f"[refill_plan] done in {elapsed_ms:,}ms | "
                    f"filled={len(result.filled_fields)}"
                )
                actions = self._convert_fill_response(context, result)
                return FillPlan(
                    document_id=context.document_id,
                    actions=tuple(actions),
                    model_used=model_used,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            else:
                return await self._llm_plan_raw(
                    context, messages, user_prompt, system_prompt
                )
        except Exception as e:
            logger.warning(f"Refill plan failed, falling back to candidates: {e}")
            return self._candidate_plan(context)

    async def _llm_plan(self, context: FormContext) -> FillPlan:
        """Use LLM to produce a fill plan."""
        fields_json, data_sources_text, user_rules = self._prepare_prompt_inputs(context)

        user_prompt = build_autofill_prompt(
            fields_json=fields_json,
            data_sources_text=data_sources_text,
            rules=user_rules,
        )

        system_prompt = self._specialized_prompt or AUTOFILL_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        model_used = getattr(self._llm_client, "model", None) or getattr(
            self._llm_client, "_model", None
        )
        prompt_chars = len(system_prompt) + len(user_prompt)
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
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            else:
                return await self._llm_plan_raw(context, messages, user_prompt, system_prompt)

        except Exception as e:
            logger.warning(f"LLM plan failed, falling back to candidates: {e}")
            return self._candidate_plan(context)

    async def _llm_plan_raw(
        self,
        context: FormContext,
        messages: list[dict[str, str]],
        user_prompt: str,
        system_prompt: str | None = None,
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
            system_prompt=system_prompt or AUTOFILL_SYSTEM_PROMPT,
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

    # ─── Helpers ───

    @staticmethod
    def _select_relevant_fields(
        context: FormContext,
    ) -> tuple[list[FormFieldSpec], list[FormFieldSpec]]:
        """Partition fields into relevant (full detail) vs rest (compact).

        A field is relevant when its label or any nearby_label text
        overlaps with a data source key (case-insensitive substring).

        When data sources have no extracted_fields (e.g. raw text only),
        all fields are returned as relevant so the LLM gets full
        nearby_labels context for every field.
        """
        ds_keys: set[str] = set()
        for ds in context.data_sources:
            for key in ds.extracted_fields:
                ds_keys.add(key.lower())

        # If no structured keys exist, return all fields as relevant
        # so the LLM gets nearby_labels context for field identification.
        if not ds_keys:
            return list(context.fields), []

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
