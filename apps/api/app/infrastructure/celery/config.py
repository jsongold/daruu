"""Celery configuration settings.

Provides configuration for Celery task queue:
- Broker and result backend URLs (Redis)
- Task time limits
- Worker concurrency settings
- Retry and dead letter queue configuration
"""

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class CeleryConfig(BaseSettings):
    """Celery configuration loaded from environment variables.

    All settings can be overridden via environment variables with CELERY_ prefix.
    """

    # Broker settings (Redis)
    broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL for Celery broker (Redis)",
    )
    result_backend: str = Field(
        default="redis://localhost:6379/1",
        description="URL for Celery result backend (Redis)",
    )

    # Task time limits
    task_soft_time_limit: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Soft time limit in seconds (sends SoftTimeLimitExceeded)",
    )
    task_time_limit: int = Field(
        default=600,
        ge=60,
        le=7200,
        description="Hard time limit in seconds (terminates task)",
    )

    # Worker settings
    worker_concurrency: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of concurrent worker processes",
    )
    worker_prefetch_multiplier: int = Field(
        default=1,
        ge=1,
        le=16,
        description="Number of tasks to prefetch per worker",
    )

    # Retry settings
    task_default_retry_delay: int = Field(
        default=30,
        ge=1,
        le=600,
        description="Default retry delay in seconds",
    )
    task_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries for failed tasks",
    )

    # Serialization
    task_serializer: str = Field(
        default="json",
        description="Task serialization format",
    )
    result_serializer: str = Field(
        default="json",
        description="Result serialization format",
    )
    accept_content: list[str] = Field(
        default_factory=lambda: ["json"],
        description="Accepted content types",
    )

    # Result settings
    result_expires: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Result expiry time in seconds",
    )
    task_track_started: bool = Field(
        default=True,
        description="Track when tasks start executing",
    )
    task_ignore_result: bool = Field(
        default=False,
        description="Whether to ignore task results",
    )

    # Task routing
    task_default_queue: str = Field(
        default="daru_default",
        description="Default queue for tasks",
    )

    # Dead letter queue settings
    task_reject_on_worker_lost: bool = Field(
        default=True,
        description="Reject task if worker is lost",
    )
    task_acks_late: bool = Field(
        default=True,
        description="Acknowledge task after completion (enables redelivery)",
    )

    model_config = {
        "env_prefix": "CELERY_",
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }

    def to_celery_config(self) -> dict[str, Any]:
        """Convert to Celery configuration dictionary.

        Returns:
            Dictionary suitable for Celery app configuration.
        """
        return {
            # Broker
            "broker_url": self.broker_url,
            "result_backend": self.result_backend,
            # Time limits
            "task_soft_time_limit": self.task_soft_time_limit,
            "task_time_limit": self.task_time_limit,
            # Worker
            "worker_concurrency": self.worker_concurrency,
            "worker_prefetch_multiplier": self.worker_prefetch_multiplier,
            # Retry
            "task_default_retry_delay": self.task_default_retry_delay,
            # Serialization
            "task_serializer": self.task_serializer,
            "result_serializer": self.result_serializer,
            "accept_content": self.accept_content,
            # Results
            "result_expires": self.result_expires,
            "task_track_started": self.task_track_started,
            "task_ignore_result": self.task_ignore_result,
            # Queue
            "task_default_queue": self.task_default_queue,
            # Dead letter / reliability
            "task_reject_on_worker_lost": self.task_reject_on_worker_lost,
            "task_acks_late": self.task_acks_late,
            # Task routes
            "task_routes": {
                "app.infrastructure.celery.tasks.process_job_task": {
                    "queue": "daru_jobs",
                },
                "app.infrastructure.celery.tasks.ingest_document_task": {
                    "queue": "daru_ingest",
                },
            },
            # Timezone
            "timezone": "UTC",
            "enable_utc": True,
        }


class TaskProgressConfig(BaseModel):
    """Configuration for task progress reporting.

    Defines progress checkpoints for different task stages.
    """

    ingest_start: float = Field(default=0.0)
    ingest_complete: float = Field(default=0.10)
    structure_complete: float = Field(default=0.25)
    mapping_complete: float = Field(default=0.45)
    extract_complete: float = Field(default=0.65)
    adjust_complete: float = Field(default=0.80)
    fill_complete: float = Field(default=0.95)
    review_complete: float = Field(default=1.0)

    model_config = {"frozen": True}


@lru_cache
def get_celery_config() -> CeleryConfig:
    """Get cached Celery configuration.

    Returns:
        CeleryConfig instance with values from environment.
    """
    return CeleryConfig()


@lru_cache
def get_task_progress_config() -> TaskProgressConfig:
    """Get cached task progress configuration.

    Returns:
        TaskProgressConfig with default values.
    """
    return TaskProgressConfig()


def clear_celery_config_cache() -> None:
    """Clear cached Celery configuration.

    Useful for testing when settings need to be reloaded.
    """
    get_celery_config.cache_clear()
    get_task_progress_config.cache_clear()
