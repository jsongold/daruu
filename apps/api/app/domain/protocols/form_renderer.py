"""Protocol for FormRenderer.

FormRenderer takes a FillPlan and writes values into the PDF,
producing a RenderReport.
"""

from typing import Any, Protocol, runtime_checkable

from app.domain.models.fill_plan import FillPlan
from app.domain.models.render_report import RenderReport


@runtime_checkable
class FormRendererProtocol(Protocol):
    """Interface for rendering filled values into a PDF document.

    Implementations convert FillPlan actions into actual PDF writes
    (AcroForm or overlay) via the underlying FillService.
    """

    async def render(
        self,
        plan: FillPlan,
        target_document_ref: str,
        render_params: dict[str, Any] | None = None,
    ) -> RenderReport:
        """Render the fill plan into a PDF document.

        Args:
            plan: FillPlan with per-field actions (only 'fill' actions are rendered).
            target_document_ref: Storage reference to the target PDF.
            render_params: Optional rendering parameters (font, size, etc.).

        Returns:
            RenderReport with filled document reference and per-field results.

        Raises:
            FileNotFoundError: If the target document cannot be loaded.
        """
        ...
