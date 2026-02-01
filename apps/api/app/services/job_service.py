"""Job service for handling job operations."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models import (
    Activity,
    ActivityAction,
    BBox,
    ConfidenceSummary,
    Document,
    Evidence,
    Extraction,
    FieldAnswer,
    FieldEdit,
    FieldModel,
    FieldType,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobCreate,
    JobMode,
    JobStatus,
    Mapping,
    PagePreview,
    ReviewResponse,
    RunMode,
)
from app.models.orchestrator import NextAction, OrchestratorConfig
from app.repositories import DocumentRepository, EventPublisher, JobRepository
from app.infrastructure.repositories import (
    get_document_repository,
    get_event_publisher,
    get_job_repository,
)
from app.orchestrator import Orchestrator


class JobService:
    """Service for job operations."""

    def __init__(
        self,
        job_repository: JobRepository | None = None,
        document_repository: DocumentRepository | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._job_repository = job_repository or get_job_repository()
        self._document_repository = document_repository or get_document_repository()
        self._event_publisher = event_publisher or get_event_publisher()

    def create_job(self, request: JobCreate) -> JobContext:
        """Create a new job."""
        # Validate documents exist
        target_doc = self._document_repository.get(request.target_document_id)
        if target_doc is None:
            raise ValueError(f"Target document not found: {request.target_document_id}")

        source_doc: Document | None = None
        if request.mode == JobMode.TRANSFER:
            if request.source_document_id is None:
                raise ValueError("Source document required for transfer mode")
            source_doc = self._document_repository.get(request.source_document_id)
            if source_doc is None:
                raise ValueError(f"Source document not found: {request.source_document_id}")

        # Create job
        job = self._job_repository.create(
            mode=request.mode,
            target_document=target_doc,
            source_document=source_doc,
        )

        # Publish event
        self._event_publisher.publish_sync(job.id, {
            "event": "job_created",
            "job_id": job.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return job

    def get_job(self, job_id: str) -> JobContext | None:
        """Get a job by ID."""
        return self._job_repository.get(job_id)

    async def run_job(
        self,
        job_id: str,
        run_mode: RunMode,
        max_steps: int | None = None,
    ) -> JobContext:
        """Run a job with the specified mode.

        This method delegates to the Orchestrator which handles:
        - Pipeline stage execution
        - Decision making for branching/loops
        - State transitions
        - Event publishing

        Args:
            job_id: ID of the job to run.
            run_mode: How to run the job (step, until_blocked, until_done).
            max_steps: Optional maximum steps to execute.

        Returns:
            Updated job context.

        Raises:
            ValueError: If job not found or cannot be run.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            raise ValueError(f"Job is already {job.status.value}")

        # Create orchestrator with appropriate config
        orchestrator = Orchestrator(
            job_repository=self._job_repository,
            event_publisher=self._event_publisher,
        )

        # Delegate to orchestrator
        return await orchestrator.run(job_id, run_mode, max_steps)

    async def _process_step(self, job_id: str) -> JobContext | None:
        """Process a single step of the job.

        Note: This is a mock implementation for MVP.
        Production would call actual OCR/LLM services.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        current_progress = job.progress

        # Simulate different processing phases
        if current_progress < 0.2:
            # Phase 1: Extract fields from target document
            job = await self._extract_target_fields(job_id)
        elif current_progress < 0.4 and job.mode == JobMode.TRANSFER:
            # Phase 2: Extract fields from source document (transfer mode only)
            job = await self._extract_source_fields(job_id)
        elif current_progress < 0.6 and job.mode == JobMode.TRANSFER:
            # Phase 3: Create mappings (transfer mode only)
            job = await self._create_mappings(job_id)
        elif current_progress < 0.8:
            # Phase 4: Extract/transfer values
            job = await self._extract_values(job_id)
        else:
            # Phase 5: Finalize
            job = await self._finalize_job(job_id)

        return job

    async def _extract_target_fields(self, job_id: str) -> JobContext | None:
        """Extract fields from target document (mock)."""
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        # Add mock fields if not already present
        if not job.fields:
            mock_fields = self._generate_mock_fields(job.target_document.id, "target")
            for field in mock_fields:
                job = self._job_repository.add_field(job_id, field)

        # Add activity
        activity = Activity(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=ActivityAction.EXTRACTION_COMPLETED,
            details={"phase": "target_fields", "count": len(job.fields) if job else 0},
        )
        job = self._job_repository.add_activity(job_id, activity)

        # Update progress
        return self._job_repository.update(job_id, progress=0.2)

    async def _extract_source_fields(self, job_id: str) -> JobContext | None:
        """Extract fields from source document (mock)."""
        job = self._job_repository.get(job_id)
        if job is None or job.source_document is None:
            return job

        # Add mock source fields
        source_fields = self._generate_mock_fields(job.source_document.id, "source")
        for field in source_fields:
            job = self._job_repository.add_field(job_id, field)

        # Add activity
        activity = Activity(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=ActivityAction.EXTRACTION_COMPLETED,
            details={"phase": "source_fields", "count": len(source_fields)},
        )
        self._job_repository.add_activity(job_id, activity)

        return self._job_repository.update(job_id, progress=0.4)

    async def _create_mappings(self, job_id: str) -> JobContext | None:
        """Create field mappings (mock)."""
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        # Create mock mappings between source and target fields
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]
        source_fields = [
            f for f in job.fields
            if job.source_document and f.document_id == job.source_document.id
        ]

        for i, target in enumerate(target_fields):
            if i < len(source_fields):
                mapping = Mapping(
                    id=str(uuid4()),
                    source_field_id=source_fields[i].id,
                    target_field_id=target.id,
                    confidence=0.85,
                    is_confirmed=False,
                )
                self._job_repository.add_mapping(job_id, mapping)

        # Add activity
        activity = Activity(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=ActivityAction.MAPPING_CREATED,
            details={"count": min(len(target_fields), len(source_fields))},
        )
        self._job_repository.add_activity(job_id, activity)

        return self._job_repository.update(job_id, progress=0.6)

    async def _extract_values(self, job_id: str) -> JobContext | None:
        """Extract/transfer field values (mock)."""
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        # Create mock extractions for target fields
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]

        for field in target_fields:
            # Create extraction
            extraction = Extraction(
                id=str(uuid4()),
                field_id=field.id,
                value=f"Sample value for {field.name}",
                confidence=0.75,
                evidence_ids=[],
            )
            self._job_repository.add_extraction(job_id, extraction)

            # Create evidence
            evidence = Evidence(
                id=str(uuid4()),
                field_id=field.id,
                source="mock",
                bbox=field.bbox,
                confidence=0.75,
                text=f"Sample value for {field.name}",
                document_id=field.document_id,
            )
            self._job_repository.add_evidence(job_id, evidence)

            # Update field with value
            self._job_repository.update_field(job_id, field.id, value=extraction.value)

        # Add some mock issues for low confidence fields
        for field in target_fields[:1]:  # Add issue to first field
            issue = Issue(
                id=str(uuid4()),
                field_id=field.id,
                issue_type=IssueType.LOW_CONFIDENCE,
                message=f"Low confidence for field '{field.name}'",
                severity=IssueSeverity.WARNING,
                suggested_action="Please verify this value",
            )
            self._job_repository.add_issue(job_id, issue)

        # Check if we should block for user input
        job = self._job_repository.get(job_id)
        if job and job.issues:
            return self._job_repository.update(
                job_id,
                progress=0.8,
                status=JobStatus.BLOCKED,
                current_step="awaiting_review",
                next_actions=["review", "answer", "edit"],
            )

        return self._job_repository.update(job_id, progress=0.8)

    async def _finalize_job(self, job_id: str) -> JobContext | None:
        """Finalize the job (mock)."""
        activity = Activity(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=ActivityAction.JOB_COMPLETED,
            details={},
        )
        self._job_repository.add_activity(job_id, activity)

        return self._job_repository.update(
            job_id,
            progress=1.0,
            status=JobStatus.DONE,
            current_step="completed",
            next_actions=["download", "export"],
        )

    def _generate_mock_fields(self, document_id: str, prefix: str) -> list[FieldModel]:
        """Generate mock fields for testing."""
        field_names = ["Name", "Date", "Amount", "Description", "Signature"]
        fields = []

        for i, name in enumerate(field_names):
            field = FieldModel(
                id=str(uuid4()),
                name=f"{name}",
                field_type=FieldType.TEXT if name != "Signature" else FieldType.SIGNATURE,
                value=None,
                confidence=None,
                bbox=BBox(
                    x=50.0,
                    y=100.0 + (i * 50),
                    width=200.0,
                    height=30.0,
                    page=1,
                ),
                document_id=document_id,
                page=1,
                is_required=i < 3,  # First 3 fields are required
                is_editable=True,
            )
            fields.append(field)

        return fields

    def _update_status(self, job_id: str, status: JobStatus) -> JobContext | None:
        """Update job status."""
        return self._job_repository.update(job_id, status=status)

    async def _publish_event(
        self,
        job_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish an event to subscribers."""
        await self._event_publisher.publish(job_id, {
            "event": event_type,
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })

    def submit_answers(
        self,
        job_id: str,
        answers: list[FieldAnswer],
    ) -> JobContext:
        """Submit answers for blocked fields."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        # Update fields with answers
        for answer in answers:
            self._job_repository.update_field(job_id, answer.field_id, value=answer.value)

            # Add activity
            activity = Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.ANSWER_RECEIVED,
                details={"field_id": answer.field_id, "value": answer.value},
                field_id=answer.field_id,
            )
            self._job_repository.add_activity(job_id, activity)

        # Clear related issues
        self._job_repository.clear_issues(job_id)

        # Update status if was blocked
        job = self._job_repository.get(job_id)
        if job and job.status == JobStatus.BLOCKED:
            job = self._job_repository.update(
                job_id,
                status=JobStatus.RUNNING,
                next_actions=["run"],
            )

        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job lost after answers: {job_id}")
        return job

    def submit_edits(
        self,
        job_id: str,
        edits: list[FieldEdit],
    ) -> JobContext:
        """Submit manual edits for fields."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        # Update fields with edits
        for edit in edits:
            updates: dict[str, Any] = {}
            if edit.value is not None:
                updates["value"] = edit.value
            if edit.bbox is not None:
                updates["bbox"] = edit.bbox

            if updates:
                self._job_repository.update_field(job_id, edit.field_id, **updates)

                # Add activity
                activity = Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.FIELD_EDITED,
                    details={"field_id": edit.field_id, **updates},
                    field_id=edit.field_id,
                )
                self._job_repository.add_activity(job_id, activity)

        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job lost after edits: {job_id}")
        return job

    def get_review(self, job_id: str) -> ReviewResponse:
        """Get review data for a job."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        # Get target fields
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]

        # Build confidence summary
        confidence_summary = self._build_confidence_summary(target_fields)

        # Build page previews
        previews = self._build_page_previews(job)

        return ReviewResponse(
            issues=list(job.issues),
            previews=previews,
            fields=target_fields,
            confidence_summary=confidence_summary,
        )

    def _build_confidence_summary(self, fields: list[FieldModel]) -> ConfidenceSummary:
        """Build confidence summary from fields."""
        total = len(fields)
        high = 0
        medium = 0
        low = 0
        no_value = 0
        confidence_sum = 0.0
        confidence_count = 0

        for field in fields:
            if field.value is None:
                no_value += 1
            elif field.confidence is None:
                no_value += 1
            elif field.confidence >= 0.8:
                high += 1
                confidence_sum += field.confidence
                confidence_count += 1
            elif field.confidence >= 0.5:
                medium += 1
                confidence_sum += field.confidence
                confidence_count += 1
            else:
                low += 1
                confidence_sum += field.confidence
                confidence_count += 1

        avg = confidence_sum / confidence_count if confidence_count > 0 else 0.0

        return ConfidenceSummary(
            total_fields=total,
            high_confidence=high,
            medium_confidence=medium,
            low_confidence=low,
            no_value=no_value,
            average_confidence=avg,
        )

    def _build_page_previews(self, job: JobContext) -> list[PagePreview]:
        """Build page preview list for a job."""
        previews = []
        doc = job.target_document

        for page in range(1, doc.meta.page_count + 1):
            # Get annotations for this page
            annotations = [
                f.bbox
                for f in job.fields
                if f.document_id == doc.id and f.page == page and f.bbox is not None
            ]

            preview = PagePreview(
                page=page,
                document_id=doc.id,
                url=f"/documents/{doc.id}/pages/{page}/preview",
                annotations=annotations,
            )
            previews.append(preview)

        return previews

    def get_activity(self, job_id: str) -> list[Activity]:
        """Get activity log for a job."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        return list(job.activities)

    def get_evidence(self, job_id: str, field_id: str | None = None) -> list[Evidence]:
        """Get evidence for a job, optionally filtered by field."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        if field_id:
            return [e for e in job.evidence if e.field_id == field_id]
        return list(job.evidence)

    def export_job(self, job_id: str) -> dict[str, Any]:
        """Export job data as JSON."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        return {
            "job_id": job.id,
            "mode": job.mode.value,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "fields": [f.model_dump(mode="json") for f in job.fields],
            "mappings": [m.model_dump(mode="json") for m in job.mappings],
            "extractions": [e.model_dump(mode="json") for e in job.extractions],
            "evidence": [e.model_dump(mode="json") for e in job.evidence],
            "activities": [a.model_dump(mode="json") for a in job.activities],
        }

    def get_next_actions(self, job_id: str) -> list[NextAction]:
        """Get available next actions for a job.

        Uses the decision engine to determine what actions are available
        based on the current job state.

        Args:
            job_id: ID of the job.

        Returns:
            List of available next actions.

        Raises:
            ValueError: If job not found.
        """
        orchestrator = Orchestrator(
            job_repository=self._job_repository,
            event_publisher=self._event_publisher,
        )
        return orchestrator.get_next_actions(job_id)
