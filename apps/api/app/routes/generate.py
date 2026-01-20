from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.template_schema import TemplateSchema, default_template_schema
from app.services.pdf_engine import generate_pdf

router = APIRouter()


class GenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    template_id: str | None = None
    schema_json_: TemplateSchema | None = Field(default=None, alias="schema_json")
    data: dict[str, str]

    @model_validator(mode="after")
    def _ensure_template_reference(self) -> "GenerateRequest":
        if self.template_id is None and self.schema_json_ is None:
            raise ValueError("schema_json or template_id must be provided")
        return self


@router.post("/generate")
def generate(request: GenerateRequest) -> Response:
    schema = request.schema_json_
    if schema is None:
        if request.template_id == "default":
            schema = default_template_schema()
        else:
            raise HTTPException(
                status_code=400,
                detail="template_id is not available yet; provide schema_json",
            )

    missing_required = [
        field.key for field in schema.fields if field.required and field.key not in request.data
    ]
    if missing_required:
        raise HTTPException(
            status_code=422,
            detail={"missing_required_fields": missing_required},
        )

    pdf_bytes = generate_pdf(schema=schema, data=request.data)
    return Response(content=pdf_bytes, media_type="application/pdf")
