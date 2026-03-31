"""All API routes in one file."""

import logging

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.models import (
    Annotation,
    Message,
    ContextWindow,
    CreateAnnotationRequest,
    CreateConversationRequest,
    FieldsResponse,
    FillRequest,
    FormSchema,
    MapResult,
    MapRun,
    RuleItem,
    UploadFormResponse,
)
from app.services import (
    AnnotationService,
    MessageService,
    FormSchemaService,
    FormService,
    FillService,
    MapService,
    ConversationService,
    UnderstandService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

doc_service = FormService()
annotation_service = AnnotationService()
conversation_service = ConversationService()
map_service = MapService()
fill_service = FillService()
understand_service = UnderstandService()
message_service = MessageService()
form_schema_service = FormSchemaService()


@router.post("/forms", response_model=UploadFormResponse)
async def upload_form(file: UploadFile = File(...)) -> UploadFormResponse:
    """Upload a PDF form and extract its fields."""
    file_bytes = await file.read()
    try:
        form = doc_service.upload_pdf(file_bytes, file.filename or "form.pdf")
    except Exception as e:
        logger.error("Failed to upload form: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    try:
        map_service.run_heuristic(form.form_id)
    except Exception as e:
        logger.warning("Heuristic map failed for %s: %s", form.form_id, e)

    return UploadFormResponse(form_id=form.form_id, form=form)


@router.get("/forms/{form_id}/pages/{page}")
async def get_page_preview(form_id: str, page: int) -> dict:
    """Render a PDF page and return it as a base64 data URL."""
    try:
        image_url = doc_service.get_page_preview_base64(form_id, page)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to render page %d for form %s: %s", page, form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"form_id": form_id, "page": page, "image_url": image_url}


@router.get("/forms/{form_id}/fields", response_model=FieldsResponse)
async def get_form_fields(form_id: str) -> FieldsResponse:
    """Extract form fields and text blocks from a PDF form."""
    try:
        fields, text_blocks = doc_service.get_fields_and_text_blocks(form_id)
        page_count = doc_service.get_page_count(form_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to extract fields for form %s: %s", form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FieldsResponse(form_id=form_id, fields=fields, text_blocks=text_blocks, page_count=page_count)


@router.post("/conversations", response_model=ContextWindow)
async def create_conversation(req: CreateConversationRequest) -> ContextWindow:
    """Create a new conversation for a form."""
    try:
        ctx = conversation_service.create(req.form_id, req.user_info, req.rules)
    except Exception as e:
        logger.error("Failed to create conversation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return ctx


@router.patch("/conversations/{conversation_id}/form", response_model=ContextWindow)
async def update_conversation_form(conversation_id: str, body: dict) -> ContextWindow:
    """Attach a form to an existing conversation."""
    form_id = body.get("form_id")
    if not form_id:
        raise HTTPException(status_code=422, detail="form_id is required")
    if conversation_service.get(conversation_id) is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    try:
        conversation_service.update_form(conversation_id, form_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return conversation_service.get(conversation_id)  # type: ignore[return-value]


@router.patch("/conversations/{conversation_id}/user-info", response_model=ContextWindow)
async def update_user_info(conversation_id: str, body: dict) -> ContextWindow:
    """Merge key/value pairs into conversation user_info.data."""
    ctx = conversation_service.get(conversation_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    try:
        conversation_service.update_user_info(conversation_id, body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    updated = conversation_service.get(conversation_id)
    return updated  # type: ignore[return-value]


@router.get("/conversations/{conversation_id}", response_model=ContextWindow)
async def get_conversation(conversation_id: str) -> ContextWindow:
    """Retrieve a conversation by ID."""
    ctx = conversation_service.get(conversation_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    return ctx


@router.post("/messages", response_model=Message, status_code=201)
async def add_message(body: dict) -> Message:
    """Append an activity entry to a conversation's message log."""
    conversation_id = body.get("conversation_id")
    role = body.get("role")
    content = body.get("content")
    if not conversation_id or not role or not content:
        raise HTTPException(status_code=422, detail="conversation_id, role, and content are required")
    try:
        return message_service.add(conversation_id, role, content)
    except Exception as e:
        logger.error("add_message error for conversation %s: %s", conversation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages/{conversation_id}", response_model=list[Message])
async def list_messages(conversation_id: str) -> list[Message]:
    """Return all message entries for a conversation, ordered by time."""
    try:
        return message_service.list_by_conversation(conversation_id)
    except Exception as e:
        logger.error("list_messages error for conversation %s: %s", conversation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/annotations", response_model=Annotation)
async def create_annotation(req: CreateAnnotationRequest) -> Annotation:
    """Create an annotation pair linking a label to a form field."""
    try:
        annotation = annotation_service.create(req)
    except Exception as e:
        logger.error("Failed to create annotation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return annotation


@router.get("/annotations/{form_id}", response_model=list[Annotation])
async def list_annotations(form_id: str) -> list[Annotation]:
    """List all annotations for a form."""
    try:
        return annotation_service.list_by_form(form_id)
    except Exception as e:
        logger.error("Failed to list annotations for form %s: %s", form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/annotations/{annotation_id}", status_code=204)
async def delete_annotation(annotation_id: str) -> None:
    """Delete an annotation by ID."""
    try:
        annotation_service.delete(annotation_id)
    except Exception as e:
        logger.error("Failed to delete annotation %s: %s", annotation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/map/{form_id}", response_model=MapResult)
async def run_map(form_id: str, conversation_id: Optional[str] = Query(None)) -> MapResult:
    """Run spatial + LLM field label identification for a form."""
    logger.info("Mode triggered: MAP form=%s", form_id)
    try:
        maps = map_service.run(form_id, conversation_id=conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Map error for form %s: %s", form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return MapResult(form_id=form_id, maps=maps)


@router.get("/map/{form_id}/runs", response_model=list[MapRun])
async def list_map_runs(form_id: str) -> list[MapRun]:
    """List all past map runs for a form, newest first."""
    try:
        return map_service.list_runs(form_id)
    except Exception as e:
        logger.error("Failed to list map runs for form %s: %s", form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/map/{form_id}", response_model=MapResult)
async def get_map(form_id: str, created_at: Optional[str] = Query(default=None)) -> MapResult:
    """Get field label maps for a form. Defaults to the latest run; pass created_at to load a specific run."""
    try:
        maps = map_service.list_by_form(form_id, created_at=created_at)
    except Exception as e:
        logger.error("Failed to get maps for form %s: %s", form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return MapResult(form_id=form_id, maps=maps)


@router.post("/fill")
async def fill(req: FillRequest) -> dict:
    """Fill form fields using LLM."""
    logger.info("Mode triggered: FILL conversation=%s", req.conversation_id)
    try:
        return fill_service.fill(req.conversation_id, req.ask_answers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Fill error for conversation %s: %s", req.conversation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/conversations/{conversation_id}/understand", response_model=ContextWindow)
async def understand(conversation_id: str) -> ContextWindow:
    """LLM analyzes the form and extracts filling rules into the conversation."""
    logger.info("Mode triggered: RULES conversation=%s", conversation_id)
    try:
        understand_service.understand(conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Understand error for conversation %s: %s", conversation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    ctx = conversation_service.get(conversation_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ctx


@router.patch("/conversations/{conversation_id}/rules", response_model=ContextWindow)
async def update_rules(conversation_id: str, body: dict) -> ContextWindow:
    """Replace conversation rules with a manually edited list of RuleItem objects."""
    if conversation_service.get(conversation_id) is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    raw_items = body.get("items", [])
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=422, detail="'items' must be a list")
    try:
        rule_items = [RuleItem(**i) for i in raw_items]
        conversation_service.update_rules(conversation_id, rule_items)
    except Exception as e:
        logger.error("update_rules error for conversation %s: %s", conversation_id, e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    return conversation_service.get(conversation_id)  # type: ignore[return-value]


@router.get("/forms/{form_id}/schema", response_model=FormSchema)
async def get_form_schema(form_id: str) -> FormSchema:
    """Return the consolidated form schema (field labels, semantic keys, etc.)."""
    try:
        schema = form_schema_service.get(form_id)
        if schema is None:
            schema = form_schema_service.ensure_schema(form_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to get form schema for %s: %s", form_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return schema


@router.post("/ask")
async def ask(req: FillRequest) -> dict:
    """Agent asks clarifying questions."""
    logger.info("Mode triggered: ASK conversation=%s", req.conversation_id)
    try:
        return fill_service.ask(req.conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Ask error for conversation %s: %s", req.conversation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
