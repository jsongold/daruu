"""FormRenderer — wraps existing FillService.fill().

Converts FillPlan actions into FillRequest/FillValue tuples
and delegates to the existing FillService for PDF rendering.
"""

import logging
from typing import Any

from app.domain.models.fill_plan import FillActionType, FillPlan
from app.domain.models.render_report import (
    FieldRenderResult,
    RenderReport,
    RenderStatus,
)
from app.models.fill import FillRequest, FillValue
from app.services.fill.service import FillService

logger = logging.getLogger(__name__)


class FormRenderer:
    """Renders a FillPlan into a PDF document.

    Wraps FillService.fill() — converts FillPlan actions (only 'fill' actions)
    into a FillRequest with FillValue tuples and delegates to FillService.
    """

    def __init__(self, fill_service: FillService) -> None:
        self._fill_service = fill_service

    async def render(
        self,
        plan: FillPlan,
        target_document_ref: str,
        render_params: dict[str, Any] | None = None,
    ) -> RenderReport:
        """Render the fill plan into a PDF document.

        Args:
            plan: FillPlan with per-field actions.
            target_document_ref: Storage reference to the target PDF.
            render_params: Optional rendering parameters.

        Returns:
            RenderReport with filled document reference and per-field results.
        """
        fill_actions = [a for a in plan.actions if a.action == FillActionType.FILL and a.value]

        if not fill_actions:
            return RenderReport(
                success=True,
                filled_document_ref=None,
                field_results=tuple(
                    FieldRenderResult(
                        field_id=a.field_id,
                        status=RenderStatus.SKIPPED,
                    )
                    for a in plan.actions
                ),
                filled_count=0,
                failed_count=0,
            )

        fill_values = tuple(
            FillValue(
                field_id=a.field_id,
                value=a.value,
            )
            for a in fill_actions
        )

        fill_request = FillRequest(
            target_document_ref=target_document_ref,
            fields=fill_values,
        )

        try:
            fill_result = await self._fill_service.fill(fill_request)
        except Exception as e:
            logger.exception(f"FillService.fill() failed: {e}")
            return RenderReport(
                success=False,
                error_message=str(e),
                field_results=tuple(
                    FieldRenderResult(
                        field_id=a.field_id,
                        status=RenderStatus.FAILED,
                        error_message=str(e),
                    )
                    for a in fill_actions
                ),
                failed_count=len(fill_actions),
            )

        fill_result_map = {r.field_id: r for r in fill_result.field_results}
        filled_field_ids = {a.field_id for a in fill_actions}

        field_results: list[FieldRenderResult] = []
        for action in plan.actions:
            if action.field_id in filled_field_ids:
                fr = fill_result_map.get(action.field_id)
                if fr and fr.success:
                    field_results.append(
                        FieldRenderResult(
                            field_id=action.field_id,
                            status=RenderStatus.SUCCESS,
                            value_written=fr.value_written,
                        )
                    )
                else:
                    msg = None
                    if fr and fr.issues:
                        msg = fr.issues[0].message
                    field_results.append(
                        FieldRenderResult(
                            field_id=action.field_id,
                            status=RenderStatus.FAILED,
                            error_message=msg or "Fill failed",
                        )
                    )
            else:
                field_results.append(
                    FieldRenderResult(
                        field_id=action.field_id,
                        status=RenderStatus.SKIPPED,
                    )
                )

        filled_count = sum(1 for r in field_results if r.status == RenderStatus.SUCCESS)
        failed_count = sum(1 for r in field_results if r.status == RenderStatus.FAILED)

        return RenderReport(
            success=fill_result.success,
            filled_document_ref=fill_result.filled_document_ref,
            field_results=tuple(field_results),
            filled_count=filled_count,
            failed_count=failed_count,
            error_message=(fill_result.errors[0].message if fill_result.errors else None),
        )
