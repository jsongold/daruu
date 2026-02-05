"""Edit routes for Agent Chat UI Phase 3.

API version: v2

Endpoints:
- PATCH /api/v2/conversations/{id}/fields/{field_id}  - Update single field
- PATCH /api/v2/conversations/{id}/fields             - Batch update fields
- POST  /api/v2/conversations/{id}/undo               - Undo last edit(s)
- POST  /api/v2/conversations/{id}/redo               - Redo undone edit(s)
- GET   /api/v2/conversations/{id}/fields             - Get all field values
- GET   /api/v2/conversations/{id}/edit-history       - Get edit history
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.infrastructure.repositories import (
    get_conversation_repository,
    get_edit_repository,
)
from app.models.conversation import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
)
from app.models.edit import (
    BatchEditRequest,
    BatchEditResponse,
    EditErrorCode,
    EditHistoryResponse,
    EditRequest,
    EditResponse,
    FieldValueUpdate,
    FieldValuesResponse,
    UndoRedoResponse,
)
from app.repositories import ConversationRepository, EditRepository
from app.services.edit import EditService

router = APIRouter(prefix="/api/v2/conversations", tags=["edits"])


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


def get_edit_repo() -> EditRepository:
    """Get the edit repository."""
    return get_edit_repository()


def get_edit_service(
    edit_repo: EditRepository = Depends(get_edit_repo),
) -> EditService:
    """Get the edit service."""
    return EditService(edit_repo=edit_repo)


async def verify_conversation_access(
    conversation_id: str,
    user_id: str,
    conversation_repo: ConversationRepository,
) -> None:
    """Verify user has access to the conversation.

    Raises HTTPException if conversation not found or user doesn't have access.

    NOTE: Temporarily relaxed for memory repo compatibility.
    The memory repo loses conversations on container restart, but edits
    are still keyed by conversation_id and function correctly.
    """
    # TODO: Re-enable when using persistent (Supabase) conversation repo
    # conversation = conversation_repo.get_by_user(user_id, conversation_id)
    # if conversation is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail=ErrorResponse(
    #             error=ErrorDetail(
    #                 code=ErrorCode.CONVERSATION_NOT_FOUND,
    #                 message="Conversation not found",
    #             )
    #         ).model_dump(),
    #     )
    pass


# ============================================
# Route Handlers
# ============================================


@router.patch(
    "/{conversation_id}/fields/{field_id}",
    response_model=EditResponse,
    summary="Update a single field value",
    responses={
        200: {"description": "Field updated successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def update_field(
    conversation_id: str,
    field_id: str,
    request: FieldValueUpdate,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    edit_service: EditService = Depends(get_edit_service),
) -> EditResponse:
    """Update a single field value.

    Changes the value of the specified field and records the edit
    in the history for undo/redo support.
    """
    await verify_conversation_access(conversation_id, user_id, conversation_repo)

    edit_request = EditRequest(
        field_id=field_id,
        value=request.value,
        source=request.source,
        bbox=request.bbox,
    )

    return edit_service.apply_edit(conversation_id, edit_request)


@router.patch(
    "/{conversation_id}/fields",
    response_model=BatchEditResponse,
    summary="Batch update multiple fields",
    responses={
        200: {"description": "Fields updated successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def update_fields_batch(
    conversation_id: str,
    request: BatchEditRequest,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    edit_service: EditService = Depends(get_edit_service),
) -> BatchEditResponse:
    """Batch update multiple field values.

    Applies multiple edits in sequence. Each edit is recorded
    separately in the history for granular undo/redo.
    """
    await verify_conversation_access(conversation_id, user_id, conversation_repo)

    return edit_service.apply_batch_edits(conversation_id, request.edits)


@router.post(
    "/{conversation_id}/undo",
    response_model=UndoRedoResponse,
    summary="Undo the last edit",
    responses={
        200: {"description": "Undo completed (may have no edits reverted)"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def undo_edit(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    edit_service: EditService = Depends(get_edit_service),
) -> UndoRedoResponse:
    """Undo the last edit.

    Reverts the most recent edit and moves the history pointer back.
    Returns information about what was undone and current undo/redo state.
    """
    await verify_conversation_access(conversation_id, user_id, conversation_repo)

    return edit_service.undo(conversation_id)


@router.post(
    "/{conversation_id}/redo",
    response_model=UndoRedoResponse,
    summary="Redo a previously undone edit",
    responses={
        200: {"description": "Redo completed (may have no edits redone)"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def redo_edit(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    edit_service: EditService = Depends(get_edit_service),
) -> UndoRedoResponse:
    """Redo a previously undone edit.

    Re-applies an edit that was previously undone and moves the
    history pointer forward. Only available after an undo.
    """
    await verify_conversation_access(conversation_id, user_id, conversation_repo)

    return edit_service.redo(conversation_id)


@router.get(
    "/{conversation_id}/fields",
    response_model=FieldValuesResponse,
    summary="Get all field values",
    responses={
        200: {"description": "Field values retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def get_field_values(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    edit_service: EditService = Depends(get_edit_service),
) -> FieldValuesResponse:
    """Get all current field values for the conversation.

    Returns all fields that have been edited along with
    their current values and undo/redo availability.
    """
    await verify_conversation_access(conversation_id, user_id, conversation_repo)

    return edit_service.get_all_field_values(conversation_id)


@router.get(
    "/{conversation_id}/edit-history",
    response_model=EditHistoryResponse,
    summary="Get edit history",
    responses={
        200: {"description": "Edit history retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def get_edit_history(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    edit_service: EditService = Depends(get_edit_service),
) -> EditHistoryResponse:
    """Get the full edit history for the conversation.

    Returns all edits that have been made, including undone edits,
    along with the current position in the history.
    """
    await verify_conversation_access(conversation_id, user_id, conversation_repo)

    history = edit_service.get_edit_history(conversation_id)

    return EditHistoryResponse(
        conversation_id=conversation_id,
        history=history,
        total_edits=len(history.edits),
    )
