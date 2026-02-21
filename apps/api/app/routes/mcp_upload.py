"""
MCP Upload Routes.

Handles file uploads from web UI for MCP sessions (Y Pattern).
Files are uploaded here, then MCP tools can access them.
"""

import json
import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _get_redis_client() -> Any:
    """Get Redis client."""
    try:
        import redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/2")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


UPLOAD_PREFIX = "mcp:upload:"
FORM_PREFIX = "mcp:form:"
STORAGE_TTL = 3600


class UploadStatusResponse(BaseModel):
    """Upload status response."""
    upload_id: str
    status: str
    form_id: str | None = None
    filename: str | None = None
    field_count: int | None = None


@router.get("/upload/{upload_id}")
async def get_upload_status(upload_id: str) -> UploadStatusResponse:
    """
    Get the status of a pending upload.

    Used by web UI to check if upload session is valid.
    """
    client = _get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Storage unavailable")

    data = client.get(f"{UPLOAD_PREFIX}{upload_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Upload not found or expired")

    upload_data = json.loads(data)
    return UploadStatusResponse(
        upload_id=upload_id,
        status=upload_data.get("status", "unknown"),
        form_id=upload_data.get("form_id"),
        filename=upload_data.get("filename"),
        field_count=upload_data.get("field_count"),
    )


@router.post("/upload/{upload_id}")
async def complete_upload(
    upload_id: str,
    file: UploadFile = File(...),
) -> UploadStatusResponse:
    """
    Complete a pending upload by uploading the actual file.

    This is called by the web UI when user uploads a file.
    The MCP session can then access the uploaded form.
    """
    import tempfile
    from pathlib import Path

    client = _get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Storage unavailable")

    # Get upload data
    data = client.get(f"{UPLOAD_PREFIX}{upload_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Upload not found or expired")

    upload_data = json.loads(data)

    if upload_data.get("status") == "completed":
        raise HTTPException(status_code=400, detail="Upload already completed")

    session_id = upload_data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid upload session")

    # Read file
    file_bytes = await file.read()
    filename = file.filename or "form.pdf"

    # Validate it's a PDF
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Store file and extract metadata
    try:
        import fitz  # PyMuPDF

        # Save to temp directory
        temp_dir = Path(tempfile.gettempdir()) / "daru-mcp" / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        form_id = str(uuid4())
        file_path = temp_dir / f"{form_id}.pdf"
        file_path.write_bytes(file_bytes)

        # Extract form metadata
        doc = fitz.open(str(file_path))
        try:
            page_count = len(doc)
            has_acroform = bool(doc.is_form_pdf)

            # Extract fields
            fields = {}
            field_types: dict[str, int] = {}

            for page_num, page in enumerate(doc, 1):
                for widget in page.widgets():
                    field_id = str(uuid4())
                    widget_type = widget.field_type
                    field_type = _get_field_type(widget_type)

                    fields[field_id] = {
                        "name": widget.field_name or f"field_{field_id[:8]}",
                        "type": field_type,
                        "page": page_num,
                        "bbox": list(widget.rect),
                        "value": widget.field_value,
                        "options": widget.choice_values if field_type in ("dropdown", "radio") else None,
                        "required": False,
                        "readonly": bool(widget.field_flags & 1),
                    }
                    field_types[field_type] = field_types.get(field_type, 0) + 1

            form_metadata = {
                "id": form_id,
                "session_id": session_id,
                "filename": filename,
                "path": str(file_path),
                "page_count": page_count,
                "has_acroform": has_acroform,
                "field_count": len(fields),
                "field_types": field_types,
                "fields": fields,
            }

            # Store form in Redis
            form_key = f"{FORM_PREFIX}{session_id}:{form_id}"
            client.setex(form_key, STORAGE_TTL, json.dumps(form_metadata))

            # Update upload status
            upload_data["status"] = "completed"
            upload_data["form_id"] = form_id
            upload_data["filename"] = filename
            upload_data["field_count"] = len(fields)
            client.setex(f"{UPLOAD_PREFIX}{upload_id}", STORAGE_TTL, json.dumps(upload_data))

            return UploadStatusResponse(
                upload_id=upload_id,
                status="completed",
                form_id=form_id,
                filename=filename,
                field_count=len(fields),
            )

        finally:
            doc.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")


def _get_field_type(widget_type: int) -> str:
    """Map PyMuPDF widget type to field type string."""
    type_map = {
        0: "text",
        1: "text",
        2: "checkbox",
        3: "dropdown",
        4: "dropdown",
        5: "text",
    }
    return type_map.get(widget_type, "text")
