"""Protocol for FormContextBuilder.

FormContextBuilder aggregates data from data sources, extracts text,
and produces a FormContext ready for the FillPlanner.
"""

from typing import Protocol, runtime_checkable

from app.domain.models.form_context import FormContext, FormFieldSpec


@runtime_checkable
class FormContextBuilderProtocol(Protocol):
    """Interface for building FormContext from document and data sources.

    Implementations gather data sources for a conversation, extract text/data
    from each, and produce fuzzy mapping candidates between fields and data.
    """

    async def build(
        self,
        document_id: str,
        conversation_id: str,
        field_hints: tuple[FormFieldSpec, ...],
        user_rules: tuple[str, ...] = (),
    ) -> FormContext:
        """Build a FormContext from document fields and conversation data sources.

        Args:
            document_id: Target document ID.
            conversation_id: Conversation ID containing data sources.
            field_hints: Form field specifications to match against.
            user_rules: Optional user-provided filling rules.

        Returns:
            FormContext with fields, data sources, and mapping candidates.

        Raises:
            ValueError: If document_id or conversation_id is invalid.
        """
        ...
