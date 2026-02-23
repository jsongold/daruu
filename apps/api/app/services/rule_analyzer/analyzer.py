"""RuleAnalyzer stub — returns empty list for Phase 2.

Will be replaced with real LLM-based analysis in a future phase.
"""

from app.domain.models.form_context import FormFieldSpec
from app.domain.models.rule_snippet import RuleSnippet


class RuleAnalyzerStub:
    """Stub implementation of RuleAnalyzerProtocol.

    Returns an empty list of rule snippets. Placeholder for
    future LLM-based rule document analysis.
    """

    async def analyze(
        self,
        rule_docs: tuple[str, ...],
        field_hints: tuple[FormFieldSpec, ...] = (),
    ) -> list[RuleSnippet]:
        """Return empty list (stub).

        Args:
            rule_docs: Rule document references (ignored).
            field_hints: Field specs for context (ignored).

        Returns:
            Empty list.
        """
        return []
