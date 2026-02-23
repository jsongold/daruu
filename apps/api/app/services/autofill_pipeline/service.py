"""AutofillPipelineService — orchestrates the To-Be autofill pipeline.

Pipeline:
  1. (Parallel) FormContextBuilder.build() + RuleAnalyzer.analyze()
  2. Merge rule_snippets into FormContext
  3. FillPlanner.plan(context) -> FillPlan
  4. FormRenderer.render(plan, pdf_ref) -> RenderReport
  5. Return AutofillPipelineResult
"""

import asyncio
import logging
import time

from app.domain.models.form_context import FormContext, FormFieldSpec
from app.domain.protocols.correction_tracker import CorrectionTrackerProtocol
from app.domain.protocols.fill_planner import FillPlannerProtocol
from app.domain.protocols.form_context_builder import FormContextBuilderProtocol
from app.domain.protocols.form_renderer import FormRendererProtocol
from app.domain.protocols.rule_analyzer import RuleAnalyzerProtocol
from app.services.autofill_pipeline.models import AutofillPipelineResult

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
            AutofillPipelineResult with context, plan, and report.
        """
        start_time = time.time()

        # Step 1: Parallel — build context + analyze rules
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

        # Step 2: Merge rule snippets into context rules
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

        # Step 3: Plan
        plan = await self._fill_planner.plan(context)

        # Step 4: Render
        report = await self._form_renderer.render(
            plan=plan,
            target_document_ref=target_document_ref,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        return AutofillPipelineResult(
            context=context,
            plan=plan,
            report=report,
            processing_time_ms=processing_time_ms,
        )
