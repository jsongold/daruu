"""Service client for calling pipeline services.

This module provides a client for calling pipeline services.
Following Clean Architecture and the Service vs Agent distinction:

- Orchestrator calls Services via this client
- Services may internally use Agents (FieldLabellingAgent, etc.)
- Services may internally use other Services (OcrService, etc.)
- This client abstracts the communication with services

Service Architecture (per PRD):
- Ingest Service: PDF normalization (deterministic)
- Structure/Labelling Service: Uses FieldLabellingAgent internally
- Mapping Service: Uses MappingAgent internally
- Extract Service: Uses OcrService and ValueExtractionAgent internally
- Adjust Service: Coordinate adjustment (deterministic)
- Fill Service: PDF filling (deterministic)
- Review Service: Validation and review (deterministic)
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import (
    ServiceClientConfig,
    get_extract_config,
    get_ingest_config,
    get_mapping_config,
    get_service_client_config,
)
from app.models import (
    Activity,
    ActivityAction,
    BBox,
    Evidence,
    Extraction,
    FieldModel,
    FieldType,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobMode,
    Mapping,
)
from app.models.extract.models import ExtractField, ExtractRequest, PageArtifact
from app.models.orchestrator import PipelineStage, StageResult
from app.infrastructure.repositories import get_file_repository
from app.services.document_service import DocumentService
from app.services.orchestrator.application.ports.pipeline_services import (
    AdjustServicePort,
    ExtractServicePort,
    FillServicePort,
    IngestServicePort,
    MappingServicePort,
    ReviewServicePort,
    StructureLabellingServicePort,
)


class ServiceClient:
    """Client for calling external pipeline services.

    This client calls Services (not Agents directly). Services may internally:
    - Use Agents (FieldLabellingAgent, ValueExtractionAgent, MappingAgent)
    - Use other Services (OcrService, PdfWriteService, etc.)

    The client supports two modes:
    1. Mock mode (default): Returns mock results for testing
    2. Production mode: Delegates to injected service ports

    In production, service implementations are injected via the constructor.
    """

    def __init__(
        self,
        config: ServiceClientConfig | None = None,
        ingest_service: IngestServicePort | None = None,
        structure_labelling_service: StructureLabellingServicePort | None = None,
        mapping_service: MappingServicePort | None = None,
        extract_service: ExtractServicePort | None = None,
        adjust_service: AdjustServicePort | None = None,
        fill_service: FillServicePort | None = None,
        review_service: ReviewServicePort | None = None,
    ) -> None:
        """Initialize the service client.

        Args:
            config: Configuration for the client (uses centralized config if None).
            ingest_service: Implementation of IngestServicePort.
            structure_labelling_service: Implementation of StructureLabellingServicePort.
            mapping_service: Implementation of MappingServicePort.
            extract_service: Implementation of ExtractServicePort.
            adjust_service: Implementation of AdjustServicePort.
            fill_service: Implementation of FillServicePort.
            review_service: Implementation of ReviewServicePort.
        """
        self._config = config or get_service_client_config()
        self._ingest_service = ingest_service
        self._structure_labelling_service = structure_labelling_service
        self._mapping_service = mapping_service
        self._extract_service = extract_service
        self._adjust_service = adjust_service
        self._fill_service = fill_service
        self._review_service = review_service

    async def execute_stage(
        self,
        stage: PipelineStage,
        job: JobContext,
    ) -> StageResult:
        """Execute a pipeline stage.

        Routes to the appropriate service based on the stage.

        Args:
            stage: The pipeline stage to execute.
            job: Current job context.

        Returns:
            StageResult with success status, issues, activities, and updated fields.
        """
        stage_handlers = {
            PipelineStage.INGEST: self._execute_ingest,
            PipelineStage.STRUCTURE: self._execute_structure,
            PipelineStage.LABELLING: self._execute_labelling,
            PipelineStage.MAP: self._execute_map,
            PipelineStage.EXTRACT: self._execute_extract,
            PipelineStage.ADJUST: self._execute_adjust,
            PipelineStage.FILL: self._execute_fill,
            PipelineStage.REVIEW: self._execute_review,
        }

        handler = stage_handlers.get(stage)
        if handler is None:
            return StageResult(
                stage=stage,
                success=False,
                issues=[],
                activities=[],
                updated_fields=[],
                error_message=f"Unknown stage: {stage.value}",
            )

        try:
            return await handler(job)
        except Exception as e:
            return StageResult(
                stage=stage,
                success=False,
                issues=[],
                activities=[
                    Activity(
                        id=str(uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        action=ActivityAction.ERROR_OCCURRED,
                        details={"stage": stage.value, "error": str(e)},
                    )
                ],
                updated_fields=[],
                error_message=str(e),
            )

    async def _execute_ingest(self, job: JobContext) -> StageResult:
        """Execute the ingest stage.

        Uses IngestServicePort if available, otherwise returns mock result.
        """
        # Use real service if available
        if self._ingest_service is not None:
            from app.models.ingest.models import IngestRequest

            # Get document file path
            file_repository = get_file_repository()
            document_path = file_repository.get_path(job.target_document.id)
            document_ref = str(document_path) if document_path else getattr(job.target_document, 'ref', '')

            ingest_config = get_ingest_config()
            request = IngestRequest(
                document_id=job.target_document.id,
                document_ref=document_ref,
                render_dpi=ingest_config.default_dpi,
            )
            result = await self._ingest_service.ingest(request)

            activities = [
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.EXTRACTION_STARTED,
                    details={
                        "stage": "ingest",
                        "document_id": job.target_document.id,
                        "page_count": result.meta.page_count if result.meta else 0,
                        "success": result.success,
                    },
                )
            ]

            issues: list[Issue] = []
            for error in result.errors:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=None,  # No specific field for stage-level errors
                        issue_type=IssueType.LOW_CONFIDENCE,
                        message=error.message,
                        severity=IssueSeverity.HIGH,
                    )
                )

            return StageResult(
                stage=PipelineStage.INGEST,
                success=result.success,
                issues=issues,
                activities=activities,
                updated_fields=[],
            )

        # Mock implementation (fallback)
        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.EXTRACTION_STARTED,
                details={
                    "stage": "ingest",
                    "document_id": job.target_document.id,
                    "page_count": job.target_document.meta.page_count,
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.INGEST,
            success=True,
            issues=[],
            activities=activities,
            updated_fields=[],
        )

    async def _execute_structure(self, job: JobContext) -> StageResult:
        """Execute the structure stage.

        Priority order for field detection:
        1. AcroForm fields (native PDF form fields) - fastest and most accurate
        2. StructureLabellingService (LLM-based detection) - fallback for non-form PDFs
        3. Mock fields (testing fallback)
        """
        from app.infrastructure.observability import get_logger
        from app.services.document_service import DocumentService

        logger = get_logger("structure_stage", job_id=job.id)

        # Step 1: Try to extract AcroForm fields first (native PDF form fields)
        document_service = DocumentService()
        acroform_result = document_service.get_acroform_fields(job.target_document.id)

        if acroform_result is not None and acroform_result.has_acroform:
            # Count field types for logging
            field_types_count: dict[str, int] = {}
            for acro_field in acroform_result.fields:
                field_types_count[acro_field.field_type] = (
                    field_types_count.get(acro_field.field_type, 0) + 1
                )

            logger.info(
                "AcroForm fields detected",
                has_acroform=True,
                total_fields=len(acroform_result.fields),
                field_types=field_types_count,
            )

            # Try to link labels to AcroForm fields using structure labelling service
            # This improves field names from generic "Text26" to meaningful labels like "氏名"
            label_map: dict[str, str] = {}  # Maps AcroForm field_name to linked label
            if self._structure_labelling_service is not None:
                from app.models.structure_labelling.models import (
                    StructureLabellingRequest,
                    PageImageInput,
                    TextBlockInput,
                    BoxCandidateInput,
                )

                file_repository = get_file_repository()
                document_path = file_repository.get_path(job.target_document.id)
                document_ref = str(document_path) if document_path else getattr(job.target_document, 'ref', '')

                # Get page images
                page_images: list[PageImageInput] = []
                page_count = job.target_document.meta.page_count if job.target_document.meta else 1
                for page_num in range(1, page_count + 1):
                    preview_path = file_repository.get_preview_path(job.target_document.id, page_num)
                    if preview_path:
                        page_images.append(PageImageInput(
                            page=page_num,
                            image_ref=str(preview_path),
                        ))

                # Extract text blocks for label linking
                document_service = DocumentService()
                logger.info(
                    "Extracting text blocks for label linking",
                    document_id=job.target_document.id,
                )
                try:
                    text_block_dicts = document_service.extract_text_blocks(job.target_document.id)
                    logger.info(
                        "Text blocks extracted",
                        document_id=job.target_document.id,
                        text_block_count=len(text_block_dicts),
                    )
                except Exception as e:
                    logger.error(
                        "Failed to extract text blocks",
                        document_id=job.target_document.id,
                        error=str(e),
                    )
                    text_block_dicts = []

                native_text_blocks: list[TextBlockInput] = []
                for tb in text_block_dicts:
                    native_text_blocks.append(TextBlockInput(
                        id=tb["id"],
                        text=tb["text"],
                        page=tb["page"],
                        bbox=tb["bbox"],
                        font_name=tb.get("font_name"),
                        font_size=tb.get("font_size"),
                    ))

                # Convert AcroForm fields to box candidates for structure labelling
                box_candidates: list[BoxCandidateInput] = []
                for acro_field in acroform_result.fields:
                    box_candidates.append(BoxCandidateInput(
                        id=acro_field.field_name,  # Use field_name as ID for mapping back
                        page=acro_field.bbox.page,
                        bbox=[acro_field.bbox.x, acro_field.bbox.y, acro_field.bbox.width, acro_field.bbox.height],
                        box_type=acro_field.field_type,
                        confidence=1.0,
                    ))

                if page_images and native_text_blocks:
                    logger.info(
                        "Running label linking for AcroForm fields",
                        text_block_count=len(native_text_blocks),
                        box_candidate_count=len(box_candidates),
                    )

                    try:
                        request = StructureLabellingRequest(
                            document_id=job.target_document.id,
                            document_ref=document_ref,
                            page_images=page_images,
                            native_text_blocks=native_text_blocks,
                            box_candidates=box_candidates,
                        )
                        result = await self._structure_labelling_service.process(request)

                        # Build label map from result
                        for field_output in result.fields:
                            # Use box_candidate_id to map back to AcroForm field_name
                            if field_output.box_candidate_id and field_output.name:
                                # Only add if the name is different from the box_candidate_id
                                if field_output.name != field_output.box_candidate_id:
                                    label_map[field_output.box_candidate_id] = field_output.name

                        logger.info(
                            "Label linking completed",
                            labels_linked=len(label_map),
                            total_fields=len(result.fields),
                        )
                    except Exception as e:
                        logger.warning(
                            "Label linking failed, using AcroForm names",
                            error=str(e),
                        )
                else:
                    logger.info(
                        "Skipping label linking",
                        has_page_images=bool(page_images),
                        has_text_blocks=bool(native_text_blocks),
                    )

            # Convert AcroForm fields to FieldModel with linked labels
            fields: list[FieldModel] = []
            for acro_field in acroform_result.fields:
                # Map AcroForm field type to FieldType enum
                field_type_map = {
                    "text": FieldType.TEXT,
                    "checkbox": FieldType.CHECKBOX,
                    "radio": FieldType.RADIO,
                    "combobox": FieldType.TEXT,
                    "listbox": FieldType.TEXT,
                    "signature": FieldType.SIGNATURE,
                    "button": FieldType.TEXT,
                }
                field_type = field_type_map.get(acro_field.field_type, FieldType.TEXT)

                # Use linked label if available, otherwise use AcroForm field name
                field_name = label_map.get(acro_field.field_name, acro_field.field_name)

                field = FieldModel(
                    id=str(uuid4()),
                    name=field_name,
                    field_type=field_type,
                    value=acro_field.value if acro_field.value else None,
                    confidence=1.0,  # AcroForm fields have perfect confidence
                    bbox=acro_field.bbox,
                    document_id=job.target_document.id,
                    page=acro_field.bbox.page,
                    is_required=False,
                    is_editable=not acro_field.readonly,
                )
                fields.append(field)

            activities = [
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.EXTRACTION_COMPLETED,
                    details={
                        "stage": "structure",
                        "fields_detected": len(fields),
                        "detection_method": "acroform_with_labelling" if label_map else "acroform",
                        "labels_linked": len(label_map),
                        "field_types": field_types_count,
                        "success": True,
                    },
                )
            ]

            return StageResult(
                stage=PipelineStage.STRUCTURE,
                success=True,
                issues=[],
                activities=activities,
                updated_fields=fields,
            )

        # Step 2: No AcroForm fields - try StructureLabellingService if available
        if self._structure_labelling_service is not None:
            from app.models.structure_labelling.models import (
                StructureLabellingRequest,
                PageImageInput,
                TextBlockInput,
            )

            # Get document file path and page images
            file_repository = get_file_repository()
            document_path = file_repository.get_path(job.target_document.id)
            document_ref = str(document_path) if document_path else getattr(job.target_document, 'ref', '')

            # Get page images from ingest stage artifacts (if available)
            page_images: list[PageImageInput] = []
            page_count = job.target_document.meta.page_count if job.target_document.meta else 1
            for page_num in range(1, page_count + 1):
                preview_path = file_repository.get_preview_path(job.target_document.id, page_num)
                if preview_path:
                    page_images.append(PageImageInput(
                        page=page_num,
                        image_ref=str(preview_path),
                    ))

            # Extract native text blocks from PDF for label detection
            document_service = DocumentService()
            text_block_dicts = document_service.extract_text_blocks(job.target_document.id)
            native_text_blocks: list[TextBlockInput] = []
            for tb in text_block_dicts:
                native_text_blocks.append(TextBlockInput(
                    id=tb["id"],
                    text=tb["text"],
                    page=tb["page"],
                    bbox=tb["bbox"],
                    font_name=tb.get("font_name"),
                    font_size=tb.get("font_size"),
                ))

            logger.info(
                "Extracted text blocks for labelling",
                document_id=job.target_document.id,
                text_block_count=len(native_text_blocks),
            )

            # Skip LLM labelling if no page images available (ingest stage not run)
            if not page_images:
                logger.warning(
                    "No page images available for structure labelling, skipping LLM detection",
                    has_acroform=False,
                    use_llm=False,
                    reason="no_page_images",
                )
            else:
                logger.info(
                    "No AcroForm fields found, using structure labelling service",
                    has_acroform=False,
                    use_llm=True,
                    page_count=len(page_images),
                    text_block_count=len(native_text_blocks),
                )

                request = StructureLabellingRequest(
                    document_id=job.target_document.id,
                    document_ref=document_ref,
                    page_images=page_images,
                    native_text_blocks=native_text_blocks,
                )
                result = await self._structure_labelling_service.process(request)

                # Convert result fields to FieldModel
                fields = []
                for field_output in result.fields:
                    field = FieldModel(
                        id=field_output.id,
                        name=field_output.name,
                        field_type=FieldType(field_output.field_type) if field_output.field_type in [ft.value for ft in FieldType] else FieldType.TEXT,
                        value=None,
                        confidence=field_output.confidence,
                        bbox=BBox(
                            x=field_output.bbox[0],
                            y=field_output.bbox[1],
                            width=field_output.bbox[2],
                            height=field_output.bbox[3],
                            page=field_output.page,
                        ) if field_output.bbox else None,
                        document_id=job.target_document.id,
                        page=field_output.page,
                        is_required=False,
                        is_editable=True,
                    )
                    fields.append(field)

                logger.info(
                    "Structure labelling completed",
                    total_fields=len(fields),
                    use_llm=True,
                    success=result.success,
                )

                activities = [
                    Activity(
                        id=str(uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        action=ActivityAction.EXTRACTION_COMPLETED,
                        details={
                            "stage": "structure",
                            "fields_detected": len(fields),
                            "detection_method": "llm_labelling",
                            "success": result.success,
                        },
                    )
                ]

                return StageResult(
                    stage=PipelineStage.STRUCTURE,
                    success=result.success,
                    issues=[],
                    activities=activities,
                    updated_fields=fields,
                )

        # Step 3: Mock implementation (fallback for testing)
        logger.warning(
            "No field detection method available, using mock fields",
            has_acroform=False,
            use_llm=False,
        )

        fields = self._generate_target_fields(job)

        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.EXTRACTION_COMPLETED,
                details={
                    "stage": "structure",
                    "fields_detected": len(fields),
                    "detection_method": "mock",
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.STRUCTURE,
            success=True,
            issues=[],
            activities=activities,
            updated_fields=fields,
        )

    async def _execute_labelling(self, job: JobContext) -> StageResult:
        """Execute the labelling stage.

        Uses StructureLabellingServicePort if available (combined with structure).
        """
        # Labelling is typically combined with structure in the service
        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.EXTRACTION_COMPLETED,
                details={
                    "stage": "labelling",
                    "fields_labelled": len(job.fields),
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.LABELLING,
            success=True,
            issues=[],
            activities=activities,
            updated_fields=[],
        )

    async def _execute_map(self, job: JobContext) -> StageResult:
        """Execute the map stage.

        Uses MappingServicePort if available, otherwise returns mock result.
        """
        # Use real service if available
        if self._mapping_service is not None:
            from app.models.mapping.models import MappingRequest, FieldInfo

            if job.mode != JobMode.TRANSFER or job.source_document is None:
                # Scratch mode - no mapping needed
                activities = [
                    Activity(
                        id=str(uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        action=ActivityAction.MAPPING_CREATED,
                        details={"stage": "map", "mode": "scratch", "mappings": 0},
                    )
                ]
                return StageResult(
                    stage=PipelineStage.MAP,
                    success=True,
                    issues=[],
                    activities=activities,
                    updated_fields=[],
                )

            # Get source and target fields
            source_fields_info = [
                FieldInfo(
                    id=f.id,
                    name=f.name,
                    field_type=f.field_type.value,
                    value=f.value,
                )
                for f in job.fields
                if f.document_id == job.source_document.id
            ]
            target_fields_info = [
                FieldInfo(
                    id=f.id,
                    name=f.name,
                    field_type=f.field_type.value,
                    value=None,
                )
                for f in job.fields
                if f.document_id == job.target_document.id
            ]

            mapping_config = get_mapping_config()
            request = MappingRequest(
                job_id=job.id,
                source_fields=source_fields_info,
                target_fields=target_fields_info,
                similarity_threshold=mapping_config.similarity_threshold,
            )
            result = await self._mapping_service.map_fields(request)

            # Convert issues
            issues: list[Issue] = []
            extract_config = get_extract_config()
            for mapping in result.mappings:
                if mapping.confidence < extract_config.low_confidence_warning_threshold or (hasattr(mapping, 'is_ambiguous') and mapping.is_ambiguous):
                    issues.append(
                        Issue(
                            id=str(uuid4()),
                            field_id=mapping.target_field_id,
                            issue_type=IssueType.MAPPING_AMBIGUOUS,
                            message=f"Low confidence mapping ({mapping.confidence:.2f})",
                            severity=IssueSeverity.WARNING,
                            suggested_action="Please verify mapping",
                        )
                    )

            activities = [
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.MAPPING_CREATED,
                    details={
                        "stage": "map",
                        "mappings": len(result.mappings),
                        "source_fields": len(source_fields_info),
                        "target_fields": len(target_fields_info),
                        "success": result.success,
                    },
                )
            ]

            return StageResult(
                stage=PipelineStage.MAP,
                success=result.success,
                issues=issues,
                activities=activities,
                updated_fields=[],
            )

        if job.mode != JobMode.TRANSFER or job.source_document is None:
            return StageResult(
                stage=PipelineStage.MAP,
                success=True,
                issues=[],
                activities=[
                    Activity(
                        id=str(uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        action=ActivityAction.MAPPING_CREATED,
                        details={"stage": "map", "mode": "scratch", "mappings": 0},
                    )
                ],
                updated_fields=[],
            )

        # Mock implementation for transfer mode
        source_fields = self._generate_source_fields(job)
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]
        mappings_created = min(len(source_fields), len(target_fields))

        issues: list[Issue] = []
        if len(target_fields) > 3:
            issues.append(
                Issue(
                    id=str(uuid4()),
                    field_id=target_fields[2].id,
                    issue_type=IssueType.MAPPING_AMBIGUOUS,
                    message="Multiple potential source fields detected",
                    severity=IssueSeverity.WARNING,
                    suggested_action="Please verify mapping",
                )
            )

        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.MAPPING_CREATED,
                details={
                    "stage": "map",
                    "mappings": mappings_created,
                    "source_fields": len(source_fields),
                    "target_fields": len(target_fields),
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.MAP,
            success=True,
            issues=issues,
            activities=activities,
            updated_fields=source_fields,
        )

    async def _execute_extract(self, job: JobContext) -> StageResult:
        """Execute the extract stage.

        Uses ExtractServicePort if available, otherwise returns mock result.
        """
        # Use real service if available
        if self._extract_service is not None:
            return await self._execute_extract_with_service(job)

        # Mock implementation (fallback)
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]
        updated_fields: list[FieldModel] = []
        issues: list[Issue] = []

        for i, field in enumerate(target_fields):
            confidence = 0.5 + (i % 5) * 0.1
            mock_value = self._generate_mock_value(field)

            updated_field = FieldModel(
                id=field.id,
                name=field.name,
                field_type=field.field_type,
                value=mock_value,
                confidence=confidence,
                bbox=field.bbox,
                document_id=field.document_id,
                page=field.page,
                is_required=field.is_required,
                is_editable=field.is_editable,
            )
            updated_fields.append(updated_field)

            if confidence < 0.7:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=field.id,
                        issue_type=IssueType.LOW_CONFIDENCE,
                        message=f"Confidence ({confidence:.2f}) below threshold",
                        severity=IssueSeverity.WARNING,
                        suggested_action="Please verify extracted value",
                    )
                )

        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.EXTRACTION_COMPLETED,
                details={
                    "stage": "extract",
                    "fields_extracted": len(updated_fields),
                    "low_confidence_count": len(issues),
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.EXTRACT,
            success=True,
            issues=issues,
            activities=activities,
            updated_fields=updated_fields,
        )

    async def _execute_extract_with_service(self, job: JobContext) -> StageResult:
        """Execute extract stage using the real ExtractService.

        Args:
            job: Current job context

        Returns:
            StageResult with extracted values and issues
        """
        # Get document file path
        file_repository = get_file_repository()
        document_path = file_repository.get_path(job.target_document.id)
        
        if document_path is None:
            # Fallback to document ref if available
            document_ref = getattr(job.target_document, 'ref', None)
            if document_ref is None:
                # If no path available, return error
                return StageResult(
                    stage=PipelineStage.EXTRACT,
                    success=False,
                    issues=[],
                    activities=[],
                    updated_fields=[],
                    error_message="Document file path not found",
                )
            document_ref_str = str(document_ref)
        else:
            document_ref_str = str(document_path)

        # Get target fields to extract
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]
        
        if not target_fields:
            return StageResult(
                stage=PipelineStage.EXTRACT,
                success=True,
                issues=[],
                activities=[],
                updated_fields=[],
            )

        # Convert FieldModel to ExtractField
        extract_fields = tuple(
            ExtractField(
                field_id=field.id,
                name=field.name,
                field_type=field.field_type.value if isinstance(field.field_type, FieldType) else str(field.field_type),
                page=field.page,
                bbox=field.bbox,
                validation_pattern=None,  # Could be added to FieldModel if needed
            )
            for field in target_fields
        )

        # Create extract request with centralized config
        extract_config = get_extract_config()
        extract_request = ExtractRequest(
            document_ref=document_ref_str,
            fields=extract_fields,
            artifacts=(),  # Page artifacts would come from ingest stage
            use_ocr=True,
            use_llm=True,
            confidence_threshold=extract_config.default_confidence_threshold,
        )

        # Call extract service
        try:
            extract_result = await self._extract_service.extract(extract_request)
        except Exception as e:
            return StageResult(
                stage=PipelineStage.EXTRACT,
                success=False,
                issues=[],
                activities=[],
                updated_fields=[],
                error_message=f"Extraction failed: {str(e)}",
            )

        # Convert ExtractResult to StageResult
        updated_fields: list[FieldModel] = []
        issues: list[Issue] = []

        # Create a mapping of field_id to FieldModel for updates
        field_map = {field.id: field for field in target_fields}

        # Update fields with extracted values
        for extraction in extract_result.extractions:
            field = field_map.get(extraction.field_id)
            if field is None:
                continue

            # Use normalized value if available, otherwise use raw value
            value = extraction.normalized_value or extraction.value

            updated_field = FieldModel(
                id=field.id,
                name=field.name,
                field_type=field.field_type,
                value=value,
                confidence=extraction.confidence,
                bbox=field.bbox,
                document_id=field.document_id,
                page=field.page,
                is_required=field.is_required,
                is_editable=field.is_editable,
            )
            updated_fields.append(updated_field)

            # Create issues for low confidence or conflicts
            if extraction.confidence < extract_request.confidence_threshold:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=field.id,
                        issue_type=IssueType.LOW_CONFIDENCE,
                        message=f"Confidence ({extraction.confidence:.2f}) below threshold",
                        severity=IssueSeverity.WARNING,
                        suggested_action="Please verify extracted value",
                    )
                )

            if extraction.conflict_detected:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=field.id,
                        issue_type=IssueType.MAPPING_AMBIGUOUS,
                        message="Conflicting values detected from different sources",
                        severity=IssueSeverity.WARNING,
                        suggested_action="Please verify extracted value",
                    )
                )

        # Add issues for extraction errors
        for error in extract_result.errors:
            issues.append(
                Issue(
                    id=str(uuid4()),
                    field_id=error.field_id,
                    issue_type=IssueType.LOW_CONFIDENCE,
                    message=error.message,
                    severity=IssueSeverity.WARNING,
                    suggested_action="Please verify field",
                )
            )

        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.EXTRACTION_COMPLETED,
                details={
                    "stage": "extract",
                    "fields_extracted": len(extract_result.extractions),
                    "low_confidence_count": len([i for i in issues if i.issue_type == IssueType.LOW_CONFIDENCE]),
                    "errors_count": len(extract_result.errors),
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.EXTRACT,
            success=extract_result.success,
            issues=issues,
            activities=activities,
            updated_fields=updated_fields,
        )

    async def _execute_adjust(self, job: JobContext) -> StageResult:
        """Execute the adjust stage.

        Uses AdjustServicePort if available, otherwise returns mock result.
        """
        # Use real service if available
        if self._adjust_service is not None:
            from app.models.adjust.models import AdjustRequest, PageMetaInput

            # Get target fields with bboxes
            target_fields = tuple(
                f for f in job.fields
                if f.document_id == job.target_document.id and f.bbox is not None
            )

            # Get page metadata from document
            page_metas = job.target_document.meta.pages if job.target_document.meta and job.target_document.meta.pages else ()
            page_meta_inputs = tuple(
                PageMetaInput(
                    page=pm.page_number,
                    width=pm.width,
                    height=pm.height,
                )
                for pm in page_metas
            )

            # Skip if no fields or no page meta
            if not target_fields:
                return StageResult(
                    stage=PipelineStage.ADJUST,
                    success=True,
                    issues=[],
                    activities=[
                        Activity(
                            id=str(uuid4()),
                            timestamp=datetime.now(timezone.utc),
                            action=ActivityAction.RENDERING_STARTED,
                            details={
                                "stage": "adjust",
                                "skipped": True,
                                "reason": "no_target_fields",
                            },
                        )
                    ],
                    updated_fields=[],
                )

            if not page_meta_inputs:
                # Create default page meta if none available
                page_meta_inputs = tuple(
                    PageMetaInput(page=1, width=612.0, height=792.0)
                    for _ in range(1)
                )

            request = AdjustRequest(
                fields=target_fields,
                issues=tuple(job.issues),
                page_meta=page_meta_inputs,
            )
            result = await self._adjust_service.adjust(request)

            # Convert errors to issues
            issues: list[Issue] = []
            for error in result.errors:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=error.field_id,
                        issue_type=IssueType.LAYOUT_ISSUE,
                        message=error.message,
                        severity=IssueSeverity.WARNING,
                        suggested_action="Review layout",
                    )
                )

            activities = [
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.RENDERING_STARTED,
                    details={
                        "stage": "adjust",
                        "layout_issues": len(issues),
                        "success": result.success,
                    },
                )
            ]

            return StageResult(
                stage=PipelineStage.ADJUST,
                success=result.success,
                issues=issues,
                activities=activities,
                updated_fields=[],
            )

        # Mock implementation (fallback)
        issues: list[Issue] = []
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]

        for field in target_fields:
            if field.value and len(str(field.value)) > 50:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=field.id,
                        issue_type=IssueType.LAYOUT_ISSUE,
                        message="Value may overflow field boundary",
                        severity=IssueSeverity.INFO,
                        suggested_action="Consider truncating or resizing",
                    )
                )

        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.RENDERING_STARTED,
                details={
                    "stage": "adjust",
                    "layout_issues": len(issues),
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.ADJUST,
            success=True,
            issues=issues,
            activities=activities,
            updated_fields=[],
        )

    async def _execute_fill(self, job: JobContext) -> StageResult:
        """Execute the fill stage.

        Uses FillServicePort if available, otherwise returns mock result.
        """
        # Use real service if available
        if self._fill_service is not None:
            from app.models.fill.models import FillRequest, FillValue, FillBBox

            # Get document file path
            file_repository = get_file_repository()
            document_path = file_repository.get_path(job.target_document.id)
            document_ref = str(document_path) if document_path else getattr(job.target_document, 'ref', '')

            # Get target fields with values
            target_fields = [
                f for f in job.fields
                if f.document_id == job.target_document.id and f.value is not None
            ]

            # Convert to FillValue format
            fill_values = tuple(
                FillValue(
                    field_id=f.id,
                    value=str(f.value),
                    bbox=FillBBox(
                        x=f.bbox.x,
                        y=f.bbox.y,
                        width=f.bbox.width,
                        height=f.bbox.height,
                        page=f.bbox.page,
                    ) if f.bbox else None,
                )
                for f in target_fields
            )

            request = FillRequest(
                target_document_ref=document_ref,
                fields=fill_values,
            )
            result = await self._fill_service.fill(request)

            # Convert issues
            issues: list[Issue] = []
            for field_result in result.field_results:
                for issue in field_result.issues:
                    issues.append(
                        Issue(
                            id=str(uuid4()),
                            field_id=field_result.field_id,
                            issue_type=IssueType.LAYOUT_ISSUE,
                            message=issue.message,
                            severity=IssueSeverity.WARNING,
                        )
                    )

            activities = [
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.RENDERING_COMPLETED,
                    details={
                        "stage": "fill",
                        "fields_filled": result.filled_count,
                        "failed_count": result.failed_count,
                        "success": result.success,
                        "filled_document_ref": result.filled_document_ref,
                    },
                )
            ]

            return StageResult(
                stage=PipelineStage.FILL,
                success=result.success,
                issues=issues,
                activities=activities,
                updated_fields=[],
            )

        # Mock implementation (fallback)
        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.RENDERING_COMPLETED,
                details={
                    "stage": "fill",
                    "fields_filled": len([f for f in job.fields if f.value is not None]),
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.FILL,
            success=True,
            issues=[],
            activities=activities,
            updated_fields=[],
        )

    async def _execute_review(self, job: JobContext) -> StageResult:
        """Execute the review stage.

        Uses ReviewServicePort if available, otherwise returns mock result.
        """
        # Use real service if available
        if self._review_service is not None:
            from app.models.review.models import ReviewRequest

            # Get document file path - use filled document if available
            file_repository = get_file_repository()
            document_path = file_repository.get_path(job.target_document.id)
            document_ref = str(document_path) if document_path else getattr(job.target_document, 'ref', '')

            # Check if we have a filled document from the fill stage
            filled_document_ref = document_ref
            for activity in job.activities:
                if activity.action == ActivityAction.RENDERING_COMPLETED:
                    filled_ref = activity.details.get("filled_document_ref")
                    if filled_ref:
                        filled_document_ref = filled_ref
                        break

            # Get target fields
            target_fields = [f for f in job.fields if f.document_id == job.target_document.id]

            request = ReviewRequest(
                document_id=job.target_document.id,
                filled_document_ref=filled_document_ref,
                original_document_ref=document_ref,
                fields=target_fields,
            )
            result = await self._review_service.review(request)

            # Convert issues
            issues: list[Issue] = []
            for issue in result.issues:
                issues.append(
                    Issue(
                        id=issue.id,
                        field_id=issue.field_id,
                        issue_type=IssueType(issue.issue_type.value) if hasattr(issue.issue_type, 'value') else issue.issue_type,
                        message=issue.message,
                        severity=IssueSeverity(issue.severity.value) if hasattr(issue.severity, 'value') else issue.severity,
                        suggested_action=issue.suggested_action,
                    )
                )

            activities = [
                Activity(
                    id=str(uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    action=ActivityAction.JOB_COMPLETED if result.critical_issues == 0 else ActivityAction.QUESTION_ASKED,
                    details={
                        "stage": "review",
                        "issues": result.total_issues,
                        "critical_issues": result.critical_issues,
                        "status": "complete" if result.critical_issues == 0 else "needs_review",
                        "success": result.success,
                    },
                )
            ]

            return StageResult(
                stage=PipelineStage.REVIEW,
                success=result.success,
                issues=issues,
                activities=activities,
                updated_fields=[],
            )

        # Mock implementation (fallback)
        issues: list[Issue] = []
        target_fields = [f for f in job.fields if f.document_id == job.target_document.id]

        for field in target_fields:
            if field.is_required and field.value is None:
                issues.append(
                    Issue(
                        id=str(uuid4()),
                        field_id=field.id,
                        issue_type=IssueType.MISSING_VALUE,
                        message=f"Required field '{field.name}' has no value",
                        severity=IssueSeverity.HIGH,
                        suggested_action="Please provide a value",
                    )
                )

        activities = [
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=ActivityAction.JOB_COMPLETED if not issues else ActivityAction.QUESTION_ASKED,
                details={
                    "stage": "review",
                    "issues": len(issues),
                    "status": "complete" if not issues else "needs_review",
                },
            )
        ]

        return StageResult(
            stage=PipelineStage.REVIEW,
            success=True,
            issues=issues,
            activities=activities,
            updated_fields=[],
        )

    def _generate_target_fields(self, job: JobContext) -> list[FieldModel]:
        """Generate mock fields for the target document."""
        if job.fields:
            return []

        field_configs = [
            ("Name", FieldType.TEXT, True),
            ("Date", FieldType.DATE, True),
            ("Amount", FieldType.NUMBER, True),
            ("Description", FieldType.TEXT, False),
            ("Signature", FieldType.SIGNATURE, False),
        ]

        fields = []
        for i, (name, field_type, is_required) in enumerate(field_configs):
            field = FieldModel(
                id=str(uuid4()),
                name=name,
                field_type=field_type,
                value=None,
                confidence=None,
                bbox=BBox(
                    x=50.0,
                    y=100.0 + (i * 50),
                    width=200.0,
                    height=30.0,
                    page=1,
                ),
                document_id=job.target_document.id,
                page=1,
                is_required=is_required,
                is_editable=True,
            )
            fields.append(field)

        return fields

    def _generate_source_fields(self, job: JobContext) -> list[FieldModel]:
        """Generate mock fields for the source document."""
        if job.source_document is None:
            return []

        existing_source_fields = [
            f for f in job.fields
            if f.document_id == job.source_document.id
        ]
        if existing_source_fields:
            return []

        field_configs = [
            ("Full Name", FieldType.TEXT, "John Doe"),
            ("Transaction Date", FieldType.DATE, "2024-01-15"),
            ("Total Amount", FieldType.NUMBER, "1,234.56"),
            ("Notes", FieldType.TEXT, "Invoice for services rendered"),
            ("Authorized By", FieldType.SIGNATURE, None),
        ]

        fields = []
        for i, (name, field_type, value) in enumerate(field_configs):
            field = FieldModel(
                id=str(uuid4()),
                name=name,
                field_type=field_type,
                value=value,
                confidence=0.9 if value else None,
                bbox=BBox(
                    x=50.0,
                    y=100.0 + (i * 50),
                    width=200.0,
                    height=30.0,
                    page=1,
                ),
                document_id=job.source_document.id,
                page=1,
                is_required=False,
                is_editable=False,
            )
            fields.append(field)

        return fields

    def _generate_mock_value(self, field: FieldModel) -> str | None:
        """Generate a mock value based on field type."""
        mock_values = {
            FieldType.TEXT: f"Sample {field.name}",
            FieldType.NUMBER: "123.45",
            FieldType.DATE: "2024-01-15",
            FieldType.CHECKBOX: "true",
            FieldType.RADIO: "Option A",
            FieldType.SIGNATURE: None,
        }
        return mock_values.get(field.field_type, f"Value for {field.name}")
