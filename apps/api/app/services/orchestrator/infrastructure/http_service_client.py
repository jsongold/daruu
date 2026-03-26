"""HTTP Service Client for calling pipeline services.

This module provides an HTTP-based implementation of the ServiceGateway
interface for calling external microservices over HTTP.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_service_client_config
from app.models import (
    Activity,
    ActivityAction,
    Issue,
    JobContext,
)
from app.models.orchestrator import PipelineStage, StageResult


class HttpServiceClient:
    """HTTP client for calling pipeline services.

    This implementation of ServiceGateway makes HTTP calls to external
    microservices for each pipeline stage. It includes:
    - Retry logic with exponential backoff
    - Timeout handling
    - Error conversion to StageResult

    Configuration:
        base_urls: Dictionary mapping stage names to service base URLs
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
    """

    def __init__(
        self,
        base_urls: dict[str, str] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            base_urls: Mapping of stage names to service base URLs.
                      If None, uses default localhost URLs.
            timeout: Request timeout in seconds (uses config if None).
            max_retries: Maximum retry attempts (uses config if None).
        """
        config = get_service_client_config()
        self._base_urls = base_urls or self._default_base_urls()
        self._timeout = timeout if timeout is not None else config.timeout_seconds
        self._max_retries = max_retries if max_retries is not None else config.max_retries
        self._client: httpx.AsyncClient | None = None

    def _default_base_urls(self) -> dict[str, str]:
        """Get default base URLs for development."""
        return {
            "ingest": "http://localhost:8001",
            "structure": "http://localhost:8002",
            "labelling": "http://localhost:8002",  # Same as structure
            "map": "http://localhost:8003",
            "extract": "http://localhost:8004",
            "adjust": "http://localhost:8005",
            "fill": "http://localhost:8006",
            "review": "http://localhost:8007",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _call_service(
        self,
        stage: PipelineStage,
        job_context: JobContext,
    ) -> StageResult:
        """Make an HTTP call to a pipeline service.

        Args:
            stage: Pipeline stage to call.
            job_context: Job context to send.

        Returns:
            StageResult from the service.
        """
        client = await self._get_client()
        base_url = self._base_urls.get(stage.value, "http://localhost:8000")
        url = f"{base_url}/api/v1/{stage.value}"

        try:
            response = await client.post(
                url,
                json=job_context.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            return self._parse_stage_result(stage, data)

        except httpx.HTTPStatusError as e:
            return self._create_error_result(
                stage,
                f"HTTP error {e.response.status_code}: {e.response.text}",
            )
        except httpx.TimeoutException:
            return self._create_error_result(
                stage,
                f"Request timeout after {self._timeout}s",
            )
        except httpx.ConnectError:
            return self._create_error_result(
                stage,
                f"Failed to connect to {url}",
            )
        except Exception as e:
            return self._create_error_result(stage, str(e))

    def _parse_stage_result(
        self,
        stage: PipelineStage,
        data: dict[str, Any],
    ) -> StageResult:
        """Parse a StageResult from response data."""
        return StageResult(
            stage=stage,
            success=data.get("success", False),
            issues=self._parse_issues(data.get("issues", [])),
            activities=self._parse_activities(data.get("activities", [])),
            updated_fields=[],  # TODO: Parse fields when needed
            error_message=data.get("error_message"),
        )

    def _parse_issues(self, issues_data: list[dict[str, Any]]) -> list[Issue]:
        """Parse issues from response data."""
        return [Issue.model_validate(issue) for issue in issues_data]

    def _parse_activities(self, activities_data: list[dict[str, Any]]) -> list[Activity]:
        """Parse activities from response data."""
        return [Activity.model_validate(activity) for activity in activities_data]

    def _create_error_result(
        self,
        stage: PipelineStage,
        error_message: str,
    ) -> StageResult:
        """Create a StageResult for an error."""
        return StageResult(
            stage=stage,
            success=False,
            issues=[],
            activities=[
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.ERROR_OCCURRED,
                    details={"stage": stage.value, "error": error_message},
                )
            ],
            updated_fields=[],
            error_message=error_message,
        )

    # ServiceGateway interface implementation

    async def call_ingest(self, job_context: JobContext) -> StageResult:
        """Call ingest service."""
        return await self._call_service(PipelineStage.INGEST, job_context)

    async def call_structure(self, job_context: JobContext) -> StageResult:
        """Call structure service."""
        return await self._call_service(PipelineStage.STRUCTURE, job_context)

    async def call_labelling(self, job_context: JobContext) -> StageResult:
        """Call labelling service (uses LangChain internally)."""
        return await self._call_service(PipelineStage.LABELLING, job_context)

    async def call_map(self, job_context: JobContext) -> StageResult:
        """Call mapping service."""
        return await self._call_service(PipelineStage.MAP, job_context)

    async def call_extract(self, job_context: JobContext) -> StageResult:
        """Call extraction service (may use OCR/LLM)."""
        return await self._call_service(PipelineStage.EXTRACT, job_context)

    async def call_adjust(self, job_context: JobContext) -> StageResult:
        """Call adjustment service."""
        return await self._call_service(PipelineStage.ADJUST, job_context)

    async def call_fill(self, job_context: JobContext) -> StageResult:
        """Call fill service."""
        return await self._call_service(PipelineStage.FILL, job_context)

    async def call_review(self, job_context: JobContext) -> StageResult:
        """Call review service."""
        return await self._call_service(PipelineStage.REVIEW, job_context)
