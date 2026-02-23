"""Protocol for RuleAnalyzer.

RuleAnalyzer extracts structured rule snippets from rule documents
to guide the FillPlanner's decisions.
"""

from typing import Protocol, runtime_checkable

from app.domain.models.form_context import FormFieldSpec
from app.domain.models.rule_snippet import RuleSnippet


@runtime_checkable
class RuleAnalyzerProtocol(Protocol):
    """Interface for analyzing rule documents.

    Implementations parse rule documents and extract structured
    RuleSnippets that constrain or guide field filling.
    """

    async def analyze(
        self,
        rule_docs: tuple[str, ...],
        field_hints: tuple[FormFieldSpec, ...] = (),
    ) -> list[RuleSnippet]:
        """Analyze rule documents and extract rule snippets.

        Args:
            rule_docs: Tuple of rule document references or content strings.
            field_hints: Optional field specs for context-aware rule extraction.

        Returns:
            List of extracted RuleSnippets.
        """
        ...
