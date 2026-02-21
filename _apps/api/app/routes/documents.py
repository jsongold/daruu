from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.db.supabase import get_supabase_client
from app.models.template_schema import TemplateSchema
from app.services.pdf_engine import generate_pdf
from app.services.storage import create_signed_download_url, upload_pdf

router = APIRouter()


class DocumentCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    template_id: str
    data: dict[str, str]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    template_id: str
    input_values_json: dict[str, str] | None = None
    output_pdf_path: str
    created_at: str | None = None
    download_url: str


@router.post("/documents", response_model=DocumentResponse)
def create_document(request: DocumentCreateRequest) -> DocumentResponse:
    client = get_supabase_client()
    template_result = (
        client.table("templates")
        .select("id, schema_json")
        .eq("id", request.template_id)
        .single()
        .execute()
    )
    template_data = _require_result(template_result, "Template not found.", status_code=404)
    schema = TemplateSchema.model_validate(template_data["schema_json"])

    missing_required = [
        field.key for field in schema.fields if field.required and field.key not in request.data
    ]
    if missing_required:
        raise HTTPException(
            status_code=422,
            detail={"missing_required_fields": missing_required},
        )

    pdf_bytes = generate_pdf(schema=schema, data=request.data)
    document_id = str(uuid4())
    output_path = f"documents/{document_id}/output.pdf"
    upload_pdf(path=output_path, pdf_bytes=pdf_bytes)

    insert_payload = {
        "id": document_id,
        "template_id": request.template_id,
        "input_values_json": request.data,
        "output_pdf_path": output_path,
    }
    insert_result = client.table("documents").insert(insert_payload).execute()
    document_data = _require_result(insert_result, "Failed to create document.")

    download_url = create_signed_download_url(path=output_path)
    document_data["download_url"] = download_url
    return DocumentResponse.model_validate(document_data)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str) -> DocumentResponse:
    client = get_supabase_client()
    result = (
        client.table("documents")
        .select("*")
        .eq("id", document_id)
        .single()
        .execute()
    )
    data = _require_result(result, "Document not found.", status_code=404)
    data["download_url"] = create_signed_download_url(path=data["output_pdf_path"])
    return DocumentResponse.model_validate(data)


def _require_result(result, message: str, *, status_code: int = 500) -> dict:
    data = getattr(result, "data", None)
    if data:
        if isinstance(data, list):
            return data[0]
        return data
    raise HTTPException(status_code=status_code, detail=message)
