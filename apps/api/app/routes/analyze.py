from __future__ import annotations

from typing import Annotated
import logging
import time
import os
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel, ConfigDict, Field

from app.models.template_schema import DraftTemplate
from app.services.llm_analyze import analyze_template, StrategyType
from app.services.pdf_render import RenderedPage, render_pdf_pages

router = APIRouter()
logger = logging.getLogger(__name__)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    draft_template: DraftTemplate = Field(..., alias="schema_json")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: Annotated[UploadFile | None, File(description="Template PDF file")] = None,
    pdf_url: Annotated[str | None, Form(description="GCS or public PDF URL")] = None,
    strategy: Annotated[StrategyType, Query(description="Analysis strategy")] = "auto",
) -> AnalyzeResponse:
    started_at = time.monotonic()
    if (file is None and pdf_url is None) or (file is not None and pdf_url is not None):
        raise HTTPException(
            status_code=400, detail="Provide either a PDF file or pdf_url (one only)."
        )

    filename = None
    if file is not None:
        pdf_bytes = await file.read()
        filename = file.filename
        logger.info(
            "Analyze request received (file): name=%s size_bytes=%s",
            filename,
            len(pdf_bytes),
        )
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
    else:
        parsed = urlparse(pdf_url or "")
        filename = parsed.path.split("/")[-1] or parsed.netloc
        logger.info(
            "Analyze request received (url): host=%s path=%s",
            parsed.netloc,
            parsed.path,
        )
        pdf_bytes = _fetch_pdf_from_url(pdf_url)

    # Use the functional pipeline
    from app.services.analysis.pipeline import analyze_pdf

    template_dict = await analyze_pdf(pdf_bytes, strategy=strategy)
    draft_template = DraftTemplate.model_validate(template_dict)

    duration = time.monotonic() - started_at
    logger.info("Analyze completed in %.2fs", duration)

    if DEBUG:
        logger.info(f"DEBUG summary: strategy={strategy}, filename={filename}, pdf_size={len(pdf_bytes)}, duration={round(duration, 2)}s, fields_extracted={len(draft_template.fields)}")

    return AnalyzeResponse.model_validate({"schema_json": draft_template})


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
