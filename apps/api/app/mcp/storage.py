"""
MCP Storage Management.

Handles file storage for MCP sessions:
- PDF forms (temporary, per-session)
- Source documents (temporary, per-session)
- Filled PDFs (for export)
- Download URLs (signed, time-limited)

Storage:
- Redis: Used for metadata in dev/prod
- Files: Stored on disk (temp directory)
- In-memory: Fallback for tests
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_settings

# Redis client and fallback
_redis_client: Any = None
_use_memory_fallback: bool = False
_memory_forms: dict[str, dict[str, Any]] = {}
_memory_source_docs: dict[str, dict[str, Any]] = {}

FORM_PREFIX = "mcp:form:"
DOC_PREFIX = "mcp:doc:"
STORAGE_TTL = 3600  # 1 hour


def _get_redis_client() -> Any:
    """Get or create Redis client."""
    global _redis_client, _use_memory_fallback

    if _use_memory_fallback:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/2")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception:
        _use_memory_fallback = True
        return None


class MCPStorage:
    """
    Storage manager for MCP file operations.

    Files are stored temporarily per session and cleaned up
    when sessions expire. Export files are uploaded to
    cloud storage with signed URLs.
    """

    def __init__(self) -> None:
        """Initialize storage manager."""
        self._settings = get_settings()
        self._temp_dir = Path(tempfile.gettempdir()) / "daru-mcp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    async def store_form(
        self,
        session_id: str,
        form_id: str,
        pdf_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """
        Store an uploaded PDF form.

        Args:
            session_id: MCP session ID
            form_id: Unique form ID
            pdf_bytes: PDF file content
            filename: Original filename

        Returns:
            Form metadata dict
        """
        import fitz  # PyMuPDF

        # Create session directory
        session_dir = self._temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save PDF to disk
        file_path = session_dir / f"{form_id}.pdf"
        file_path.write_bytes(pdf_bytes)

        # Extract form metadata using PyMuPDF
        doc = fitz.open(str(file_path))

        try:
            page_count = len(doc)
            has_acroform = bool(doc.is_form_pdf)

            # Extract fields
            fields = {}
            field_types: dict[str, int] = {}

            for page_num, page in enumerate(doc, 1):
                # Get AcroForm widgets
                for widget in page.widgets():
                    field_id = str(uuid4())
                    field_type = self._get_field_type(widget.field_type)

                    fields[field_id] = {
                        "name": widget.field_name or f"field_{field_id[:8]}",
                        "type": field_type,
                        "page": page_num,
                        "bbox": list(widget.rect),
                        "value": widget.field_value,
                        "options": widget.choice_values if field_type in ("dropdown", "radio") else None,
                        "required": False,  # AcroForm doesn't always specify
                        "readonly": bool(widget.field_flags & 1),
                    }

                    field_types[field_type] = field_types.get(field_type, 0) + 1

            # If no AcroForm fields, try to detect text areas
            if not fields:
                fields = await self._detect_form_fields(doc)
                for field_info in fields.values():
                    ftype = field_info.get("type", "text")
                    field_types[ftype] = field_types.get(ftype, 0) + 1

            metadata = {
                "id": form_id,
                "session_id": session_id,
                "filename": filename,
                "path": str(file_path),
                "page_count": page_count,
                "has_acroform": has_acroform,
                "field_count": len(fields),
                "field_types": field_types,
                "fields": fields,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Store in Redis or memory
            key = f"{session_id}:{form_id}"
            client = _get_redis_client()
            if client:
                client.setex(f"{FORM_PREFIX}{key}", STORAGE_TTL, json.dumps(metadata))
            else:
                _memory_forms[key] = metadata

            return metadata

        finally:
            doc.close()

    def _get_field_type(self, widget_type: int) -> str:
        """Map PyMuPDF widget type to field type string."""
        type_map = {
            0: "text",      # PDF_WIDGET_TYPE_UNKNOWN
            1: "text",      # PDF_WIDGET_TYPE_TEXT
            2: "checkbox",  # PDF_WIDGET_TYPE_BUTTON
            3: "dropdown",  # PDF_WIDGET_TYPE_COMBOBOX
            4: "dropdown",  # PDF_WIDGET_TYPE_LISTBOX
            5: "text",      # PDF_WIDGET_TYPE_SIGNATURE
        }
        return type_map.get(widget_type, "text")

    async def _detect_form_fields(
        self,
        doc: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Detect form fields in a non-AcroForm PDF.

        Uses heuristics to find fillable areas:
        - Horizontal lines (underlines)
        - Rectangles/boxes
        - Labels followed by empty space
        """
        fields = {}

        # Simplified detection - in production this would use
        # more sophisticated ML-based detection
        for page_num, page in enumerate(doc, 1):
            # Look for horizontal lines that might be form fields
            drawings = page.get_drawings()

            for drawing in drawings:
                if drawing.get("type") == "l":  # Line
                    start = drawing.get("start", (0, 0))
                    end = drawing.get("end", (0, 0))

                    # Check if horizontal line
                    if abs(start[1] - end[1]) < 2:
                        length = abs(end[0] - start[0])
                        if 50 < length < 400:  # Reasonable field width
                            field_id = str(uuid4())
                            fields[field_id] = {
                                "name": f"field_{len(fields) + 1}",
                                "type": "text",
                                "page": page_num,
                                "bbox": [start[0], start[1] - 12, end[0], start[1] + 2],
                                "value": None,
                                "detected": True,
                            }

                elif drawing.get("type") == "re":  # Rectangle
                    rect = drawing.get("rect", [0, 0, 0, 0])
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]

                    # Checkbox-like dimensions
                    if 8 < width < 25 and 8 < height < 25:
                        field_id = str(uuid4())
                        fields[field_id] = {
                            "name": f"checkbox_{len(fields) + 1}",
                            "type": "checkbox",
                            "page": page_num,
                            "bbox": rect,
                            "value": False,
                            "detected": True,
                        }

        return fields

    async def get_form(
        self,
        session_id: str,
        form_id: str,
    ) -> dict[str, Any] | None:
        """Get form metadata by ID."""
        key = f"{session_id}:{form_id}"
        client = _get_redis_client()
        if client:
            data = client.get(f"{FORM_PREFIX}{key}")
            if data:
                return json.loads(data)
            return None
        return _memory_forms.get(key)

    async def update_form_fields(
        self,
        session_id: str,
        form_id: str,
        fields: dict[str, dict[str, Any]],
    ) -> None:
        """Update form field values."""
        key = f"{session_id}:{form_id}"
        form = await self.get_form(session_id, form_id)
        if form:
            form["fields"] = fields
            form["updated_at"] = datetime.now(timezone.utc).isoformat()
            client = _get_redis_client()
            if client:
                client.setex(f"{FORM_PREFIX}{key}", STORAGE_TTL, json.dumps(form))
            else:
                _memory_forms[key] = form

    async def store_source_doc(
        self,
        session_id: str,
        doc_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        """
        Store an uploaded source document.

        Args:
            session_id: MCP session ID
            doc_id: Unique document ID
            file_bytes: File content
            filename: Original filename
            mime_type: MIME type

        Returns:
            Document metadata dict
        """
        # Create session directory
        session_dir = self._temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Determine extension
        ext = Path(filename).suffix or self._mime_to_ext(mime_type)
        file_path = session_dir / f"{doc_id}{ext}"
        file_path.write_bytes(file_bytes)

        # Get page count for PDFs
        page_count = 1
        if mime_type == "application/pdf":
            import fitz
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            doc.close()

        metadata = {
            "id": doc_id,
            "session_id": session_id,
            "filename": filename,
            "path": str(file_path),
            "mime_type": mime_type,
            "page_count": page_count,
            "size": len(file_bytes),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        key = f"{session_id}:{doc_id}"
        client = _get_redis_client()
        if client:
            client.setex(f"{DOC_PREFIX}{key}", STORAGE_TTL, json.dumps(metadata))
        else:
            _memory_source_docs[key] = metadata

        return metadata

    def _mime_to_ext(self, mime_type: str) -> str:
        """Convert MIME type to file extension."""
        mime_map = {
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "text/plain": ".txt",
        }
        return mime_map.get(mime_type, "")

    async def get_source_doc(
        self,
        session_id: str,
        doc_id: str,
    ) -> dict[str, Any] | None:
        """Get source document metadata."""
        key = f"{session_id}:{doc_id}"
        client = _get_redis_client()
        if client:
            data = client.get(f"{DOC_PREFIX}{key}")
            if data:
                return json.loads(data)
            return None
        return _memory_source_docs.get(key)

    async def get_all_source_docs(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Get all source documents for a session."""
        prefix = f"{session_id}:"
        client = _get_redis_client()
        if client:
            # Scan for all docs with this session prefix
            docs = []
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=f"{DOC_PREFIX}{prefix}*", count=100)
                for key in keys:
                    data = client.get(key)
                    if data:
                        docs.append(json.loads(data))
                if cursor == 0:
                    break
            return docs
        return [
            doc for key, doc in _memory_source_docs.items()
            if key.startswith(prefix)
        ]

    async def get_user_profile(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        """
        Get user profile data for auto-fill.

        Returns common fields like name, address, email, etc.
        """
        # TODO: Implement with Supabase
        # Return mock data for development
        return None

    async def create_download_url(
        self,
        user_id: str,
        file_path: str,
        filename: str,
        expires_in: timedelta,
    ) -> str:
        """
        Create a signed download URL.

        Args:
            user_id: User ID (for logging/quota)
            file_path: Local path to file
            filename: Download filename
            expires_in: URL expiration time

        Returns:
            Signed URL for download
        """
        # TODO: Implement with Supabase Storage
        # For now, return a placeholder URL
        settings = get_settings()
        base_url = settings.app_url or "https://daru-pdf.io"

        # In production, this would upload to cloud storage
        # and return a signed URL
        download_id = str(uuid4())

        return f"{base_url}/api/downloads/{download_id}?filename={filename}"

    async def cleanup_session(self, session_id: str) -> None:
        """
        Clean up all files for a session.

        Called when session expires.
        """
        import shutil

        # Remove session directory
        session_dir = self._temp_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)

        # Remove from Redis or memory
        prefix = f"{session_id}:"
        client = _get_redis_client()
        if client:
            # Delete all form keys for this session
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=f"{FORM_PREFIX}{prefix}*", count=100)
                if keys:
                    client.delete(*keys)
                if cursor == 0:
                    break
            # Delete all doc keys for this session
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=f"{DOC_PREFIX}{prefix}*", count=100)
                if keys:
                    client.delete(*keys)
                if cursor == 0:
                    break
        else:
            global _memory_forms, _memory_source_docs
            _memory_forms = {
                k: v for k, v in _memory_forms.items()
                if not k.startswith(prefix)
            }
            _memory_source_docs = {
                k: v for k, v in _memory_source_docs.items()
                if not k.startswith(prefix)
            }
