"""Mapping routes for field correspondence.

POST /api/v1/map - Generate source-to-target field mappings.
Uses deterministic string matching and optional LLM-based reasoning.
"""

from fastapi import APIRouter, status

from app.models import ApiResponse
from app.models.mapping import (
    MappingRequest,
    MappingResult,
)
from app.services.mapping import MappingService
from app.services.mapping.adapters import (
    InMemoryTemplateHistory,
    RapidFuzzStringMatcher,
)

router = APIRouter(tags=["mapping"])


def _get_mapping_service() -> MappingService:
    """Create and return a MappingService instance.

    Factory function for dependency injection.
    In production, this would be configured with proper adapters.

    Returns:
        Configured MappingService instance
    """
    string_matcher = RapidFuzzStringMatcher()
    template_history = InMemoryTemplateHistory()

    # Note: MappingAgent is not included by default
    # To enable LLM-based reasoning, pass a configured agent:
    #
    # from langchain_openai import ChatOpenAI
    # from app.services.mapping.agents import LangChainMappingAgent
    #
    # llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    # mapping_agent = LangChainMappingAgent(llm=llm)
    #
    # return MappingService(
    #     string_matcher=string_matcher,
    #     mapping_agent=mapping_agent,
    #     template_history=template_history,
    # )

    return MappingService(
        string_matcher=string_matcher,
        mapping_agent=None,  # LLM agent not configured
        template_history=template_history,
    )


@router.post(
    "/map",
    response_model=ApiResponse[MappingResult],
    status_code=status.HTTP_200_OK,
    summary="Generate field mappings",
    description="""
Generate source-to-target field mappings.

This endpoint analyzes source fields and target fields to create
correspondence mappings for document data transfer.

The mapping process:
1. Apply user-defined rules (highest priority)
2. Check template history for known mappings
3. Perform deterministic string matching (fuzzy matching)
4. Use LLM agent for ambiguous cases (if configured)
5. Generate followup questions for unresolved mappings

Input:
- source_fields: Fields from the source document
- target_fields: Fields in the target document/template
- user_rules: Optional explicit mapping rules
- template_history: Optional template IDs for historical inference
- require_confirmation: If true, generates questions for low-confidence mappings
- confidence_threshold: Minimum confidence for automatic mapping

Output:
- mappings: Generated field mappings with confidence scores
- evidence_refs: References to evidence supporting mappings
- followup_questions: Questions for user disambiguation
- unmapped_source_fields: Source fields that could not be mapped
- unmapped_target_fields: Required target fields without mappings
""",
)
async def create_mappings(
    request: MappingRequest,
) -> ApiResponse[MappingResult]:
    """Generate field mappings from source to target fields.

    Args:
        request: Mapping request with source/target fields and options

    Returns:
        Mapping result with generated mappings and any followup questions
    """
    service = _get_mapping_service()
    result = await service.map_fields(request)

    return ApiResponse(
        success=True,
        data=result,
        meta={
            "source_field_count": len(request.source_fields),
            "target_field_count": len(request.target_fields),
            "mapping_count": len(result.mappings),
            "question_count": len(result.followup_questions),
            "llm_enabled": False,  # Would be True if agent configured
        },
    )
