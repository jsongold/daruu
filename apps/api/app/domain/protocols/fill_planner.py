"""Protocol for FillPlanner.

FillPlanner uses LLM (or rules) to decide what value to fill into each
form field, producing a FillPlan.
"""

from typing import Any, Protocol, runtime_checkable

from app.domain.models.fill_plan import FillPlan
from app.domain.models.form_context import FormContext


@runtime_checkable
class FillPlannerProtocol(Protocol):
    """Interface for planning field fill actions.

    Implementations take a FormContext and produce a FillPlan with
    per-field actions (fill, skip, or ask_user).
    """

    async def plan(
        self,
        context: FormContext,
    ) -> FillPlan:
        """Create a fill plan from the given form context.

        Args:
            context: FormContext containing fields, data sources,
                     and mapping candidates.

        Returns:
            FillPlan with an action for each field.

        Raises:
            RuntimeError: If the LLM call fails and no fallback is available.
        """
        ...

    async def plan_turn(
        self,
        context: FormContext,
        conversation_history: list[dict[str, Any]] | None = None,
        just_fill: bool = False,
    ) -> Any:
        """Execute a single turn in detailed mode.

        Returns either a question or a fill plan.
        """
        ...
