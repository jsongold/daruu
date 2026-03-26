"""Pydantic models for the API."""

from app.models.annotation import (
    AnnotationBBox,
    AnnotationPairCreate,
    AnnotationPairModel,
    AnnotationPairsResponse,
)
from app.models.common import (
    ApiResponse,
    BBox,
    CostBreakdown,
    CostSummaryModel,
    ErrorDetail,
    ErrorResponse,
    PaginationMeta,
)
from app.models.cost import (
    CostSummary,
    CostTracker,
    LLMUsage,
)
from app.models.document import (
    Document,
    DocumentCreate,
    DocumentMeta,
    DocumentResponse,
    DocumentType,
    PagePreviewResponse,
)
from app.models.evidence import Evidence, EvidenceResponse
from app.models.field import (
    FieldAnswer,
    FieldEdit,
    FieldModel,
    FieldType,
    Mapping,
)
from app.models.health import (
    ComponentHealth,
    HealthResponse,
    ReadinessResponse,
)
from app.models.ingest import (
    IngestError,
    IngestErrorCode,
    IngestRequest,
    IngestResult,
    PageMeta,
    RenderedPage,
)
from app.models.job import (
    Activity,
    ActivityAction,
    ConfidenceSummary,
    Extraction,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobCreate,
    JobMode,
    JobResponse,
    JobStatus,
    PagePreview,
    ReviewResponse,
    RunMode,
    RunRequest,
    RunResponse,
)
from app.models.mapping import (
    FollowupQuestion,
    MappingItem,
    MappingRequest,
    MappingResult,
    SourceField,
    TargetField,
    UserRule,
)
from app.models.orchestrator import (
    PIPELINE_SEQUENCE,
    NextAction,
    NextActionType,
    OrchestratorConfig,
    PipelineStage,
    StageResult,
    get_next_stage,
    get_stage_index,
)
from app.models.review import (
    ConfidenceUpdate,
    PageMetaInput,
    PreviewArtifact,
    ReviewRequest,
    ReviewResult,
)
from app.models.task import (
    AsyncJobCreate,
    AsyncJobResponse,
    RunAsyncRequest,
    RunAsyncResponse,
    TaskStatus,
    TaskStatusResponse,
)
from app.models.template import (
    FieldType as TemplateFieldType,
)
from app.models.template import (
    RuleType,
    Template,
    TemplateBbox,
    TemplateCreate,
    TemplateDetailResponse,
    TemplateListResponse,
    TemplateMatch,
    TemplateMatchRequest,
    TemplateMatchResponse,
    TemplateResponse,
    TemplateRule,
    TemplateUpdate,
)

__all__ = [
    # Common
    "ApiResponse",
    "BBox",
    "CostBreakdown",
    "CostSummaryModel",
    "ErrorDetail",
    "ErrorResponse",
    "PaginationMeta",
    # Cost
    "CostSummary",
    "CostTracker",
    "LLMUsage",
    # Document
    "Document",
    "DocumentCreate",
    "DocumentMeta",
    "DocumentResponse",
    "DocumentType",
    "PagePreviewResponse",
    # Evidence
    "Evidence",
    "EvidenceResponse",
    # Field
    "FieldAnswer",
    "FieldEdit",
    "FieldModel",
    "FieldType",
    "Mapping",
    # Health
    "ComponentHealth",
    "HealthResponse",
    "ReadinessResponse",
    # Job
    "Activity",
    "ActivityAction",
    "ConfidenceSummary",
    "Extraction",
    "Issue",
    "IssueSeverity",
    "IssueType",
    "JobContext",
    "JobCreate",
    "JobMode",
    "JobResponse",
    "JobStatus",
    "PagePreview",
    "ReviewResponse",
    "RunMode",
    "RunRequest",
    "RunResponse",
    # Pipeline/Orchestrator
    "NextAction",
    "NextActionType",
    "OrchestratorConfig",
    "PipelineStage",
    "StageResult",
    "PIPELINE_SEQUENCE",
    "get_next_stage",
    "get_stage_index",
    # Ingest
    "IngestError",
    "IngestErrorCode",
    "IngestRequest",
    "IngestResult",
    "PageMeta",
    "RenderedPage",
    # Mapping
    "FollowupQuestion",
    "MappingItem",
    "MappingRequest",
    "MappingResult",
    "SourceField",
    "TargetField",
    "UserRule",
    # Review
    "ConfidenceUpdate",
    "PageMetaInput",
    "PreviewArtifact",
    "ReviewRequest",
    "ReviewResult",
    # Task (async processing)
    "AsyncJobCreate",
    "AsyncJobResponse",
    "RunAsyncRequest",
    "RunAsyncResponse",
    "TaskStatus",
    "TaskStatusResponse",
    # Annotation
    "AnnotationBBox",
    "AnnotationPairCreate",
    "AnnotationPairModel",
    "AnnotationPairsResponse",
    # Template (Phase 2 Template System)
    "TemplateFieldType",
    "RuleType",
    "Template",
    "TemplateBbox",
    "TemplateCreate",
    "TemplateDetailResponse",
    "TemplateListResponse",
    "TemplateMatch",
    "TemplateMatchRequest",
    "TemplateMatchResponse",
    "TemplateResponse",
    "TemplateRule",
    "TemplateUpdate",
]
