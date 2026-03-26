"""Application configuration with centralized settings.

All magic numbers and configurable values are centralized here.
Configuration is organized by domain for easy management.

Usage:
    from app.config import get_settings, get_orchestrator_config

    settings = get_settings()
    orchestrator_config = get_orchestrator_config()
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# =============================================================================
# Centralized Model Constants
# =============================================================================

DEFAULT_MODEL = "gpt-4.1-mini"

DEFAULT_LLM_PRICING: dict[str, dict[str, float]] = {
    "gpt-5-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
    "gpt-4.1-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
}


# =============================================================================
# Domain Configuration Classes
# =============================================================================


class OrchestratorConfig(BaseModel):
    """Orchestrator pipeline configuration.

    Controls the orchestrator's decision-making behavior,
    loop control, and termination conditions.
    """

    # Pipeline control
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum retry iterations to prevent infinite loops",
    )
    max_steps_per_run: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum steps in a single run_until_blocked call",
    )

    # Confidence thresholds
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for field values",
    )
    min_improvement_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum improvement rate to continue retrying",
    )

    # User interaction
    high_severity_requires_user: bool = Field(
        default=True,
        description="Whether high severity issues require user input",
    )
    require_user_approval: bool = Field(
        default=False,
        description="Require user approval before marking job as done",
    )

    model_config = {"frozen": True}


class LLMConfig(BaseModel):
    """LLM/OpenAI configuration.

    Controls timeouts, retries, and model selection for LLM calls.
    """

    # Model selection
    model: str = Field(
        default=DEFAULT_MODEL,
        description="OpenAI model to use",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom endpoint URL (e.g., Azure OpenAI)",
    )

    # Request settings
    timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
        description="Timeout for LLM API calls in seconds",
    )
    max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum concurrent LLM requests",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for transient errors",
    )

    # Agent settings
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM responses",
    )

    model_config = {"frozen": True}


class OCRConfig(BaseModel):
    """OCR processing configuration.

    Controls OCR engine behavior and confidence thresholds.
    """

    # Confidence thresholds
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum OCR confidence to trust results",
    )
    native_text_confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence assigned to native PDF text",
    )
    llm_normalization_confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence assigned to LLM-normalized values",
    )

    # Processing settings
    max_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Thread pool workers for OCR processing",
    )
    x_tolerance: float = Field(
        default=3.0,
        ge=0.0,
        le=20.0,
        description="Horizontal tolerance for text extraction",
    )
    y_tolerance: float = Field(
        default=5.0,
        ge=0.0,
        le=20.0,
        description="Vertical tolerance for text extraction",
    )

    # Text detection
    min_text_length: int = Field(
        default=10,
        ge=1,
        description="Minimum text length to consider page has content",
    )
    pages_to_check: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of pages to check for text content",
    )

    model_config = {"frozen": True}


class IngestConfig(BaseModel):
    """PDF ingestion configuration.

    Controls PDF rendering and validation.
    """

    # Rendering
    default_dpi: int = Field(
        default=150,
        ge=72,
        le=600,
        description="Default DPI for page rendering",
    )
    min_dpi: int = Field(
        default=72,
        ge=36,
        description="Minimum allowed DPI",
    )
    max_dpi: int = Field(
        default=600,
        le=1200,
        description="Maximum allowed DPI",
    )
    default_format: str = Field(
        default="png",
        pattern="^(png|jpeg)$",
        description="Default image format for rendered pages",
    )
    default_quality: int = Field(
        default=95,
        ge=0,
        le=100,
        description="JPEG quality (0-100)",
    )

    # Validation limits
    max_page_count: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum pages per document",
    )

    model_config = {"frozen": True}


class MappingConfig(BaseModel):
    """Field mapping configuration.

    Controls how source and target fields are matched.
    """

    # Matching thresholds
    similarity_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum similarity for a match",
    )
    ambiguity_gap: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description="Score gap required between best and second match",
    )
    high_confidence_threshold: float = Field(
        default=0.99,
        ge=0.9,
        le=1.0,
        description="Threshold for confident direct match",
    )
    low_threshold_multiplier: float = Field(
        default=0.4,
        ge=0.1,
        le=0.9,
        description="Multiplier for candidate gathering threshold",
    )

    # LLM fallback
    llm_fallback_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to use LLM result",
    )
    llm_confidence_reduction: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Confidence multiplier for fallback matches",
    )
    history_confidence: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Confidence for history-based matches",
    )

    # Search limits
    candidate_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum candidates to consider per field",
    )

    model_config = {"frozen": True}


class ExtractConfig(BaseModel):
    """Value extraction configuration.

    Controls how field values are extracted from documents.
    """

    # Confidence thresholds
    default_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Default confidence threshold for extraction",
    )
    low_confidence_warning_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold below which to warn about confidence",
    )

    # LLM fallback
    fallback_confidence_reduction: float = Field(
        default=0.8,
        ge=0.5,
        le=1.0,
        description="Confidence multiplier for fallback extraction",
    )

    model_config = {"frozen": True}


class StorageConfig(BaseModel):
    """File storage configuration.

    Controls upload limits and bucket names.
    """

    # Upload limits
    upload_max_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum upload size in MB",
    )
    allowed_extensions: tuple[str, ...] = Field(
        default=(".pdf",),
        description="Allowed file extensions",
    )

    # Bucket names
    bucket_documents: str = Field(
        default="documents",
        description="Bucket for original PDFs",
    )
    bucket_previews: str = Field(
        default="previews",
        description="Bucket for page preview images",
    )
    bucket_crops: str = Field(
        default="crops",
        description="Bucket for OCR crop images",
    )
    bucket_outputs: str = Field(
        default="outputs",
        description="Bucket for filled PDFs",
    )

    model_config = {"frozen": True}


class ServiceClientConfig(BaseModel):
    """HTTP service client configuration.

    Controls timeouts and retries for inter-service communication.
    """

    # Request settings
    timeout_seconds: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts",
    )

    # Retry backoff
    retry_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Exponential backoff multiplier",
    )
    retry_min_wait: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Minimum retry wait in seconds",
    )
    retry_max_wait: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Maximum retry wait in seconds",
    )

    # Mock mode
    use_mock_services: bool = Field(
        default=True,
        description="Use mock implementations for testing",
    )

    model_config = {"frozen": True}


class RedisConfig(BaseModel):
    """Redis configuration for job storage.

    Controls Redis connection and lock settings.
    """

    url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )
    prefix: str = Field(
        default="daru:",
        description="Key prefix for Redis keys",
    )
    lock_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Lock timeout in seconds",
    )
    job_ttl: int = Field(
        default=86400,
        ge=60,
        le=604800,
        description="Job TTL in seconds (default 24 hours)",
    )

    model_config = {"frozen": True}


class IssueScoringConfig(BaseModel):
    """Issue severity scoring configuration.

    Weights for calculating issue scores by severity.
    """

    critical_weight: float = Field(
        default=10.0,
        ge=1.0,
        le=100.0,
        description="Weight for CRITICAL issues",
    )
    high_weight: float = Field(
        default=5.0,
        ge=1.0,
        le=50.0,
        description="Weight for HIGH/ERROR issues",
    )
    warning_weight: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Weight for WARNING issues",
    )
    info_weight: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Weight for INFO issues",
    )

    model_config = {"frozen": True}


class PipelineProgressConfig(BaseModel):
    """Pipeline stage progress percentages.

    Defines progress values for each pipeline stage.
    """

    ingest: float = Field(default=0.10)
    structure: float = Field(default=0.20)
    labelling: float = Field(default=0.30)
    map: float = Field(default=0.45)
    extract: float = Field(default=0.60)
    adjust: float = Field(default=0.75)
    fill: float = Field(default=0.90)
    review: float = Field(default=1.0)

    model_config = {"frozen": True}

    def get_progress(self, stage: str) -> float:
        """Get progress value for a stage."""
        return getattr(self, stage, 0.0)


class CostConfig(BaseModel):
    """Cost tracking configuration.

    Defines pricing and budget limits for LLM, OCR, and storage operations.
    Prices are per-unit costs in USD.
    """

    # LLM pricing (per 1,000 tokens)
    llm_input_cost_per_1k: float = Field(
        default=0.00015,
        ge=0,
        description="Cost per 1K input tokens for gpt-5-mini",
    )
    llm_output_cost_per_1k: float = Field(
        default=0.0006,
        ge=0,
        description="Cost per 1K output tokens for gpt-5-mini",
    )

    # OCR pricing
    ocr_cost_per_page: float = Field(
        default=0.0015,
        ge=0,
        description="Cost per page for OCR processing",
    )
    ocr_cost_per_region: float = Field(
        default=0.0003,
        ge=0,
        description="Cost per region for targeted OCR",
    )

    # Storage pricing (per GB)
    storage_upload_cost_per_gb: float = Field(
        default=0.02,
        ge=0,
        description="Cost per GB for uploads",
    )
    storage_download_cost_per_gb: float = Field(
        default=0.01,
        ge=0,
        description="Cost per GB for downloads",
    )

    # Budget limits
    max_cost_per_job: float | None = Field(
        default=None,
        ge=0,
        description="Maximum cost per job in USD (None for unlimited)",
    )
    warn_cost_threshold: float | None = Field(
        default=None,
        ge=0,
        description="Cost threshold to emit warning (None for no warning)",
    )

    # Model-specific pricing overrides (per 1M tokens for precision)
    model_pricing: dict[str, dict[str, float]] = Field(
        default_factory=lambda: dict(DEFAULT_LLM_PRICING),
        description="Model-specific pricing per 1M tokens",
    )

    model_config = {"frozen": True}

    def get_model_pricing(self, model_name: str) -> dict[str, float]:
        """Get pricing for a specific model.

        Args:
            model_name: Model identifier.

        Returns:
            Pricing dictionary with input_per_1m and output_per_1m keys.
        """
        return self.model_pricing.get(
            model_name,
            {
                "input_per_1m": self.llm_input_cost_per_1k * 1000,
                "output_per_1m": self.llm_output_cost_per_1k * 1000,
            },
        )


# =============================================================================
# Processing Strategy Type
# =============================================================================

ProcessingStrategyLiteral = Literal["local_only", "llm_only", "hybrid", "llm_with_local_fallback"]


# =============================================================================
# Main Settings Class
# =============================================================================


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All domain-specific configs are nested for organization.
    Environment variables use DARU_ prefix.
    """

    # Application info
    app_name: str = "Daru PDF API"
    app_version: str = "0.1.0"
    debug: bool = False

    # API settings
    api_prefix: str = "/api/v1"
    allowed_origins: str = "*"

    # File storage paths
    upload_dir: Path = Path("/tmp/daru-pdf-uploads")
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_mime_types: list[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
        "image/tif",
        "image/webp",
    ]

    # Job processing (legacy, use orchestrator config)
    default_confidence_threshold: float = 0.7
    max_steps_per_run: int = 100

    # Processing strategy
    processing_strategy: ProcessingStrategyLiteral = "hybrid"
    structure_labelling_strategy: ProcessingStrategyLiteral | str = ""
    mapping_strategy: ProcessingStrategyLiteral | str = ""
    extract_strategy: ProcessingStrategyLiteral | str = ""

    # Strategy behavior
    skip_llm_on_high_confidence: bool = True
    high_confidence_threshold: float = 0.9
    fallback_on_llm_error: bool = True

    # OpenAI/LLM settings (environment variables)
    openai_api_key: str | None = None
    openai_model: str = DEFAULT_MODEL
    openai_base_url: str | None = None
    openai_timeout_seconds: int = 120
    openai_max_concurrent_requests: int = 5
    llm_analyze_mode: str | None = None

    # LangChain settings
    langchain_tracing: bool = False
    langchain_project: str = "daru-pdf"
    langchain_verbose: bool = False

    # Supabase settings (backend uses secret key only)
    supabase_url: str | None = None
    supabase_secret_key: str | None = None  # Backend: sb_secret_* or service_role JWT

    # Storage bucket names
    storage_bucket_documents: str = "documents"
    storage_bucket_previews: str = "previews"
    storage_bucket_crops: str = "crops"
    storage_bucket_outputs: str = "outputs"

    # SSE settings
    sse_keepalive_interval: int = 15

    # Cost tracking settings
    cost_max_per_job: float | None = None
    cost_warn_threshold: float | None = None

    # Autofill architecture toggle: "legacy" uses VisionAutofillService,
    # "tobe" uses the new FormContextBuilder -> FillPlanner -> FormRenderer pipeline
    autofill_architecture: str = "legacy"

    # Maximum characters for raw text in autofill prompts
    autofill_max_raw_text_chars: int = 4000

    # Celery settings (can also use CELERY_ prefix directly)
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_soft_time_limit: int = 300
    celery_task_time_limit: int = 600
    celery_worker_concurrency: int = 4

    # Rule Service URL (standalone rule extraction microservice)
    rule_service_url: str = "http://rule-service:8002"

    # Domain configs (loaded from env or defaults)
    # These can be overridden via DARU_ORCHESTRATOR__MAX_ITERATIONS etc.

    model_config = {
        "env_prefix": "DARU_",
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
        "env_nested_delimiter": "__",
    }


