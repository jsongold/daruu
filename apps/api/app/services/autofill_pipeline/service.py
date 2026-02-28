"""AutofillPipelineService — orchestrates the To-Be autofill pipeline.

Pipeline:
  1. (Parallel) FormContextBuilder.build() + RuleAnalyzer.analyze()
  2. Merge rule_snippets into FormContext
  3. FillPlanner.plan(context) -> FillPlan
  4. FormRenderer.render(plan, pdf_ref) -> RenderReport
  5. Return AutofillPipelineResult with per-step logs

For Detailed mode, also supports multi-turn Q&A via autofill_turn().
"""

import asyncio
import logging
from typing import Any

from app.infrastructure.observability.stopwatch import StopWatch

from app.domain.models.fill_plan import FillActionType
from app.domain.models.form_context import FormContext, FormFieldSpec
from app.domain.protocols.correction_tracker import CorrectionTrackerProtocol
from app.domain.protocols.fill_planner import FillPlannerProtocol
from app.domain.protocols.form_context_builder import FormContextBuilderProtocol
from app.domain.protocols.form_renderer import FormRendererProtocol
from app.domain.protocols.rule_analyzer import RuleAnalyzerProtocol
from app.services.autofill_pipeline.models import AutofillPipelineResult
from app.services.autofill_pipeline.step_log import PipelineStepLog
from app.services.fill_planner.planner import TurnResult

logger = logging.getLogger(__name__)


class AutofillPipelineService:
    """Orchestrates the full autofill pipeline.

    Composes FormContextBuilder, RuleAnalyzer, FillPlanner,
    FormRenderer, and CorrectionTracker into a single pipeline.

    For detailed mode, context is cached after the first turn so
    subsequent turns only pay for the LLM planning call.
    """

    def __init__(
        self,
        context_builder: FormContextBuilderProtocol,
        fill_planner: FillPlannerProtocol,
        form_renderer: FormRendererProtocol,
        rule_analyzer: RuleAnalyzerProtocol,
        correction_tracker: CorrectionTrackerProtocol,
    ) -> None:
        self._context_builder = context_builder
        self._fill_planner = fill_planner
        self._form_renderer = form_renderer
        self._rule_analyzer = rule_analyzer
        self._correction_tracker = correction_tracker
        # Cache context per (document_id, conversation_id) for turn reuse
        self._turn_context_cache: dict[tuple[str, str], FormContext] = {}

    async def autofill(
        self,
        document_id: str,
        conversation_id: str,
        fields: tuple[FormFieldSpec, ...],
        target_document_ref: str,
        user_rules: tuple[str, ...] = (),
        rule_docs: tuple[str, ...] = (),
    ) -> AutofillPipelineResult:
        """Run the full autofill pipeline.

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

        step_logs.append(PipelineStepLog(
            step_name="fill_plan",
            status="success",
            duration_ms=sw.laps["fill_plan"],
            summary=f"{fill_count} fill, {skip_count} skip, {ask_user_count} ask_user",
            details={
                "model_used": plan.model_used,
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
        conversation_history: list[dict[str, Any]] | None = None,
        just_fill: bool = False,
    ) -> tuple[TurnResult, tuple[PipelineStepLog, ...], AutofillPipelineResult | None]:
        """Execute a single turn in detailed autofill mode.

        Returns:
            Tuple of (TurnResult, step_logs, pipeline_result).
            pipeline_result is only set when TurnResult.type == "fill_plan".
        """
        sw = StopWatch()
        step_logs: list[PipelineStepLog] = []

        # Reuse cached context for subsequent turns (context + rules don't
        # change between Q&A turns for the same document/conversation).
        cache_key = (document_id, conversation_id)
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
            # Step 1: Build context (same as quick mode)
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

            # Step 2: Merge rules
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

        # Step 3: Plan turn (may return question or fill plan)
        with sw.lap("fill_plan_turn"):
            turn_result = await self._fill_planner.plan_turn(
                context,
                conversation_history=conversation_history,
                just_fill=just_fill,
            )

        step_logs.append(PipelineStepLog(
            step_name="fill_plan_turn",
            status="success",
            duration_ms=sw.laps["fill_plan_turn"],
            summary=f"type={turn_result.type}",
            details={
                "turn_type": turn_result.type,
                "model_used": turn_result.model_used,
                "system_prompt": turn_result.system_prompt,
                "user_prompt": turn_result.user_prompt,
                "raw_llm_response": turn_result.raw_llm_response,
            },
        ))

        # Step 4: If fill plan, render
        pipeline_result: AutofillPipelineResult | None = None
        if turn_result.type == "fill_plan" and turn_result.plan:
            with sw.lap("render"):
                report = await self._form_renderer.render(
                    plan=turn_result.plan,
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
                },
            ))

            pipeline_result = AutofillPipelineResult(
                context=context,
                plan=turn_result.plan,
                report=report,
                processing_time_ms=sw.total_ms,
                step_logs=tuple(step_logs),
            )

        return turn_result, tuple(step_logs), pipeline_result
