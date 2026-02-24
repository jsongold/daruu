"""AutofillPipelineService — orchestrates the To-Be autofill pipeline.

Pipeline:
  1. (Parallel) FormContextBuilder.build() + RuleAnalyzer.analyze()
  2. Merge rule_snippets into FormContext
  3. FillPlanner.plan(context) -> FillPlan
  4. FormRenderer.render(plan, pdf_ref) -> RenderReport
  5. Return AutofillPipelineResult with per-step logs
"""

import asyncio
import logging
import time

from app.domain.models.fill_plan import FillActionType
from app.domain.models.form_context import FormContext, FormFieldSpec
from app.domain.protocols.correction_tracker import CorrectionTrackerProtocol
from app.domain.protocols.fill_planner import FillPlannerProtocol
from app.domain.protocols.form_context_builder import FormContextBuilderProtocol
from app.domain.protocols.form_renderer import FormRendererProtocol
from app.domain.protocols.rule_analyzer import RuleAnalyzerProtocol
from app.services.autofill_pipeline.models import AutofillPipelineResult
from app.services.autofill_pipeline.step_log import PipelineStepLog

logger = logging.getLogger(__name__)


class AutofillPipelineService:
    """Orchestrates the full autofill pipeline.

    Composes FormContextBuilder, RuleAnalyzer, FillPlanner,
    FormRenderer, and CorrectionTracker into a single pipeline.
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
        start_time = time.time()
        step_logs: list[PipelineStepLog] = []

        # Step 1: Parallel — build context + analyze rules
        t0 = time.time()
        context_task = self._context_builder.build(
            document_id=document_id,
            conversation_id=conversation_id,
            field_hints=fields,
            user_rules=user_rules,
        )
        rule_task = self._rule_analyzer.analyze(
            rule_docs=rule_docs,
            field_hints=fields,
        )

        context, rule_snippets = await asyncio.gather(context_task, rule_task)
        context_duration = int((time.time() - t0) * 1000)

        step_logs.append(PipelineStepLog(
            step_name="context_build",
            status="success",
            duration_ms=context_duration,
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
        t1 = time.time()
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
        rule_duration = int((time.time() - t1) * 1000)

        all_rules = list(context.rules) if context.rules else []
        step_logs.append(PipelineStepLog(
            step_name="rule_analyze",
            status="success",
            duration_ms=rule_duration,
            summary=f"{len(all_rules)} rules",
            details={
                "rules_count": len(all_rules),
                "rules": all_rules,
            },
        ))

        # Step 3: Plan
        t2 = time.time()
        plan = await self._fill_planner.plan(context)
        plan_duration = int((time.time() - t2) * 1000)

        fill_count = sum(1 for a in plan.actions if a.action == FillActionType.FILL)
        skip_count = sum(1 for a in plan.actions if a.action == FillActionType.SKIP)
        ask_user_count = sum(
            1 for a in plan.actions if a.action == FillActionType.ASK_USER
        )

        step_logs.append(PipelineStepLog(
            step_name="fill_plan",
            status="success",
            duration_ms=plan_duration,
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
        t3 = time.time()
        report = await self._form_renderer.render(
            plan=plan,
            target_document_ref=target_document_ref,
        )
        render_duration = int((time.time() - t3) * 1000)

        step_logs.append(PipelineStepLog(
            step_name="render",
            status="success",
            duration_ms=render_duration,
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

        processing_time_ms = int((time.time() - start_time) * 1000)

        return AutofillPipelineResult(
            context=context,
            plan=plan,
            report=report,
            processing_time_ms=processing_time_ms,
            step_logs=tuple(step_logs),
        )