# =============================================================================
# Configuration Factory Functions
# =============================================================================


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache
def get_orchestrator_config() -> OrchestratorConfig:
    """Get orchestrator configuration from settings.

    Returns:
        OrchestratorConfig with values from environment or defaults.
    """
    settings = get_settings()
    return OrchestratorConfig(
        max_iterations=10,
        max_steps_per_run=settings.max_steps_per_run,
        confidence_threshold=settings.default_confidence_threshold,
        min_improvement_rate=0.1,
        high_severity_requires_user=True,
        require_user_approval=False,
    )


@lru_cache
def get_llm_config() -> LLMConfig:
    """Get LLM configuration from settings.

    Returns:
        LLMConfig with values from environment or defaults.
    """
    settings = get_settings()
    return LLMConfig(
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
        max_concurrent_requests=settings.openai_max_concurrent_requests,
        max_retries=3,
        temperature=0.0,
    )


@lru_cache
def get_ocr_config() -> OCRConfig:
    """Get OCR configuration with defaults.

    Returns:
        OCRConfig with default values.
    """
    return OCRConfig()


@lru_cache
def get_ingest_config() -> IngestConfig:
    """Get ingest configuration with defaults.

    Returns:
        IngestConfig with default values.
    """
    return IngestConfig()


@lru_cache
def get_mapping_config() -> MappingConfig:
    """Get mapping configuration with defaults.

    Returns:
        MappingConfig with default values.
    """
    return MappingConfig()


