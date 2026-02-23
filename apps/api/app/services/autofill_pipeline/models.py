"""Models for the autofill pipeline orchestrator."""

from pydantic import BaseModel, Field

from app.domain.models.fill_plan import FillPlan
from app.domain.models.form_context import FormContext
from app.domain.models.render_report import RenderReport


class AutofillPipelineResult(BaseModel):
    """Result of the full autofill pipeline.

    Contains the intermediate outputs (context, plan) and
    the final render report.
    """

    context: FormContext = Field(..., description="Built form context")
    plan: FillPlan = Field(..., description="Generated fill plan")
    report: RenderReport = Field(..., description="Render report with filled PDF ref")
    processing_time_ms: int = Field(
        default=0, ge=0, description="Total pipeline processing time in ms"
    )

    model_config = {"frozen": True}
