"""Conversation Agent for Agent Chat UI.

This service handles the core agent logic for the conversational form-filling flow.
It receives user messages, detects document types, and orchestrates the form filling pipeline.

The agent transitions through stages:
- IDLE: Initial state, waiting for documents
- ANALYZING: Analyzing uploaded documents
- CONFIRMING: Waiting for user to confirm document roles
- MAPPING: Mapping source data to form fields
- FILLING: Filling the form with extracted/provided data
- REVIEWING: User reviewing the filled form
- COMPLETE: Form filling completed, PDF ready
- ERROR: An error occurred

For MVP, this provides stub implementations that simulate the agent behavior.
"""

import re
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.conversation import (
    AgentStage,
    AgentState,
    Attachment,
    DetectedDocument,
    Message,
    MessageRole,
)
from app.models.edit import EditRequest
from app.repositories import ConversationRepository, EditRepository, MessageRepository
from app.services.conversation_logger import log
from app.services.edit import EditService


class AgentResponse(BaseModel):
    """Response from the conversation agent."""

    message: Message = Field(..., description="Agent response message")
    new_stage: AgentStage = Field(..., description="New agent stage")
    detected_documents: list[DetectedDocument] = Field(
        default_factory=list,
        description="Newly detected documents",
    )

    model_config = {"frozen": True}