@lru_cache
def get_extract_config() -> ExtractConfig:
    """Get extraction configuration with defaults.

    Returns:
        ExtractConfig with default values.
    """
    return ExtractConfig()


@lru_cache
def get_storage_config() -> StorageConfig:
    """Get storage configuration from settings.

    Returns:
        StorageConfig with values from environment or defaults.
    """
    settings = get_settings()
    return StorageConfig(
        upload_max_size_mb=settings.max_upload_size // (1024 * 1024),
        bucket_documents=settings.storage_bucket_documents,
        bucket_previews=settings.storage_bucket_previews,
        bucket_crops=settings.storage_bucket_crops,
        bucket_outputs=settings.storage_bucket_outputs,
    )


@lru_cache
def get_service_client_config() -> ServiceClientConfig:
    """Get service client configuration with defaults.

    Returns:
        ServiceClientConfig with default values.
    """
    return ServiceClientConfig()


@lru_cache
def get_redis_config() -> RedisConfig:
    """Get Redis configuration with defaults.

    Returns:
        RedisConfig with default values.
    """
    return RedisConfig()


@lru_cache
def get_issue_scoring_config() -> IssueScoringConfig:
    """Get issue scoring configuration with defaults.

    Returns:
        IssueScoringConfig with default values.
    """
    return IssueScoringConfig()


