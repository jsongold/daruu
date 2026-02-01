"""Conversation routes for Agent Chat UI.

Based on PRD: docs/prd/agent-chat-ui.md
API version: v2

Endpoints:
- POST   /api/v2/conversations           - Create new conversation
- GET    /api/v2/conversations           - List conversations
- GET    /api/v2/conversations/{id}      - Get conversation with messages
- DELETE /api/v2/conversations/{id}      - Delete/abandon conversation
- POST   /api/v2/conversations/{id}/messages  - Send message
- GET    /api/v2/conversations/{id}/messages  - Get messages (paginated)
- GET    /api/v2/conversations/{id}/stream    - SSE stream
- POST   /api/v2/conversations/{id}/approve   - Approve preview
- GET    /api/v2/conversations/{id}/download  - Download filled PDF
"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.infrastructure.repositories import (
    get_conversation_repository,
    get_edit_repository,
    get_message_repository,
)
from app.models.conversation import (
    ApprovalStatus,
    ApprovePreviewRequest,
    Attachment,
    Conversation,
    ConversationListResponse,
    ConversationStatus,
    ConversationWithMessages,
    CreateConversationRequest,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    Message,
    MessageListResponse,
    MessageRole,
)
from app.repositories import ConversationRepository, EditRepository, MessageRepository
from app.services.agents.conversation_agent import ConversationAgent
from app.services.conversation_logger import log

router = APIRouter(prefix="/api/v2/conversations", tags=["conversations"])


# ============================================
# Dependencies
# ============================================


async def get_current_user_id() -> str:
    """Get the authenticated user ID.

    TODO: Replace with actual auth from Supabase.
    """
    return "stub-user-id"


def get_conversation_repo() -> ConversationRepository:
    """Get the conversation repository."""
    return get_conversation_repository()


def get_message_repo() -> MessageRepository:
    """Get the message repository."""
    return get_message_repository()


def get_edit_repo() -> EditRepository:
    """Get the edit repository."""
    return get_edit_repository()


def get_agent(
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
    edit_repo: EditRepository = Depends(get_edit_repo),
) -> ConversationAgent:
    """Get the conversation agent."""
    return ConversationAgent(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        edit_repo=edit_repo,
    )


# ============================================
# Route Handlers
# ============================================


@router.post(
    "",
    response_model=Conversation,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    responses={
        201: {"description": "Conversation created"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def create_conversation(
    request: CreateConversationRequest | None = None,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> Conversation:
    """Create a new conversation.

    Creates a new conversation for the authenticated user.
    Title is optional and will be auto-generated if not provided.
    """
    title = request.title if request and request.title else None

    # Create conversation in repository
    conversation = conversation_repo.create(user_id=user_id, title=title)

    # Log conversation creation
    log.conversation_created(conversation.id, user_id, conversation.title)

    return conversation


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List user's conversations",
    responses={
        200: {"description": "List of conversations"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def list_conversations(
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status: active, completed, all"),
    ] = "all",
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 20,
    cursor: Annotated[str | None, Query(description="Pagination cursor")] = None,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> ConversationListResponse:
    """List user's conversations.

    Returns paginated list of conversations sorted by updated_at descending.
    """
    items, next_cursor = conversation_repo.list_by_user(
        user_id=user_id,
        status_filter=status_filter,
        limit=limit,
        cursor=cursor,
    )

    return ConversationListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/{conversation_id}",
    response_model=ConversationWithMessages,
    summary="Get conversation with recent messages",
    responses={
        200: {"description": "Conversation with messages"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
) -> ConversationWithMessages:
    """Get a conversation with its recent messages.

    Returns the conversation details along with the most recent messages.
    """
    # Verify user ownership
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    # Get recent messages
    messages, _ = message_repo.list_by_conversation(conversation_id, limit=50)

    return ConversationWithMessages(
        conversation=conversation,
        messages=messages,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete/abandon a conversation",
    responses={
        204: {"description": "Conversation deleted"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
) -> None:
    """Delete or abandon a conversation.

    Sets the conversation status to 'abandoned' and marks it for cleanup.
    """
    # Verify user ownership
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    # Update status to abandoned
    conversation_repo.update_status(conversation_id, ConversationStatus.ABANDONED)

    # Log abandonment
    log.conversation_abandoned(conversation_id, reason="User deleted")


@router.post(
    "/{conversation_id}/messages",
    response_model=Message,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a message (text or file upload)",
    responses={
        202: {"description": "Message accepted, agent processing"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
        429: {"model": ErrorResponse, "description": "Rate limited"},
    },
)
async def send_message(
    conversation_id: str,
    content: Annotated[str | None, Form(description="Text message content")] = None,
    files: Annotated[
        list[UploadFile] | None,
        File(description="Files to upload (max 5)"),
    ] = None,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
    agent: ConversationAgent = Depends(get_agent),
) -> Message:
    """Send a message to the conversation.

    Accepts text content and/or file uploads.
    Files are limited to 5 per message, max 50MB each.
    Supported formats: PDF, PNG, JPG, TIFF.

    Returns 202 Accepted as the agent will process asynchronously.
    Subscribe to SSE stream for real-time updates.
    """
    # Verify conversation exists and user owns it
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    # Check if conversation is still active
    if conversation.status == ConversationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_COMPLETED,
                    message="Cannot modify completed conversation",
                )
            ).model_dump(),
        )

    # Validate input
    if not content and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either content or files must be provided",
        )

    # Validate file count
    if files and len(files) > 5:
        log.error(
            conversation_id=conversation_id,
            error_code="TOO_MANY_FILES",
            message=f"User tried to upload {len(files)} files (max 5)",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.TOO_MANY_FILES,
                    message="Maximum 5 files per message",
                )
            ).model_dump(),
        )

    # Validate file types and sizes
    allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
    max_size = 50 * 1024 * 1024  # 50MB
    attachments: list[Attachment] = []

    if files:
        for file in files:
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorResponse(
                        error=ErrorDetail(
                            code=ErrorCode.INVALID_FILE_TYPE,
                            message="Only PDF and image files are supported",
                        )
                    ).model_dump(),
                )

            # Check file size
            file.file.seek(0, 2)  # Seek to end
            size = file.file.tell()
            file.file.seek(0)  # Reset

            if size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorResponse(
                        error=ErrorDetail(
                            code=ErrorCode.FILE_TOO_LARGE,
                            message="File exceeds 50MB limit",
                        )
                    ).model_dump(),
                )

            # Create attachment (in real impl, would store file first)
            attachment = Attachment(
                id=str(uuid4()),
                filename=file.filename or "unknown",
                content_type=file.content_type or "application/octet-stream",
                size_bytes=size,
                ref=f"temp://{file.filename}",  # Placeholder ref
                document_id=None,
            )
            attachments.append(attachment)

            log.file_uploaded(
                conversation_id=conversation_id,
                message_id="pending",
                filename=file.filename or "unknown",
                content_type=file.content_type or "application/octet-stream",
                size_bytes=size,
            )

    # Create user message
    user_message = message_repo.create(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=content or "[File upload]",
        attachments=attachments if attachments else None,
    )

    log.message_received(
        conversation_id=conversation_id,
        message_id=user_message.id,
        content_preview=content,
        has_files=bool(files),
        file_count=len(files) if files else 0,
    )

    # Process with agent
    agent_response = await agent.process_message(
        conversation_id=conversation_id,
        user_message=user_message,
        attachments=attachments if attachments else None,
    )

    # Store agent message
    stored_agent_message = message_repo.create(
        conversation_id=conversation_id,
        role=MessageRole.AGENT,
        content=agent_response.message.content,
        thinking=agent_response.message.thinking,
        preview_ref=agent_response.message.preview_ref,
        approval_required=agent_response.message.approval_required,
        metadata=agent_response.message.metadata,
    )

    # Update conversation with detected documents
    for doc in agent_response.detected_documents:
        if doc.document_type == "form":
            conversation_repo.set_form_document(conversation_id, doc.document_id)
        else:
            conversation_repo.add_source_document(conversation_id, doc.document_id)

    # Return user message (agent message comes via SSE)
    return user_message


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="Get messages (paginated)",
    responses={
        200: {"description": "List of messages"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def get_messages(
    conversation_id: str,
    before: Annotated[str | None, Query(description="Get messages before this ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 50,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
) -> MessageListResponse:
    """Get messages in a conversation.

    Returns paginated list of messages sorted by created_at ascending.
    Use 'before' parameter to paginate backwards.
    """
    # Verify user ownership
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    messages, has_more = message_repo.list_by_conversation(
        conversation_id=conversation_id,
        before=before,
        limit=limit,
    )

    return MessageListResponse(items=messages, has_more=has_more)


@router.get(
    "/{conversation_id}/stream",
    summary="SSE stream for real-time updates",
    responses={
        200: {"description": "SSE stream", "content": {"text/event-stream": {}}},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def stream_updates(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> StreamingResponse:
    """Subscribe to real-time updates for a conversation.

    Returns a Server-Sent Events stream with the following event types:
    - connected: Connection established
    - thinking: Agent is processing
    - message: New message from agent
    - preview: Preview image ready
    - approval: Approval requested
    - stage_change: Agent stage changed
    - error: Error occurred
    - complete: Conversation complete
    """
    # Verify user ownership
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    async def event_generator():
        """Generate SSE events.

        TODO: Replace with actual event stream from Redis pub/sub.
        """
        import asyncio
        import json

        # Send connected event
        connected_data = json.dumps({"conversation_id": conversation_id})
        yield f"event: connected\ndata: {connected_data}\n\n"

        # Keep connection alive with heartbeat
        # Real implementation would listen to Redis pub/sub
        while True:
            await asyncio.sleep(30)
            yield ": heartbeat\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post(
    "/{conversation_id}/approve",
    response_model=Message,
    summary="Approve current preview",
    responses={
        200: {"description": "Approval processed"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def approve_preview(
    conversation_id: str,
    request: ApprovePreviewRequest,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
) -> Message:
    """Approve the current preview.

    Triggers final PDF generation and completes the conversation.
    """
    # Verify user ownership
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    # Find the message to approve
    approval_message = message_repo.get(request.message_id)
    if approval_message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message not found",
        )

    if not approval_message.approval_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This message does not require approval",
        )

    # Update approval status
    updated_message = message_repo.update_approval_status(
        request.message_id, ApprovalStatus.APPROVED
    )

    if updated_message is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update approval status",
        )

    # Log approval
    log.approval_received(
        conversation_id=conversation_id,
        message_id=request.message_id,
        approved=True,
    )

    # Update conversation status to completed
    conversation_repo.update_status(conversation_id, ConversationStatus.COMPLETED)

    # Log completion
    message_count = message_repo.count_by_conversation(conversation_id)
    log.conversation_completed(
        conversation_id=conversation_id,
        message_count=message_count,
    )

    return updated_message


@router.get(
    "/{conversation_id}/download",
    summary="Download filled PDF",
    responses={
        200: {"description": "PDF file", "content": {"application/pdf": {}}},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "No filled PDF available"},
    },
)
async def download_pdf(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> StreamingResponse:
    """Download the filled PDF.

    Only available after the conversation is completed and PDF is generated.
    """
    # Verify user ownership
    conversation = conversation_repo.get_by_user(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.CONVERSATION_NOT_FOUND,
                    message="Conversation not found",
                )
            ).model_dump(),
        )

    # Check if PDF is available
    if not conversation.filled_pdf_ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No filled PDF available",
        )

    # Log download
    log.pdf_downloaded(conversation_id=conversation_id, user_id=user_id)

    # TODO: Fetch from storage and stream
    # For now, return a placeholder error
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF download not yet implemented",
    )