class DocumentDetectionResult(BaseModel):
    """Result of document type detection."""

    document_type: str = Field(..., description="Detected type: form or source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    has_acroform: bool = Field(default=False, description="Whether PDF has AcroForm fields")
    page_count: int = Field(default=1, ge=1, description="Number of pages")

    model_config = {"frozen": True}


class ConversationAgent:
    """Agent that handles conversational form filling.

    This agent manages the conversation state and orchestrates
    the form filling pipeline through natural language interaction.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        edit_repo: EditRepository | None = None,
    ) -> None:
        """Initialize the conversation agent.

        Args:
            conversation_repo: Repository for conversation persistence.
            message_repo: Repository for message persistence.
            edit_repo: Optional repository for edit operations.
        """
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._edit_repo = edit_repo
        self._edit_service = EditService(edit_repo) if edit_repo else None

    async def process_message(
        self,
        conversation_id: str,
        user_message: Message,
        attachments: list[Attachment] | None = None,
    ) -> AgentResponse:
        """Process a user message and generate an agent response.

        Args:
            conversation_id: ID of the conversation.
            user_message: The user's message.
            attachments: Optional file attachments.

        Returns:
            AgentResponse containing the agent's message and state changes.
        """
        # Get current agent state
        state = self._conversation_repo.get_agent_state(conversation_id)
        if state is None:
            # Create initial state if missing
            state = AgentState(
                conversation_id=conversation_id,
                current_stage=AgentStage.IDLE,
                detected_documents=[],
                form_fields=[],
                extracted_values=[],
                pending_questions=[],
                last_error=None,
                retry_count=0,
                last_activity=datetime.now(timezone.utc),
            )
            self._conversation_repo.save_agent_state(state)

        # Log agent thinking
        log.agent_thinking(
            conversation_id=conversation_id,
            stage=state.current_stage.value,
            message=f"Processing user message: {user_message.content[:50]}...",
        )

        # Process based on current stage
        if attachments and len(attachments) > 0:
            return await self._handle_file_upload(conversation_id, state, user_message, attachments)

        # Handle text-only messages based on stage
        stage_handlers = {
            AgentStage.IDLE: self._handle_idle_message,
            AgentStage.ANALYZING: self._handle_analyzing_message,
            AgentStage.CONFIRMING: self._handle_confirming_message,
            AgentStage.MAPPING: self._handle_mapping_message,
            AgentStage.FILLING: self._handle_filling_message,
            AgentStage.REVIEWING: self._handle_reviewing_message,
            AgentStage.COMPLETE: self._handle_complete_message,
            AgentStage.ERROR: self._handle_error_message,
        }

        handler = stage_handlers.get(state.current_stage, self._handle_default)
        return await handler(conversation_id, state, user_message)

    async def _handle_file_upload(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
        attachments: list[Attachment],
    ) -> AgentResponse:
        """Handle file uploads.

        Detects document types (form vs source) and transitions to ANALYZING stage.
        """
        log.agent_stage_change(
            conversation_id=conversation_id,
            from_stage=state.current_stage.value,
            to_stage=AgentStage.ANALYZING.value,
        )

        # Detect document types (stub implementation)
        detected_docs: list[DetectedDocument] = []
        for attachment in attachments:
            detection = self._detect_document_type(attachment)
            detected = DetectedDocument(
                document_id=attachment.id,
                filename=attachment.filename,
                document_type=detection.document_type,
                confidence=detection.confidence,
                page_count=detection.page_count,
                preview_ref=None,
            )
            detected_docs.append(detected)

            log.document_detected(
                conversation_id=conversation_id,
                document_id=attachment.id,
                document_type=detection.document_type,
                filename=attachment.filename,
                page_count=detection.page_count,
                confidence=detection.confidence,
            )

        # Build response message
        form_docs = [d for d in detected_docs if d.document_type == "form"]
        source_docs = [d for d in detected_docs if d.document_type == "source"]

        if form_docs and source_docs:
            content = self._build_multi_doc_response(form_docs, source_docs)
            new_stage = AgentStage.CONFIRMING
        elif form_docs:
            content = self._build_form_only_response(form_docs)
            new_stage = AgentStage.CONFIRMING
        elif source_docs:
            content = self._build_source_only_response(source_docs)
            new_stage = AgentStage.IDLE  # Need form document
        else:
            content = "I couldn't identify the document types. Please upload a PDF form to fill."
            new_stage = AgentStage.IDLE

        # Create agent message
        now = datetime.now(timezone.utc)
        agent_message = Message(
            id=str(uuid4()),
            role=MessageRole.AGENT,
            content=content,
            thinking="Analyzed uploaded documents to detect form vs source",
            preview_ref=None,
            approval_required=False,
            approval_status=None,
            attachments=[],
            metadata={"detected_documents": [d.model_dump() for d in detected_docs]},
            created_at=now,
        )

        # Update agent state
        updated_state = AgentState(
            conversation_id=conversation_id,
            current_stage=new_stage,
            detected_documents=[*state.detected_documents, *detected_docs],
            form_fields=state.form_fields,
            extracted_values=state.extracted_values,
            pending_questions=state.pending_questions,
            last_error=None,
            retry_count=0,
            last_activity=now,
        )
        self._conversation_repo.save_agent_state(updated_state)

        log.agent_response(
            conversation_id=conversation_id,
            message_id=agent_message.id,
            content_preview=content[:50],
            has_preview=False,
            requires_approval=False,
        )

        return AgentResponse(
            message=agent_message,
            new_stage=new_stage,
            detected_documents=detected_docs,
        )

    def _detect_document_type(self, attachment: Attachment) -> DocumentDetectionResult:
        """Detect document type based on filename and content type.

        Stub implementation for MVP. Real implementation would:
        1. Check for AcroForm fields using PyMuPDF
        2. Analyze content to detect form structure
        3. Use LLM vision to classify document type
        """
        filename_lower = attachment.filename.lower()

        # Simple heuristics based on filename
        form_keywords = ["form", "application", "blank", "fillable", "template"]
        source_keywords = ["invoice", "receipt", "statement", "report", "data", "source"]

        is_form = any(keyword in filename_lower for keyword in form_keywords)
        is_source = any(keyword in filename_lower for keyword in source_keywords)

        if is_form and not is_source:
            return DocumentDetectionResult(
                document_type="form",
                confidence=0.8,
                has_acroform=True,
                page_count=1,
            )
        elif is_source and not is_form:
            return DocumentDetectionResult(
                document_type="source",
                confidence=0.8,
                has_acroform=False,
                page_count=1,
            )
        else:
            # Default to form if PDF
            if attachment.content_type == "application/pdf":
                return DocumentDetectionResult(
                    document_type="form",
                    confidence=0.5,
                    has_acroform=False,
                    page_count=1,
                )
            else:
                return DocumentDetectionResult(
                    document_type="source",
                    confidence=0.6,
                    has_acroform=False,
                    page_count=1,
                )

    def _build_multi_doc_response(
        self,
        form_docs: list[DetectedDocument],
        source_docs: list[DetectedDocument],
    ) -> str:
        """Build response for when both form and source documents are detected."""
        form_names = ", ".join(d.filename for d in form_docs)
        source_names = ", ".join(d.filename for d in source_docs)

        return (
            f"I found the following documents:\n\n"
            f"**Form to fill:** {form_names}\n"
            f"**Source data:** {source_names}\n\n"
            f"Is this correct? I'll extract data from the source and fill the form.\n\n"
            f"[Yes, proceed] [Switch roles]"
        )

    def _build_form_only_response(self, form_docs: list[DetectedDocument]) -> str:
        """Build response for when only form documents are detected."""
        form_names = ", ".join(d.filename for d in form_docs)

        return (
            f"I found a form to fill: **{form_names}**\n\n"
            f"Would you like to:\n"
            f"1. Upload a source document with data to extract\n"
            f"2. Enter the information manually through chat\n\n"
            f"[Upload source] [Enter manually]"
        )

    def _build_source_only_response(self, source_docs: list[DetectedDocument]) -> str:
        """Build response for when only source documents are detected."""
        source_names = ", ".join(d.filename for d in source_docs)

        return (
            f"I found source documents: **{source_names}**\n\n"
            f"Please upload the form (blank PDF) that you want to fill."
        )

    async def _handle_idle_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in IDLE stage."""
        content = (
            "Hello! I can help you fill out PDF forms. "
            "Please upload a PDF form to get started, or "
            "drop both a form and source document at once."
        )

        return self._create_simple_response(conversation_id, content, AgentStage.IDLE)

    async def _handle_analyzing_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in ANALYZING stage."""
        content = "I'm still analyzing your documents. This should only take a moment..."

        return self._create_simple_response(conversation_id, content, AgentStage.ANALYZING)

    async def _handle_confirming_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in CONFIRMING stage."""
        message_lower = user_message.content.lower()

        # Check for confirmation
        if any(word in message_lower for word in ["yes", "proceed", "correct", "ok", "okay"]):
            log.agent_stage_change(
                conversation_id=conversation_id,
                from_stage=AgentStage.CONFIRMING.value,
                to_stage=AgentStage.FILLING.value,
            )

            content = (
                "Great! I'm now analyzing the form structure and extracting data. "
                "This may take a moment...\n\n"
                "**Processing:**\n"
                "- Detecting form fields...\n"
                "- Extracting data from source...\n"
                "- Mapping values..."
            )

            # Update state to FILLING
            now = datetime.now(timezone.utc)
            updated_state = AgentState(
                conversation_id=conversation_id,
                current_stage=AgentStage.FILLING,
                detected_documents=state.detected_documents,
                form_fields=state.form_fields,
                extracted_values=state.extracted_values,
                pending_questions=state.pending_questions,
                last_error=None,
                retry_count=0,
                last_activity=now,
            )
            self._conversation_repo.save_agent_state(updated_state)

            return self._create_simple_response(conversation_id, content, AgentStage.FILLING)

        elif "switch" in message_lower:
            content = (
                "I've switched the document roles. "
                "Please confirm the new assignment or describe what you'd like to change."
            )
            return self._create_simple_response(conversation_id, content, AgentStage.CONFIRMING)

        else:
            content = (
                "Please confirm if the document roles are correct, "
                "or let me know if you'd like to switch them."
            )
            return self._create_simple_response(conversation_id, content, AgentStage.CONFIRMING)

    async def _handle_mapping_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in MAPPING stage."""
        content = "I'm mapping the extracted data to form fields. Almost done..."

        return self._create_simple_response(conversation_id, content, AgentStage.MAPPING)

    async def _handle_filling_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in FILLING stage.

        For MVP, simulate completion and transition to REVIEWING.
        """
        log.agent_stage_change(
            conversation_id=conversation_id,
            from_stage=AgentStage.FILLING.value,
            to_stage=AgentStage.REVIEWING.value,
        )

        content = (
            "I've filled the form with the extracted data!\n\n"
            "**Summary:**\n"
            "- 12 fields detected\n"
            "- 10 fields filled automatically\n"
            "- 2 fields need your input\n\n"
            "Please review the preview and let me know if anything needs to be changed.\n\n"
            "[Approve] [Edit fields]"
        )

        # Update state to REVIEWING
        now = datetime.now(timezone.utc)
        updated_state = AgentState(
            conversation_id=conversation_id,
            current_stage=AgentStage.REVIEWING,
            detected_documents=state.detected_documents,
            form_fields=state.form_fields,
            extracted_values=state.extracted_values,
            pending_questions=state.pending_questions,
            last_error=None,
            retry_count=0,
            last_activity=now,
        )
        self._conversation_repo.save_agent_state(updated_state)

        return self._create_approval_response(conversation_id, content, AgentStage.REVIEWING)

    async def _handle_reviewing_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in REVIEWING stage."""
        message_lower = user_message.content.lower()

        if any(word in message_lower for word in ["approve", "yes", "looks good", "ok", "okay"]):
            log.agent_stage_change(
                conversation_id=conversation_id,
                from_stage=AgentStage.REVIEWING.value,
                to_stage=AgentStage.COMPLETE.value,
            )

            content = (
                "The form has been completed and saved.\n\n"
                "[Download PDF]\n\n"
                "Is there anything else you'd like me to help with?"
            )

            # Update state to COMPLETE
            now = datetime.now(timezone.utc)
            updated_state = AgentState(
                conversation_id=conversation_id,
                current_stage=AgentStage.COMPLETE,
                detected_documents=state.detected_documents,
                form_fields=state.form_fields,
                extracted_values=state.extracted_values,
                pending_questions=[],
                last_error=None,
                retry_count=0,
                last_activity=now,
            )
            self._conversation_repo.save_agent_state(updated_state)

            log.conversation_completed(
                conversation_id=conversation_id,
                duration_seconds=None,  # Would calculate from conversation start
                message_count=None,
            )

            return self._create_simple_response(conversation_id, content, AgentStage.COMPLETE)

        # Try to parse edit commands
        edit_result = self._parse_edit_command(user_message.content)
        if edit_result and self._edit_service:
            return await self._handle_edit_command(conversation_id, state, edit_result)

        if "edit" in message_lower or "change" in message_lower:
            content = (
                "What would you like to change? "
                "You can say something like 'change [field name] to [value]' "
                "or click on a field in the preview."
            )
            return self._create_simple_response(conversation_id, content, AgentStage.REVIEWING)

        else:
            content = (
                "Would you like to approve the form or make any changes? "
                "Click [Approve] when ready or describe what you'd like to edit."
            )
            return self._create_approval_response(conversation_id, content, AgentStage.REVIEWING)

    async def _handle_complete_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in COMPLETE stage."""
        content = (
            "Your form is ready! You can download it using the button above.\n\n"
            "Would you like to fill another form or make changes to this one?"
        )

        return self._create_simple_response(conversation_id, content, AgentStage.COMPLETE)

    async def _handle_error_message(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Handle messages in ERROR stage."""
        content = (
            "I encountered an error. Let me try again.\n\n"
            "You can also start over by uploading new documents."
        )

        # Reset to IDLE
        now = datetime.now(timezone.utc)
        updated_state = AgentState(
            conversation_id=conversation_id,
            current_stage=AgentStage.IDLE,
            detected_documents=[],
            form_fields=[],
            extracted_values=[],
            pending_questions=[],
            last_error=None,
            retry_count=0,
            last_activity=now,
        )
        self._conversation_repo.save_agent_state(updated_state)

        return self._create_simple_response(conversation_id, content, AgentStage.IDLE)

    async def _handle_default(
        self,
        conversation_id: str,
        state: AgentState,
        user_message: Message,
    ) -> AgentResponse:
        """Default handler for unknown stages."""
        content = "I'm not sure how to help with that. Please upload a PDF form to get started."

        return self._create_simple_response(conversation_id, content, AgentStage.IDLE)

    def _parse_edit_command(
        self,
        message: str,
    ) -> list[tuple[str, str]] | None:
        """Parse edit commands from a message.

        Recognizes patterns like:
        - "change [field] to [value]"
        - "set [field] to [value]"
        - "update [field] to [value]"
        - "[field] = [value]"

        Args:
            message: The user message to parse.

        Returns:
            List of (field_id, value) tuples, or None if no edits found.
        """
        edits: list[tuple[str, str]] = []

        # Pattern: change/set/update [field_name] to [value]
        # Field name is a single word (underscore/hyphen allowed)
        # Value continues until 'and [verb]' or real end of string/sentence
        # Use negative lookahead for sentence-ending punctuation not preceded by word chars
        pattern1 = r"(?:change|set|update)\s+(?:the\s+)?([a-zA-Z][a-zA-Z0-9_-]*)\s+to\s+['\"]?(.+?)['\"]?(?=\s+and\s+(?:change|set|update)|$|\s*[!?](?:\s|$))"
        matches1 = re.findall(pattern1, message, re.IGNORECASE)
        for field, value in matches1:
            # Clean trailing periods that aren't part of the value
            clean_value = value.rstrip(".")
            # But keep domain-like patterns (e.g., .com)
            if value.endswith(".") and not re.search(r"\.\w+$", clean_value):
                value = clean_value
            edits.append((field.strip(), value.strip()))

        # Pattern: [field] = [value] (value is non-whitespace chars)
        pattern2 = r"\b([a-zA-Z][a-zA-Z0-9_-]*)\s*=\s*['\"]?([^\s'\"]+)['\"]?"
        matches2 = re.findall(pattern2, message)
        for field, value in matches2:
            edits.append((field.strip(), value.strip()))

        return edits if edits else None

    async def _handle_edit_command(
        self,
        conversation_id: str,
        state: AgentState,
        edits: list[tuple[str, str]],
    ) -> AgentResponse:
        """Handle parsed edit commands.

        Args:
            conversation_id: ID of the conversation.
            state: Current agent state.
            edits: List of (field_id, value) tuples to apply.

        Returns:
            AgentResponse confirming the edits.
        """
        if not self._edit_service:
            return self._create_simple_response(
                conversation_id,
                "Edit functionality is not available.",
                AgentStage.REVIEWING,
            )

        edit_requests = [
            EditRequest(field_id=field_id, value=value, source="chat") for field_id, value in edits
        ]

        if len(edit_requests) == 1:
            # Single edit
            result = self._edit_service.apply_edit(conversation_id, edit_requests[0])
            content = result.message
        else:
            # Batch edit
            result = self._edit_service.apply_batch_edits(conversation_id, edit_requests)
            content = result.summary

        log.agent_thinking(
            conversation_id=conversation_id,
            stage="reviewing",
            message=f"Applied {len(edit_requests)} edit(s) from chat command",
        )

        # Build a more detailed response
        full_content = f"{content}\n\nThe preview has been updated. Would you like to make more changes or approve the form?"

        return self._create_simple_response(conversation_id, full_content, AgentStage.REVIEWING)

    def _create_simple_response(
        self,
        conversation_id: str,
        content: str,
        new_stage: AgentStage,
    ) -> AgentResponse:
        """Create a simple agent response without approval."""
        now = datetime.now(timezone.utc)
        message = Message(
            id=str(uuid4()),
            role=MessageRole.AGENT,
            content=content,
            thinking=None,
            preview_ref=None,
            approval_required=False,
            approval_status=None,
            attachments=[],
            metadata={},
            created_at=now,
        )

        log.agent_response(
            conversation_id=conversation_id,
            message_id=message.id,
            content_preview=content[:50],
            has_preview=False,
            requires_approval=False,
        )

        return AgentResponse(
            message=message,
            new_stage=new_stage,
            detected_documents=[],
        )

    def _create_approval_response(
        self,
        conversation_id: str,
        content: str,
        new_stage: AgentStage,
    ) -> AgentResponse:
        """Create an agent response that requires approval."""
        now = datetime.now(timezone.utc)
        message = Message(
            id=str(uuid4()),
            role=MessageRole.AGENT,
            content=content,
            thinking=None,
            preview_ref=None,
            approval_required=True,
            approval_status=None,
            attachments=[],
            metadata={},
            created_at=now,
        )

        log.agent_response(
            conversation_id=conversation_id,
            message_id=message.id,
            content_preview=content[:50],
            has_preview=False,
            requires_approval=True,
        )

        log.approval_requested(
            conversation_id=conversation_id,
            message_id=message.id,
            fields_to_approve=0,
        )

        return AgentResponse(
            message=message,
            new_stage=new_stage,
            detected_documents=[],
        )