@lru_cache
def get_pipeline_progress_config() -> PipelineProgressConfig:
    """Get pipeline progress configuration with defaults.

    Returns:
        PipelineProgressConfig with default values.
    """
    return PipelineProgressConfig()


@lru_cache
def get_cost_config() -> CostConfig:
    """Get cost tracking configuration from settings.

    Returns:
        CostConfig with values from environment or defaults.
    """
    settings = get_settings()
    return CostConfig(
        max_cost_per_job=settings.cost_max_per_job,
        warn_cost_threshold=settings.cost_warn_threshold,
    )


def get_strategy_config(
    service_name: str | None = None,
) -> "StrategyConfig":
    """Get strategy configuration from settings.

    Args:
        service_name: Optional service name for service-specific override.
            Valid values: "structure_labelling", "mapping", "extract"
            If None, returns the default strategy.

    Returns:
        StrategyConfig instance based on settings
    """
    # Import here to avoid circular imports
    from app.models.processing_strategy import (
        ProcessingStrategy,
        StrategyConfig,
    )

    settings = get_settings()
    llm_config = get_llm_config()

    # Determine which strategy string to use
    strategy_str = settings.processing_strategy

    # Check for service-specific override
    if service_name:
        override_attr = f"{service_name}_strategy"
        override_value = getattr(settings, override_attr, "")
        if override_value and override_value.strip():
            strategy_str = override_value

    # Parse the strategy enum
    try:
        strategy_enum = ProcessingStrategy(strategy_str)
    except ValueError:
        # Fall back to HYBRID if invalid
        strategy_enum = ProcessingStrategy.HYBRID

    return StrategyConfig(
        strategy=strategy_enum,
        skip_llm_on_high_confidence=settings.skip_llm_on_high_confidence,
        high_confidence_threshold=settings.high_confidence_threshold,
        fallback_on_llm_error=settings.fallback_on_llm_error,
        llm_timeout_seconds=llm_config.timeout_seconds,
    )


# =============================================================================
# Utility Functions
# =============================================================================


def clear_config_cache() -> None:
    """Clear all cached configuration instances.

    Useful for testing when settings need to be reloaded.
    """
    get_settings.cache_clear()
    get_orchestrator_config.cache_clear()
    get_llm_config.cache_clear()
    get_ocr_config.cache_clear()
    get_ingest_config.cache_clear()
    get_mapping_config.cache_clear()
    get_extract_config.cache_clear()
    get_storage_config.cache_clear()
    get_service_client_config.cache_clear()
    get_redis_config.cache_clear()
    get_issue_scoring_config.cache_clear()
    get_pipeline_progress_config.cache_clear()
    get_cost_config.cache_clear()
