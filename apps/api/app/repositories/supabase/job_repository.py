"""Supabase implementation of JobRepository.

Provides job persistence using Supabase PostgreSQL database.
All operations follow immutable patterns - they return new objects
rather than mutating existing ones.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.resilience import is_retryable_error, with_retry
from app.models import (
    Activity,
    ActivityAction,
    Document,
    DocumentMeta,
    DocumentType,
    Evidence,
    Extraction,
    FieldModel,
    FieldType,
    Issue,
    IssueType,
    IssueSeverity,
    JobContext,
    JobMode,
    JobStatus,
    Mapping,
)
from app.models.common import BBox, CostSummaryModel, CostBreakdown
from app.repositories import JobRepository

logger = logging.getLogger(__name__)


class SupabaseJobRepository:
    """Supabase implementation of JobRepository.

    Uses Supabase PostgreSQL to store job data and related entities.
    Implements immutable update patterns for all operations.
    """

    TABLE_JOBS = "jobs"
    TABLE_FIELDS = "fields"
    TABLE_MAPPINGS = "mappings"
    TABLE_EXTRACTIONS = "extractions"
    TABLE_EVIDENCE = "evidence"
    TABLE_ISSUES = "issues"
    TABLE_ACTIVITIES = "activities"
    TABLE_DOCUMENTS = "documents"

    def __init__(self) -> None:
        """Initialize the repository."""
        self._client = get_supabase_client()

    def _parse_datetime(self, value: str | datetime | None) -> datetime:
        """Parse datetime from string or return as-is."""
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _parse_json(self, value: Any) -> Any:
        """Parse JSON string if needed."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    def _to_document(self, row: dict[str, Any]) -> Document:
        """Convert a document row to Document model."""
        meta_dict = self._parse_json(row.get("meta", {}))
        meta = DocumentMeta(
            page_count=meta_dict.get("page_count", 1),
            file_size=meta_dict.get("file_size", 0),
            mime_type=meta_dict.get("mime_type", "application/pdf"),
            filename=meta_dict.get("filename", "unknown.pdf"),
            has_password=meta_dict.get("has_password", False),
            has_acroform=meta_dict.get("has_acroform", False),
        )
        return Document(
            id=str(row["id"]),
            ref=row["ref"],
            document_type=DocumentType(row["document_type"]),
            meta=meta,
            created_at=self._parse_datetime(row.get("created_at")),
        )

    def _to_field(self, row: dict[str, Any]) -> FieldModel:
        """Convert a field row to FieldModel."""
        bbox_data = self._parse_json(row.get("bbox"))
        bbox = None
        if bbox_data:
            bbox = BBox(
                x=bbox_data.get("x", 0),
                y=bbox_data.get("y", 0),
                width=bbox_data.get("width", 0),
                height=bbox_data.get("height", 0),
                page=bbox_data.get("page", row.get("page", 1)),
            )
        return FieldModel(
            id=str(row["id"]),
            name=row["name"],
            field_type=FieldType(row.get("field_type", "text")),
            value=row.get("value"),
            confidence=row.get("confidence"),
            bbox=bbox,
            document_id=str(row["document_id"]),
            page=row["page"],
            is_required=row.get("is_required", False),
            is_editable=row.get("is_editable", True),
        )

    def _to_mapping(self, row: dict[str, Any]) -> Mapping:
        """Convert a mapping row to Mapping model."""
        return Mapping(
            id=str(row["id"]),
            source_field_id=str(row["source_field_id"]),
            target_field_id=str(row["target_field_id"]),
            confidence=row["confidence"],
            is_confirmed=row.get("is_confirmed", False),
        )

    def _to_extraction(self, row: dict[str, Any]) -> Extraction:
        """Convert an extraction row to Extraction model."""
        evidence_ids = self._parse_json(row.get("evidence_ids", []))
        return Extraction(
            id=str(row["id"]),
            field_id=str(row["field_id"]),
            value=row["value"],
            confidence=row["confidence"],
            evidence_ids=evidence_ids if isinstance(evidence_ids, list) else [],
        )

    def _to_evidence(self, row: dict[str, Any]) -> Evidence:
        """Convert an evidence row to Evidence model."""
        bbox_data = self._parse_json(row.get("bbox"))
        bbox = None
        if bbox_data:
            bbox = BBox(
                x=bbox_data.get("x", 0),
                y=bbox_data.get("y", 0),
                width=bbox_data.get("width", 0),
                height=bbox_data.get("height", 0),
                page=bbox_data.get("page", row.get("page", 1)),
            )
        return Evidence(
            id=str(row["id"]),
            field_id=str(row["field_id"]),
            source=row["source"],
            bbox=bbox,
            confidence=row["confidence"],
            text=row.get("text"),
            document_id=str(row["document_id"]),
        )

    def _to_issue(self, row: dict[str, Any]) -> Issue:
        """Convert an issue row to Issue model."""
        field_id = row.get("field_id")
        return Issue(
            id=str(row["id"]),
            field_id=str(field_id) if field_id else None,
            issue_type=IssueType(row["issue_type"]),
            message=row["message"],
            severity=IssueSeverity(row["severity"]),
            suggested_action=row.get("suggested_action"),
        )

    def _to_activity(self, row: dict[str, Any]) -> Activity:
        """Convert an activity row to Activity model."""
        details = self._parse_json(row.get("details", {}))
        return Activity(
            id=str(row["id"]),
            timestamp=self._parse_datetime(row.get("timestamp")),
            action=ActivityAction(row["action"]),
            details=details if isinstance(details, dict) else {},
            field_id=str(row["field_id"]) if row.get("field_id") else None,
        )

    def _to_cost_summary(self, cost_data: dict[str, Any]) -> CostSummaryModel:
        """Convert cost data to CostSummaryModel."""
        if not cost_data:
            return CostSummaryModel.empty()

        breakdown_data = cost_data.get("breakdown", {})
        breakdown = CostBreakdown(
            llm_cost_usd=breakdown_data.get("llm_cost_usd", 0.0),
            ocr_cost_usd=breakdown_data.get("ocr_cost_usd", 0.0),
            storage_cost_usd=breakdown_data.get("storage_cost_usd", 0.0),
        )

        return CostSummaryModel(
            llm_tokens_input=cost_data.get("llm_tokens_input", 0),
            llm_tokens_output=cost_data.get("llm_tokens_output", 0),
            llm_calls=cost_data.get("llm_calls", 0),
            ocr_pages_processed=cost_data.get("ocr_pages_processed", 0),
            ocr_regions_processed=cost_data.get("ocr_regions_processed", 0),
            storage_bytes_uploaded=cost_data.get("storage_bytes_uploaded", 0),
            storage_bytes_downloaded=cost_data.get("storage_bytes_downloaded", 0),
            estimated_cost_usd=cost_data.get("estimated_cost_usd", 0.0),
            breakdown=breakdown,
            model_name=cost_data.get("model_name", "gpt-4o-mini"),
        )

    def _fetch_job_related_data(
        self, job_id: str
    ) -> tuple[
        list[FieldModel],
        list[Mapping],
        list[Extraction],
        list[Evidence],
        list[Issue],
        list[Activity],
    ]:
        """Fetch all related data for a job."""
        # Fetch fields
        fields_result = (
            self._client.table(self.TABLE_FIELDS)
            .select("*")
            .eq("job_id", job_id)
            .execute()
        )
        fields = [self._to_field(row) for row in fields_result.data]

        # Fetch mappings
        mappings_result = (
            self._client.table(self.TABLE_MAPPINGS)
            .select("*")
            .eq("job_id", job_id)
            .execute()
        )
        mappings = [self._to_mapping(row) for row in mappings_result.data]

        # Fetch extractions
        extractions_result = (
            self._client.table(self.TABLE_EXTRACTIONS)
            .select("*")
            .eq("job_id", job_id)
            .execute()
        )
        extractions = [self._to_extraction(row) for row in extractions_result.data]

        # Fetch evidence (via field_ids from this job)
        evidence: list[Evidence] = []
        if fields:
            field_ids = [f.id for f in fields]
            for field_id in field_ids:
                evidence_result = (
                    self._client.table(self.TABLE_EVIDENCE)
                    .select("*")
                    .eq("field_id", field_id)
                    .execute()
                )
                evidence.extend([self._to_evidence(row) for row in evidence_result.data])

        # Fetch issues
        issues_result = (
            self._client.table(self.TABLE_ISSUES)
            .select("*")
            .eq("job_id", job_id)
            .execute()
        )
        issues = [self._to_issue(row) for row in issues_result.data]

        # Fetch activities
        activities_result = (
            self._client.table(self.TABLE_ACTIVITIES)
            .select("*")
            .eq("job_id", job_id)
            .order("timestamp", desc=False)
            .execute()
        )
        activities = [self._to_activity(row) for row in activities_result.data]

        return fields, mappings, extractions, evidence, issues, activities

    def _fetch_document(self, document_id: str) -> Document | None:
        """Fetch a document by ID."""
        result = (
            self._client.table(self.TABLE_DOCUMENTS)
            .select("*")
            .eq("id", document_id)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return self._to_document(result.data[0])
        return None

    def _to_job_context(self, row: dict[str, Any]) -> JobContext:
        """Convert a job row and related data to JobContext."""
        job_id = str(row["id"])

        # Fetch documents
        target_doc = self._fetch_document(str(row["target_document_id"]))
        source_doc = None
        if row.get("source_document_id"):
            source_doc = self._fetch_document(str(row["source_document_id"]))

        # Fetch related data
        fields, mappings, extractions, evidence, issues, activities = (
            self._fetch_job_related_data(job_id)
        )

        # Parse next_actions
        next_actions = self._parse_json(row.get("next_actions", []))
        if not isinstance(next_actions, list):
            next_actions = []

        # Parse cost
        cost_data = self._parse_json(row.get("cost", {}))
        cost = self._to_cost_summary(cost_data)

        if target_doc is None:
            raise ValueError(f"Target document not found for job {job_id}")

        return JobContext(
            id=job_id,
            mode=JobMode(row["mode"]),
            status=JobStatus(row["status"]),
            source_document=source_doc,
            target_document=target_doc,
            fields=fields,
            mappings=mappings,
            extractions=extractions,
            evidence=evidence,
            issues=issues,
            activities=activities,
            created_at=self._parse_datetime(row.get("created_at")),
            updated_at=self._parse_datetime(row.get("updated_at")),
            progress=row.get("progress", 0.0),
            current_step=row.get("current_step"),
            current_stage=row.get("current_stage"),
            next_actions=next_actions,
            iteration_count=row.get("iteration_count", 0),
            cost=cost,
        )

    def create(
        self,
        mode: JobMode,
        target_document: Document,
        source_document: Document | None = None,
    ) -> JobContext:
        """Create a new job.

        Args:
            mode: Job mode (transfer/scratch).
            target_document: Target document to fill.
            source_document: Optional source document for transfer mode.

        Returns:
            Created JobContext with generated ID.
        """
        job_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Create job row
        job_row: dict[str, Any] = {
            "id": job_id,
            "mode": mode.value,
            "status": JobStatus.CREATED.value,
            "target_document_id": target_document.id,
            "progress": 0.0,
            "current_step": "initialized",
            "next_actions": ["run"],
            "iteration_count": 0,
            "cost": {},
        }
        if source_document:
            job_row["source_document_id"] = source_document.id

        try:
            self._client.table(self.TABLE_JOBS).insert(job_row).execute()

            # Create initial activity
            activity_id = str(uuid4())
            activity_row = {
                "id": activity_id,
                "job_id": job_id,
                "action": ActivityAction.JOB_CREATED.value,
                "details": {"mode": mode.value},
                "timestamp": now.isoformat(),
            }
            self._client.table(self.TABLE_ACTIVITIES).insert(activity_row).execute()

            # Return the created job
            initial_activity = Activity(
                id=activity_id,
                timestamp=now,
                action=ActivityAction.JOB_CREATED,
                details={"mode": mode.value},
            )

            return JobContext(
                id=job_id,
                mode=mode,
                status=JobStatus.CREATED,
                source_document=source_document,
                target_document=target_document,
                fields=[],
                mappings=[],
                extractions=[],
                evidence=[],
                issues=[],
                activities=[initial_activity],
                created_at=now,
                updated_at=now,
                progress=0.0,
                current_step="initialized",
                next_actions=["run"],
            )
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            raise

    def get(self, job_id: str) -> JobContext | None:
        """Get a job by ID with retry on transient errors.

        Args:
            job_id: Unique job identifier.

        Returns:
            JobContext if found, None otherwise.
        """
        try:
            return self._get_with_retry(job_id)
        except Exception as e:
            if is_retryable_error(e):
                # Already retried, log and return None
                logger.error(f"Failed to get job {job_id} after retries: {e}")
            else:
                logger.error(f"Non-retryable error getting job {job_id}: {e}")
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _get_with_retry(self, job_id: str) -> JobContext | None:
        """Internal get with retry logic."""
        result = (
            self._client.table(self.TABLE_JOBS)
            .select("*")
            .eq("id", job_id)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return self._to_job_context(result.data[0])
        return None

    def update(self, job_id: str, **updates: Any) -> JobContext | None:
        """Update a job with new values (immutable pattern) with retry on transient errors.

        Args:
            job_id: Unique job identifier.
            **updates: Fields to update.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            return self._update_with_retry(job_id, **updates)
        except Exception as e:
            if is_retryable_error(e):
                logger.error(f"Failed to update job {job_id} after retries: {e}")
            else:
                logger.error(f"Non-retryable error updating job {job_id}: {e}")
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _update_with_retry(self, job_id: str, **updates: Any) -> JobContext | None:
        """Internal update with retry logic."""
        # Build update data for jobs table
        update_data: dict[str, Any] = {}

        simple_fields = [
            "status", "progress", "current_step", "current_stage",
            "iteration_count",
        ]
        for field in simple_fields:
            if field in updates:
                value = updates[field]
                if hasattr(value, "value"):
                    update_data[field] = value.value
                else:
                    update_data[field] = value

        if "next_actions" in updates:
            update_data["next_actions"] = updates["next_actions"]

        if "cost" in updates:
            cost = updates["cost"]
            if isinstance(cost, CostSummaryModel):
                update_data["cost"] = cost.model_dump()
            else:
                update_data["cost"] = cost

        if not update_data:
            return self.get(job_id)

        self._client.table(self.TABLE_JOBS).update(update_data).eq(
            "id", job_id
        ).execute()

        return self.get(job_id)

    def add_activity(self, job_id: str, activity: Activity) -> JobContext | None:
        """Add an activity to a job.

        Args:
            job_id: Unique job identifier.
            activity: Activity to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            activity_row = {
                "id": activity.id,
                "job_id": job_id,
                "action": activity.action.value,
                "details": activity.details,
                "timestamp": activity.timestamp.isoformat(),
            }
            if activity.field_id:
                activity_row["field_id"] = activity.field_id

            self._client.table(self.TABLE_ACTIVITIES).insert(activity_row).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to add activity to job {job_id}: {e}")
            return None

    def add_field(self, job_id: str, field: FieldModel) -> JobContext | None:
        """Add a field to a job.

        Note: No retry logic here - this is called in bulk (e.g., 189 fields).
        Retry with sleep would block the async event loop.

        Args:
            job_id: Unique job identifier.
            field: Field to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            field_row: dict[str, Any] = {
                "id": field.id,
                "job_id": job_id,
                "document_id": field.document_id,
                "name": field.name,
                "field_type": field.field_type.value,
                "page": field.page,
                "is_required": field.is_required,
                "is_editable": field.is_editable,
            }
            if field.value is not None:
                field_row["value"] = field.value
            if field.confidence is not None:
                field_row["confidence"] = field.confidence
            if field.bbox:
                field_row["bbox"] = {
                    "x": field.bbox.x,
                    "y": field.bbox.y,
                    "width": field.bbox.width,
                    "height": field.bbox.height,
                    "page": field.bbox.page,
                }

            self._client.table(self.TABLE_FIELDS).insert(field_row).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to add field to job {job_id}: {e}")
            return None

    def update_field(
        self, job_id: str, field_id: str, **updates: Any
    ) -> JobContext | None:
        """Update a field in a job (immutable).

        Args:
            job_id: Unique job identifier.
            field_id: Field identifier to update.
            **updates: Fields to update.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            update_data: dict[str, Any] = {}

            for key, value in updates.items():
                if key == "field_type" and hasattr(value, "value"):
                    update_data[key] = value.value
                elif key == "bbox" and value is not None:
                    update_data[key] = {
                        "x": value.x,
                        "y": value.y,
                        "width": value.width,
                        "height": value.height,
                        "page": value.page,
                    }
                else:
                    update_data[key] = value

            if not update_data:
                return self.get(job_id)

            self._client.table(self.TABLE_FIELDS).update(update_data).eq(
                "id", field_id
            ).execute()

            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to update field {field_id}: {e}")
            return None

    def add_mapping(self, job_id: str, mapping: Mapping) -> JobContext | None:
        """Add a mapping to a job.

        Args:
            job_id: Unique job identifier.
            mapping: Mapping to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            mapping_row = {
                "id": mapping.id,
                "job_id": job_id,
                "source_field_id": mapping.source_field_id,
                "target_field_id": mapping.target_field_id,
                "confidence": mapping.confidence,
                "is_confirmed": mapping.is_confirmed,
            }

            self._client.table(self.TABLE_MAPPINGS).insert(mapping_row).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to add mapping to job {job_id}: {e}")
            return None

    def add_extraction(self, job_id: str, extraction: Extraction) -> JobContext | None:
        """Add an extraction to a job.

        Args:
            job_id: Unique job identifier.
            extraction: Extraction to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            extraction_row = {
                "id": extraction.id,
                "job_id": job_id,
                "field_id": extraction.field_id,
                "value": extraction.value,
                "confidence": extraction.confidence,
                "evidence_ids": extraction.evidence_ids,
            }

            self._client.table(self.TABLE_EXTRACTIONS).insert(extraction_row).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to add extraction to job {job_id}: {e}")
            return None

    def add_evidence(self, job_id: str, evidence: Evidence) -> JobContext | None:
        """Add evidence to a job.

        Args:
            job_id: Unique job identifier.
            evidence: Evidence to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            evidence_row: dict[str, Any] = {
                "id": evidence.id,
                "field_id": evidence.field_id,
                "document_id": evidence.document_id,
                "source": evidence.source,
                "confidence": evidence.confidence,
            }
            if evidence.bbox:
                evidence_row["bbox"] = {
                    "x": evidence.bbox.x,
                    "y": evidence.bbox.y,
                    "width": evidence.bbox.width,
                    "height": evidence.bbox.height,
                    "page": evidence.bbox.page,
                }
                evidence_row["page"] = evidence.bbox.page
            if evidence.text:
                evidence_row["text"] = evidence.text

            self._client.table(self.TABLE_EVIDENCE).insert(evidence_row).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to add evidence to job {job_id}: {e}")
            return None

    def add_issue(self, job_id: str, issue: Issue) -> JobContext | None:
        """Add an issue to a job.

        Note: No retry logic here - this can be called in bulk.
        Retry with sleep would block the async event loop.

        Args:
            job_id: Unique job identifier.
            issue: Issue to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            issue_row: dict[str, Any] = {
                "id": issue.id,
                "job_id": job_id,
                "issue_type": issue.issue_type.value,
                "severity": issue.severity.value,
                "message": issue.message,
            }
            # field_id is optional for stage-level issues
            if issue.field_id is not None:
                issue_row["field_id"] = issue.field_id
            if issue.suggested_action:
                issue_row["suggested_action"] = issue.suggested_action

            self._client.table(self.TABLE_ISSUES).insert(issue_row).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to add issue to job {job_id}: {e}")
            return None

    def clear_issues(self, job_id: str) -> JobContext | None:
        """Clear all issues from a job.

        Args:
            job_id: Unique job identifier.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            self._client.table(self.TABLE_ISSUES).delete().eq(
                "job_id", job_id
            ).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to clear issues for job {job_id}: {e}")
            return None

    def remove_issue(self, job_id: str, issue_id: str) -> JobContext | None:
        """Remove a specific issue from a job.

        Args:
            job_id: Unique job identifier.
            issue_id: Issue identifier to remove.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        try:
            self._client.table(self.TABLE_ISSUES).delete().eq(
                "id", issue_id
            ).execute()
            return self.get(job_id)
        except Exception as e:
            logger.error(f"Failed to remove issue {issue_id}: {e}")
            return None

    def list_all(self) -> list[JobContext]:
        """List all jobs.

        Returns:
            List of all jobs.
        """
        try:
            result = (
                self._client.table(self.TABLE_JOBS)
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            jobs = []
            for row in result.data:
                try:
                    jobs.append(self._to_job_context(row))
                except Exception as e:
                    logger.warning(f"Failed to parse job {row.get('id')}: {e}")
            return jobs
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []

    def delete(self, job_id: str) -> bool:
        """Delete a job by ID.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if deleted, False if not found.
        """
        try:
            existing = self.get(job_id)
            if existing is None:
                return False

            # Delete cascades to related tables via foreign keys
            self._client.table(self.TABLE_JOBS).delete().eq("id", job_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False


# Verify protocol compliance
_assert_protocol: JobRepository = SupabaseJobRepository()
