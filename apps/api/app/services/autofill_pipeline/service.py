"""AutofillPipelineService — orchestrates the autofill pipeline.

Pipeline (quick mode):
  1. (Parallel) FormContextBuilder.build() + RuleAnalyzer.analyze()
  2. Merge rule_snippets into FormContext
  3. FillPlanner.plan(context) -> FillPlan
  4. FormRenderer.render(plan, pdf_ref) -> RenderReport
  5. Return AutofillPipelineResult with per-step logs

Fill-first pipeline (detailed mode):
  Turn 1 (no answers):
    1. Build context + rules [parallel] -> cache
    2. PromptGenerator.generate() [SYNC, blocking]
    3. FillPlanner.plan(context) -> draft FillPlan
    4. FormRenderer.render(plan) -> draft PDF
    5. QuestionGenerator.generate(plan, context) -> questions
    6. Return: (plan, questions, pipeline_result, step_logs)

  Turn 2 (with answers):
    1. Load context + prompt from cache
    2. FillPlanner.plan_with_answers(context, answers)
    3. FormRenderer.render(plan) -> final PDF
    4. Return: (plan, (), pipeline_result, step_logs)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.infrastructure.observability.stopwatch import StopWatch

from app.domain.models.fill_plan import (
    FillActionType,
    FillPlan,
    FieldQuestion,
)
from app.domain.models.form_context import FormContext, FormFieldSpec
from app.domain.protocols.correction_tracker import CorrectionTrackerProtocol
from app.domain.protocols.fill_planner import FillPlannerProtocol
from app.domain.protocols.form_context_builder import FormContextBuilderProtocol
from app.domain.protocols.form_renderer import FormRendererProtocol
from app.domain.protocols.rule_analyzer import RuleAnalyzerProtocol
from app.services.autofill_pipeline.models import AutofillPipelineResult
from app.services.autofill_pipeline.step_log import PipelineStepLog
from app.services.prompt_generator import PromptGenerator, PromptStore
from app.services.question_generator import QuestionGenerator

logger = logging.getLogger(__name__)


class AutofillPipelineService:
    """Orchestrates the full autofill pipeline.

    Composes FormContextBuilder, RuleAnalyzer, FillPlanner,
    FormRenderer, and CorrectionTracker into a single pipeline.

    For detailed mode, uses a fill-first pattern:
    draft fill -> generate questions -> user answers -> final fill.
    Context and prompts are cached between turns.
    """

    def __init__(
        self,
        context_builder: FormContextBuilderProtocol,
        fill_planner: FillPlannerProtocol,
        form_renderer: FormRendererProtocol,
        rule_analyzer: RuleAnalyzerProtocol,
        correction_tracker: CorrectionTrackerProtocol,
        prompt_generator: PromptGenerator | None = None,
        prompt_store: PromptStore | None = None,
        question_generator: QuestionGenerator | None = None,
    ) -> None:
        self._context_builder = context_builder
        self._fill_planner = fill_planner
        self._form_renderer = form_renderer
        self._rule_analyzer = rule_analyzer
        self._correction_tracker = correction_tracker
        self._prompt_generator = prompt_generator
        self._prompt_store = prompt_store
        self._question_generator = question_generator
        # Cache context per (document_id, conversation_id) for turn reuse
        self._turn_context_cache: dict[tuple[str, str], FormContext] = {}
        # Cache specialized prompt per (document_id, conversation_id)
        self._turn_prompt_cache: dict[tuple[str, str], str | None] = {}

    async def autofill(
        self,
        document_id: str,
        conversation_id: str,
        fields: tuple[FormFieldSpec, ...],
        target_document_ref: str,
        user_rules: tuple[str, ...] = (),
        rule_docs: tuple[str, ...] = (),
    ) -> AutofillPipelineResult:
        """Run the full autofill pipeline (quick mode).

        Args:
            document_id: Target document ID.
            conversation_id: Conversation ID with data sources.
            fields: Form field specifications.
            target_document_ref: Storage path to the target PDF.
            user_rules: Optional user-provided rules (strings).
            rule_docs: Optional rule document references for RuleAnalyzer.

        Returns:
            AutofillPipelineResult with context, plan, report, and step_logs.
        """
        sw = StopWatch()
        step_logs: list[PipelineStepLog] = []

        # Step 1: Parallel — build context + analyze rules
        with sw.lap("context_build"):
            context_task = self._context_builder.build(
                document_id=document_id,
                conversation_id=conversation_id,
                field_hints=fields,
                user_rules=user_rules,
            )
            rule_task = self._rule_analyzer.analyze(
                rule_docs=rule_docs,
                field_hints=fields,
                skip_embedding=True,
            )
            context, rule_snippets = await asyncio.gather(context_task, rule_task)

        step_logs.append(PipelineStepLog(
            step_name="context_build",
            status="success",
            duration_ms=sw.laps["context_build"],
            summary=f"{len(context.data_sources)} sources, {len(context.mapping_candidates)} candidates",
            details={
                "data_sources_count": len(context.data_sources),
                "data_sources": [
                    {
                        "name": ds.source_name,
                        "type": ds.source_type,
                        "field_count": len(ds.extracted_fields),
                    }
                    for ds in context.data_sources
                ],
                "candidates_count": len(context.mapping_candidates),
                "top_candidates": [
                    {
                        "field_id": mc.field_id,
                        "source_key": mc.source_key,
                        "score": mc.score,
                    }
                    for mc in sorted(
                        context.mapping_candidates,
                        key=lambda c: c.score,
                        reverse=True,
                    )[:10]
                ],
            },
        ))

        # Step 2: Merge rule snippets into context rules
        with sw.lap("rule_analyze"):
            if rule_snippets:
                merged_rules = context.rules + tuple(
                    snippet.rule_text for snippet in rule_snippets
                )
                context = FormContext(
                    document_id=context.document_id,
                    conversation_id=context.conversation_id,
                    fields=context.fields,
                    data_sources=context.data_sources,
                    mapping_candidates=context.mapping_candidates,
                    rules=merged_rules,
                )

        all_rules = list(context.rules) if context.rules else []
        step_logs.append(PipelineStepLog(
            step_name="rule_analyze",
            status="success",
            duration_ms=sw.laps["rule_analyze"],
            summary=f"{len(all_rules)} rules",
            details={
                "rules_count": len(all_rules),
                "rules": all_rules,
            },
        ))

        # Step 3: Plan
        with sw.lap("fill_plan"):
            plan = await self._fill_planner.plan(context)

        fill_count = sum(1 for a in plan.actions if a.action == FillActionType.FILL)
        skip_count = sum(1 for a in plan.actions if a.action == FillActionType.SKIP)
        ask_user_count = sum(
            1 for a in plan.actions if a.action == FillActionType.ASK_USER
        )

        plan_prompt_chars = (
            (len(plan.system_prompt) if plan.system_prompt else 0)
            + (len(plan.user_prompt) if plan.user_prompt else 0)
        )
        plan_response_chars = len(plan.raw_llm_response) if plan.raw_llm_response else 0
        step_logs.append(PipelineStepLog(
            step_name="fill_plan",
            status="success",
            duration_ms=sw.laps["fill_plan"],
            summary=f"{fill_count} fill, {skip_count} skip, {ask_user_count} ask_user",
            details={
                "model_used": plan.model_used,
                "prompt_chars": plan_prompt_chars,
                "prompt_tokens_est": plan_prompt_chars // 4,
                "response_chars": plan_response_chars,
                "system_prompt": plan.system_prompt,
                "user_prompt": plan.user_prompt,
                "raw_llm_response": plan.raw_llm_response,
                "fill_count": fill_count,
                "skip_count": skip_count,
                "ask_user_count": ask_user_count,
                "actions": [
                    {
                        "field_id": a.field_id,
                        "action": a.action.value,
                        "value": a.value,
                        "confidence": a.confidence,
                        "reason": a.reason,
                    }
                    for a in plan.actions
                ],
            },
        ))

        # Step 4: Render
        with sw.lap("render"):
            report = await self._form_renderer.render(
                plan=plan,
                target_document_ref=target_document_ref,
            )

        step_logs.append(PipelineStepLog(
            step_name="render",
            status="success",
            duration_ms=sw.laps["render"],
            summary=f"{report.filled_count} filled, {report.failed_count} failed",
            details={
                "filled_count": report.filled_count,
                "failed_count": report.failed_count,
                "filled_document_ref": report.filled_document_ref,
                "field_results": [
                    {
                        "field_id": fr.field_id,
                        "status": fr.status.value,
                        "value_written": fr.value_written,
                    }
                    for fr in report.field_results
                ],
            },
        ))

        return AutofillPipelineResult(
            context=context,
            plan=plan,
            report=report,
            processing_time_ms=sw.total_ms,
            step_logs=tuple(step_logs),
        )

    async def autofill_turn(
        self,
        document_id: str,
        conversation_id: str,
        fields: tuple[FormFieldSpec, ...],
        target_document_ref: str,
        user_rules: tuple[str, ...] = (),
        rule_docs: tuple[str, ...] = (),
        answers: list[dict[str, Any]] | None = None,
    ) -> tuple[FillPlan, tuple[FieldQuestion, ...], AutofillPipelineResult | None, tuple[PipelineStepLog, ...]]:
        """Execute a single turn in detailed autofill mode (fill-first).

        Turn 1 (answers=None): draft fill + questions.
        Turn 2 (answers provided): final fill with user answers.

        Returns:
            Tuple of (plan, questions, pipeline_result, step_logs).
        """
        sw = StopWatch()
        step_logs: list[PipelineStepLog] = []
        cache_key = (document_id, conversation_id)

        # ── Load or build context ──
        cached_context = self._turn_context_cache.get(cache_key)

        if cached_context is not None:
            context = cached_context
            step_logs.append(PipelineStepLog(
                step_name="context_build",
                status="success",
                duration_ms=0,
                summary="cached",
                details={"cached": True},
            ))
        else:
            with sw.lap("context_build"):
                context_task = self._context_builder.build(
                    document_id=document_id,
                    conversation_id=conversation_id,
                    field_hints=fields,
                    user_rules=user_rules,
                )
                rule_task = self._rule_analyzer.analyze(
                    rule_docs=rule_docs,
                    field_hints=fields,
                    skip_embedding=True,
                )
                context, rule_snippets = await asyncio.gather(context_task, rule_task)

            step_logs.append(PipelineStepLog(
                step_name="context_build",
                status="success",
                duration_ms=sw.laps["context_build"],
                summary=f"{len(context.data_sources)} sources, {len(context.mapping_candidates)} candidates",
                details={
                    "data_sources_count": len(context.data_sources),
                    "candidates_count": len(context.mapping_candidates),
                },
            ))

            # Merge rules
            if rule_snippets:
                merged_rules = context.rules + tuple(
                    snippet.rule_text for snippet in rule_snippets
                )
                context = FormContext(
                    document_id=context.document_id,
                    conversation_id=context.conversation_id,
                    fields=context.fields,
                    data_sources=context.data_sources,
                    mapping_candidates=context.mapping_candidates,
                    rules=merged_rules,
                )

            self._turn_context_cache[cache_key] = context

            # ── Generate prompt (SYNC, blocking) ──
            prompt = await self._generate_prompt_sync(
                document_id, context, step_logs, sw
            )
            if prompt:
                self._fill_planner.set_specialized_prompt(prompt)
            self._turn_prompt_cache[cache_key] = prompt

        # Restore cached prompt for subsequent turns
        cached_prompt = self._turn_prompt_cache.get(cache_key)
        if cached_prompt and cached_context is not None:
            self._fill_planner.set_specialized_prompt(cached_prompt)

        # ── Turn 2: Re-fill with answers ──
        if answers is not None:
            return await self._turn_with_answers(
                context, answers, target_document_ref, sw, step_logs
            )

        # ── Turn 1: Draft fill + question generation ──
        return await self._turn_draft_fill(
            context, target_document_ref, sw, step_logs
        )

    async def _turn_draft_fill(
        self,
        context: FormContext,
        target_document_ref: str,
        sw: StopWatch,
        step_logs: list[PipelineStepLog],
    ) -> tuple[FillPlan, tuple[FieldQuestion, ...], AutofillPipelineResult | None, tuple[PipelineStepLog, ...]]:
        """Turn 1: Draft fill, render, then generate questions."""
        # Step: Draft fill
        with sw.lap("fill_plan"):
            plan = await self._fill_planner.plan(context)

        self._append_plan_log(plan, sw.laps["fill_plan"], step_logs)

        # Step: Render draft
        with sw.lap("render"):
            report = await self._form_renderer.render(
                plan=plan,
                target_document_ref=target_document_ref,
            )

        step_logs.append(PipelineStepLog(
            step_name="render",
            status="success",
            duration_ms=sw.laps["render"],
            summary=f"{report.filled_count} filled, {report.failed_count} failed (draft)",
            details={
                "filled_count": report.filled_count,
                "failed_count": report.failed_count,
                "filled_document_ref": report.filled_document_ref,
                "is_draft": True,
            },
        ))

        pipeline_result = AutofillPipelineResult(
            context=context,
            plan=plan,
            report=report,
            processing_time_ms=sw.total_ms,
            step_logs=tuple(step_logs),
        )

        # Step: Generate questions from fill gaps
        questions: tuple[FieldQuestion, ...] = ()
        if self._question_generator:
            with sw.lap("question_gen"):
                questions = await self._question_generator.generate(plan, context)

            step_logs.append(PipelineStepLog(
                step_name="question_gen",
                status="success",
                duration_ms=sw.laps["question_gen"],
                summary=f"{len(questions)} questions generated",
                details={
                    "question_count": len(questions),
                    "questions": [
                        {"id": q.id, "text": q.text, "type": q.type.value}
                        for q in questions
                    ],
                },
            ))

        return plan, questions, pipeline_result, tuple(step_logs)

    async def _turn_with_answers(
        self,
        context: FormContext,
        answers: list[dict[str, Any]],
        target_document_ref: str,
        sw: StopWatch,
        step_logs: list[PipelineStepLog],
    ) -> tuple[FillPlan, tuple[FieldQuestion, ...], AutofillPipelineResult | None, tuple[PipelineStepLog, ...]]:
        """Turn 2: Re-fill with user answers, then render final PDF."""
        # Step: Re-fill with answers
        with sw.lap("fill_plan"):
            plan = await self._fill_planner.plan_with_answers(context, answers)

        self._append_plan_log(plan, sw.laps["fill_plan"], step_logs)

        # Step: Render final
        with sw.lap("render"):
            report = await self._form_renderer.render(
                plan=plan,
                target_document_ref=target_document_ref,
            )

        step_logs.append(PipelineStepLog(
            step_name="render",
            status="success",
            duration_ms=sw.laps["render"],
            summary=f"{report.filled_count} filled, {report.failed_count} failed (final)",
            details={
                "filled_count": report.filled_count,
                "failed_count": report.failed_count,
                "filled_document_ref": report.filled_document_ref,
                "is_draft": False,
            },
        ))

        pipeline_result = AutofillPipelineResult(
            context=context,
            plan=plan,
            report=report,
            processing_time_ms=sw.total_ms,
            step_logs=tuple(step_logs),
        )

        return plan, (), pipeline_result, tuple(step_logs)

    async def _generate_prompt_sync(
        self,
        document_id: str,
        context: FormContext,
        step_logs: list[PipelineStepLog],
        sw: StopWatch,
    ) -> str | None:
        """Generate specialized prompt synchronously (blocking).

        Checks PromptStore cache first, then falls back to LLM generation.
        """
        # Check cache first
        cached = self._try_cached_prompt(context)
        if cached:
            step_logs.append(PipelineStepLog(
                step_name="prompt_generate",
                status="success",
                duration_ms=0,
                summary="cache_hit",
                details={"cached": True},
            ))
            return cached

        if not self._prompt_generator:
            return None

        try:
            with sw.lap("prompt_generate"):
                result = await self._prompt_generator.generate(document_id, context)

            # Cache for future reuse
            if self._prompt_store:
                form_hash = self._prompt_store.compute_form_hash(context.fields)
                self._prompt_store.store(
                    form_hash=form_hash,
                    prompt=result.specialized_prompt,
                    field_count=len(result.field_mapping),
                )

            step_logs.append(PipelineStepLog(
                step_name="prompt_generate",
                status="success",
                duration_ms=result.generation_time_ms,
                summary=f"validated={result.validation_passed}",
                details={
                    "model_used": result.model_used,
                    "generation_time_ms": result.generation_time_ms,
                    "validation_passed": result.validation_passed,
                    "missing_field_ids": list(result.missing_field_ids),
                    "prompt_length": len(result.specialized_prompt),
                    "specialized_prompt": result.specialized_prompt,
                },
            ))
            return result.specialized_prompt

        except Exception as e:
            logger.warning(f"Prompt generation failed: {e}")
            step_logs.append(PipelineStepLog(
                step_name="prompt_generate",
                status="error",
                duration_ms=sw.laps.get("prompt_generate", 0),
                summary=f"failed: {e}",
                details={"error": str(e)},
            ))
            return None

    def _try_cached_prompt(self, context: FormContext) -> str | None:
        """Check PromptStore for a cached prompt matching this form."""
        if not self._prompt_store:
            return None
        form_hash = self._prompt_store.compute_form_hash(context.fields)
        cached = self._prompt_store.find_similar(form_hash)
        if cached:
            return cached[0]
        return None

    @staticmethod
    def _append_plan_log(
        plan: FillPlan,
        duration_ms: int,
        step_logs: list[PipelineStepLog],
    ) -> None:
        """Append a fill_plan step log."""
        fill_count = sum(1 for a in plan.actions if a.action == FillActionType.FILL)
        skip_count = sum(1 for a in plan.actions if a.action == FillActionType.SKIP)

        plan_prompt_chars = (
            (len(plan.system_prompt) if plan.system_prompt else 0)
            + (len(plan.user_prompt) if plan.user_prompt else 0)
        )
        step_logs.append(PipelineStepLog(
            step_name="fill_plan",
            status="success",
            duration_ms=duration_ms,
            summary=f"{fill_count} fill, {skip_count} skip",
            details={
                "model_used": plan.model_used,
                "prompt_chars": plan_prompt_chars,
                "prompt_tokens_est": plan_prompt_chars // 4,
                "system_prompt": plan.system_prompt,
                "user_prompt": plan.user_prompt,
                "raw_llm_response": plan.raw_llm_response,
                "fill_count": fill_count,
                "skip_count": skip_count,
                "actions": [
                    {
                        "field_id": a.field_id,
                        "action": a.action.value,
                        "value": a.value,
                        "confidence": a.confidence,
                        "reason": a.reason,
                    }
                    for a in plan.actions
                ],
            },
        ))
