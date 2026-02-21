from __future__ import annotations

import base64
import hashlib
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.supabase import get_supabase_client
from app.models.template_schema import DraftTemplate, TemplateSchema
from app.services.storage import upload_pdf

router = APIRouter()


class TemplateCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1)
    schema_json_: DraftTemplate = Field(..., alias="schema_json")
    pdf_base64: str | None = None
    pdf_url: str | None = None

    @model_validator(mode="after")
    def _validate_pdf_source(self) -> "TemplateCreateRequest":
        if self.pdf_base64 and self.pdf_url:
            raise ValueError("Provide only one of pdf_base64 or pdf_url.")
        if not self.pdf_base64 and not self.pdf_url:
            raise ValueError("pdf_base64 or pdf_url is required.")
        return self


class TemplateFinalizeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_json_: TemplateSchema = Field(..., alias="schema_json")
    updated_by: str | None = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    status: str
    version: int
    schema_json_: TemplateSchema = Field(..., alias="schema_json")
    pdf_fingerprint: str | None = None
    pdf_path: str | None = None


class TemplateSchemaResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    schema_json_: TemplateSchema = Field(..., alias="schema_json")


@router.post("/templates", response_model=TemplateResponse)
def create_template(request: TemplateCreateRequest) -> TemplateResponse:
    pdf_bytes = _resolve_pdf_bytes(request)
    template_id = str(uuid4())
    pdf_path = f"templates/{template_id}/template.pdf"
    pdf_fingerprint = _sha256_fingerprint(pdf_bytes)

    upload_pdf(path=pdf_path, pdf_bytes=pdf_bytes)

    client = get_supabase_client()
    payload = {
        "id": template_id,
        "name": request.name,
        "status": "draft",
        "schema_json": request.schema_json_.model_dump(),
        "pdf_fingerprint": pdf_fingerprint,
        "pdf_path": pdf_path,
        "version": 1,
    }
    result = client.table("templates").insert(payload).execute()
    data = _require_result(result, "Failed to create template.")
    return TemplateResponse.model_validate(data)


@router.post("/templates/{template_id}/finalize", response_model=TemplateResponse)
def finalize_template(template_id: str, request: TemplateFinalizeRequest) -> TemplateResponse:
    client = get_supabase_client()
    current = (
        client.table("templates")
        .select("*")
        .eq("id", template_id)
        .single()
        .execute()
    )
    current_data = _require_result(current, "Template not found.", status_code=404)

    from_version = int(current_data.get("version", 1))
    to_version = from_version + 1
    revision_payload = {
        "template_id": template_id,
        "from_version": from_version,
        "to_version": to_version,
        "before_schema_json": current_data.get("schema_json"),
        "after_schema_json": request.schema_json_.model_dump(),
        "updated_by": request.updated_by,
    }
    revision_result = client.table("template_revisions").insert(revision_payload).execute()
    _require_result(revision_result, "Failed to save template revision.")

    update_payload = {
        "status": "final",
        "version": to_version,
        "schema_json": request.schema_json_.model_dump(),
    }
    update_result = (
        client.table("templates")
        .update(update_payload)
        .eq("id", template_id)
        .execute()
    )
    updated_data = _require_result(update_result, "Failed to finalize template.")
    return TemplateResponse.model_validate(updated_data)


@router.get("/templates/{template_id}", response_model=TemplateSchemaResponse)
def get_template(template_id: str) -> TemplateSchemaResponse:
    client = get_supabase_client()
    result = (
        client.table("templates")
        .select("id, schema_json")
        .eq("id", template_id)
        .single()
        .execute()
    )
    data = _require_result(result, "Template not found.", status_code=404)
    return TemplateSchemaResponse.model_validate(data)


def _resolve_pdf_bytes(request: TemplateCreateRequest) -> bytes:
    if request.pdf_base64:
        try:
            return base64.b64decode(request.pdf_base64)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid pdf_base64.") from exc

    return _fetch_pdf_from_url(request.pdf_url)


def _fetch_pdf_from_url(pdf_url: str | None) -> bytes:
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url is required.")
    timeout = httpx.Timeout(20.0)
    try:
        response = httpx.get(pdf_url, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail="Failed to fetch pdf_url.") from exc
    return response.content


def _sha256_fingerprint(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _require_result(result, message: str, *, status_code: int = 500) -> dict:
    data = getattr(result, "data", None)
    if data:
        if isinstance(data, list):
            return data[0]
        return data
    raise HTTPException(status_code=status_code, detail=message)
