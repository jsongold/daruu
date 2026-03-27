"""All API routes in one file."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models import (
    Annotation,
    ContextWindow,
    CreateAnnotationRequest,
    CreateSessionRequest,
    FieldsResponse,
    FillRequest,
    MapResult,
    RuleItem,
    UploadDocumentResponse,
)
from app.services import (
    AnnotationService,
    DocumentService,
    FillService,
    MapService,
    SessionService,
    UnderstandService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

doc_service = DocumentService()
annotation_service = AnnotationService()
session_service = SessionService()
map_service = MapService()
fill_service = FillService()
understand_service = UnderstandService()


@router.post("/documents", response_model=UploadDocumentResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadDocumentResponse:
    """Upload a PDF document and extract its form fields."""
    file_bytes = await file.read()
    try:
        form = doc_service.upload_pdf(file_bytes, file.filename or "document.pdf")
    except Exception as e:
        logger.error("Failed to upload document: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return UploadDocumentResponse(document_id=form.document_id, form=form)


@router.get("/documents/{document_id}/pages/{page}")
async def get_page_preview(document_id: str, page: int) -> dict:
    """Render a PDF page and return it as a base64 data URL."""
    try:
        image_url = doc_service.get_page_preview_base64(document_id, page)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to render page %d for document %s: %s", page, document_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"document_id": document_id, "page": page, "image_url": image_url}


@router.get("/documents/{document_id}/fields", response_model=FieldsResponse)
async def get_document_fields(document_id: str) -> FieldsResponse:
    """Extract form fields and text blocks from a PDF document."""
    try:
        fields, text_blocks = doc_service.get_fields_and_text_blocks(document_id)
        page_count = doc_service.get_page_count(document_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to extract fields for document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FieldsResponse(document_id=document_id, fields=fields, text_blocks=text_blocks, page_count=page_count)


@router.post("/sessions", response_model=ContextWindow)
async def create_session(req: CreateSessionRequest) -> ContextWindow:
    """Create a new fill session for a document."""
    try:
        ctx = session_service.create(req.document_id, req.user_info, req.rules)
    except Exception as e:
        logger.error("Failed to create session: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return ctx


@router.patch("/sessions/{session_id}/user-info", response_model=ContextWindow)
async def update_user_info(session_id: str, body: dict) -> ContextWindow:
    """Merge key/value pairs into session user_info.data."""
    ctx = session_service.get(session_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    try:
        session_service.update_user_info(session_id, body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    updated = session_service.get(session_id)
    return updated  # type: ignore[return-value]


@router.get("/sessions/{session_id}", response_model=ContextWindow)
async def get_session(session_id: str) -> ContextWindow:
    """Retrieve a session by ID."""
    ctx = session_service.get(session_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return ctx


@router.post("/annotations", response_model=Annotation)
async def create_annotation(req: CreateAnnotationRequest) -> Annotation:
    """Create an annotation pair linking a label to a form field."""
    try:
        annotation = annotation_service.create(req)
    except Exception as e:
        logger.error("Failed to create annotation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return annotation


@router.get("/annotations/{document_id}", response_model=list[Annotation])
async def list_annotations(document_id: str) -> list[Annotation]:
    """List all annotations for a document."""
    try:
        return annotation_service.list_by_document(document_id)
    except Exception as e:
        logger.error("Failed to list annotations for document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/annotations/{annotation_id}", status_code=204)
async def delete_annotation(annotation_id: str) -> None:
    """Delete an annotation by ID."""
    try:
        annotation_service.delete(annotation_id)
    except Exception as e:
        logger.error("Failed to delete annotation %s: %s", annotation_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/map/{document_id}", response_model=MapResult)
async def run_map(document_id: str) -> MapResult:
    """Run spatial + LLM field label identification for a document."""
    try:
        maps = map_service.run(document_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Map error for document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return MapResult(document_id=document_id, maps=maps)


@router.get("/map/{document_id}", response_model=MapResult)
async def get_map(document_id: str) -> MapResult:
    """Get the latest field label maps for a document."""
    try:
        maps = map_service.list_by_document(document_id)
    except Exception as e:
        logger.error("Failed to get maps for document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return MapResult(document_id=document_id, maps=maps)


@router.post("/fill")
async def fill(req: FillRequest) -> dict:
    """Fill form fields using LLM."""
    try:
        return fill_service.fill(req.session_id, req.user_message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Fill error for session %s: %s", req.session_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sessions/{session_id}/understand", response_model=ContextWindow)
async def understand(session_id: str) -> ContextWindow:
    """LLM analyzes the document and extracts filling rules into the session."""
    try:
        understand_service.understand(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Understand error for session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    ctx = session_service.get(session_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ctx


@router.patch("/sessions/{session_id}/rules", response_model=ContextWindow)
async def update_rules(session_id: str, body: dict) -> ContextWindow:
    """Replace session rules with a manually edited list of RuleItem objects."""
    if session_service.get(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    raw_items = body.get("items", [])
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=422, detail="'items' must be a list")
    try:
        rule_items = [RuleItem(**i) for i in raw_items]
        session_service.update_rules(session_id, rule_items)
    except Exception as e:
        logger.error("update_rules error for session %s: %s", session_id, e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    return session_service.get(session_id)  # type: ignore[return-value]


@router.post("/ask")
async def ask(req: FillRequest) -> dict:
    """Agent asks clarifying questions."""
    try:
        return fill_service.ask(req.session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Ask error for session %s: %s", req.session_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
