"""
Document Analysis Pipeline

A functional pipeline for PDF form field extraction.
Each step is a pure function that can succeed or skip to the next step.

Pipeline Flow:
    PDF bytes
    → check_acroform         (if has fields: extract → done)
    → check_visual_structure (if no structure: reject → done)
    → classify_with_llm      (if not form: reject → done)
    → extract_fields_vision  (extract → done)
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


@dataclass
class PipelineResult:
    """Result from a pipeline step."""
    success: bool
    template: dict[str, Any] | None = None
    reason: str = ""
    should_continue: bool = True


# ============================================================================
# Pipeline Steps (Pure Functions)
# ============================================================================

def check_acroform(pdf_bytes: bytes) -> PipelineResult:
    """
    Step 1: Check if PDF has AcroForm fields.

    If yes: Extract field definitions directly (fastest, most accurate).
    If no: Continue to next step.
    """
    from pypdf import PdfReader
    from io import BytesIO

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        # We check both form fields and fields to be sure
        fields = reader.get_fields()

        if DEBUG:
            logger.debug(f"AcroForm Check: pdf_size={len(pdf_bytes)}, pages={len(reader.pages)}, has_acroform={fields is not None and len(fields) > 0}, field_count={len(fields) if fields else 0}, fields={list(fields.keys()) if fields else []}")

        if fields and len(fields) > 0:
            # Has AcroForm - extract directly
            template = _acroform_to_template(reader)
            if template and template['fields']:
                if DEBUG:
                    logger.debug(f"AcroForm extracted template: {json.dumps(template, default=str)}")

                logger.info(f"AcroForm extraction success: {len(template['fields'])} fields")
                return PipelineResult(
                    success=True,
                    template=template,
                    reason=f"AcroForm extraction: {len(template['fields'])} fields found",
                    should_continue=True  # Allow enrichment
                )
    except Exception as e:
        logger.error(f"Error in check_acroform: {e}", exc_info=True)
        if DEBUG:
            logger.debug(f"AcroForm error: {type(e).__name__}: {str(e)}")

    # No AcroForm or extraction failed - continue to next step
    logger.info("No AcroForm fields found - continuing to next step")
    return PipelineResult(
        success=False,
        reason="No AcroForm fields found or extraction failed",
        should_continue=True
    )


def check_visual_structure(pdf_bytes: bytes) -> PipelineResult:
    """
    Step 2: Check if PDF has visual structure (lines, boxes).

    If yes: Continue to LLM classification.
    If no: Reject (probably just text document).
    """
    from app.services.pdf_render import render_pdf_pages

    logger.info("Checking visual structure...")
    # Optimize: Only render first page for structure check (cache hit on subsequent full renders)
    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=False, page_indices=[0])

    if not pages:
        logger.warning("No pages found in PDF")
        if DEBUG:
            logger.debug("Visual structure error: No pages found")
        return PipelineResult(
            success=False,
            reason="No pages found",
            should_continue=False
        )

    # Check first page for visual structure
    first_page = pages[0]
    anchor_count = len(first_page.visual_anchors or [])

    if DEBUG:
        logger.debug(f"Visual structure analysis: pages={len(pages)}, page_0_size=({first_page.width}x{first_page.height}), anchors={anchor_count}, anchors_data={json.dumps(first_page.visual_anchors or [], default=str)}")

    MIN_ANCHORS = 15

    if anchor_count < MIN_ANCHORS:
        # No visual structure - probably text document
        logger.info(f"Insufficient visual structure: {anchor_count} anchors < {MIN_ANCHORS}")
        empty_template = {
            "version": "v1",
            "name": "non-form-document",
            "fields": [],
            "description": f"Document rejected: only {anchor_count} visual anchors (< {MIN_ANCHORS})"
        }
        return PipelineResult(
            success=False,
            template=empty_template,
            reason=f"Insufficient visual structure: {anchor_count} anchors < {MIN_ANCHORS}",
            should_continue=False  # Stop here
        )

    # Has visual structure - continue to classification
    logger.info(f"Visual structure confirmed: {anchor_count} anchors")
    return PipelineResult(
        success=True,
        reason=f"Visual structure detected: {anchor_count} anchors",
        should_continue=True
    )


async def classify_with_llm(pdf_bytes: bytes) -> PipelineResult:
    """
    Step 3: Use LLM to classify if this is a form.

    If yes: Continue to field extraction.
    If no: Reject.
    """
    from app.services.pdf_render import render_pdf_pages
    from app.services.analysis.strategies import DocumentClassifier

    logger.info("Running LLM classification...")
    # Optimize: Only render first page for classification (cache hit on subsequent full renders)
    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=False, page_indices=[0])

    if not pages:
        logger.warning("No pages to classify")
        if DEBUG:
            logger.debug("Classification error: No pages to classify")
        return PipelineResult(
            success=False,
            reason="No pages to classify",
            should_continue=False
        )

    classifier = DocumentClassifier()
    is_form = await classifier.classify(pages[0])

    if DEBUG:
        logger.debug(f"LLM Classification result: is_form={is_form}, page_index={pages[0].index}")

    if not is_form:
        # LLM says not a form
        logger.info("Document classified as non-form by LLM")
        empty_template = {
            "version": "v1",
            "name": "non-form-document",
            "fields": [],
            "description": "LLM classified as non-form document"
        }
        return PipelineResult(
            success=False,
            template=empty_template,
            reason="LLM classified as non-form",
            should_continue=False  # Stop here
        )

    # Is a form - continue to extraction
    logger.info("Document classified as form - proceeding to field extraction")
    return PipelineResult(
        success=True,
        reason="LLM classified as form",
        should_continue=True
    )


async def extract_fields_vision(pdf_bytes: bytes, strategy: str = "hybrid") -> PipelineResult:
    """
    Step 4: Extract fields using vision analysis.

    Always succeeds (returns best effort extraction).
    """
    from app.services.pdf_render import render_pdf_pages
    from app.services.analysis.strategies import HybridStrategy, VisionLowResStrategy

    logger.info(f"Extracting fields with strategy: {strategy}")
    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=True)

    if DEBUG:
        pages_info = [f"page_{p.index}({p.width}x{p.height},text_blocks={len(p.text_blocks) if p.text_blocks else 0},anchors={len(p.visual_anchors) if p.visual_anchors else 0})" for p in pages]
        logger.debug(f"Vision extraction start: strategy={strategy}, pages={pages_info}")

    # Choose strategy
    if strategy == "vision_low_res":
        analyzer = VisionLowResStrategy()
    else:
        analyzer = HybridStrategy()

    # Extract fields
    template = await analyzer.analyze(pages, {})

    # Convert to dict
    template_dict = template.model_dump()

    if DEBUG:
        logger.debug(f"Vision extraction complete: fields_count={len(template.fields)}, template={json.dumps(template_dict, default=str)}")

    logger.info(f"Vision extraction complete: {len(template.fields)} fields found")
    return PipelineResult(
        success=True,
        template=template_dict,
        reason=f"Vision extraction: {len(template.fields)} fields found",
        should_continue=False  # Done!
    )


# ============================================================================
# Pipeline Executor
# ============================================================================

async def analyze_pdf(pdf_bytes: bytes, strategy: str = "auto") -> dict[str, Any]:
    """
    Run the full analysis pipeline.

    Args:
        pdf_bytes: PDF file bytes
        strategy: "auto", "acroform_only", "vision_only", "vision_low_res"

    Returns:
        Template dict with extracted fields
    """
    import inspect
    import asyncio

    logger.info(f"Starting PDF analysis pipeline - strategy: {strategy}")

    if DEBUG:
        logger.debug(f"Pipeline start: strategy={strategy}, pdf_size={len(pdf_bytes)} bytes")

    steps: list[tuple[str, Callable[[bytes], PipelineResult | Any]]] = []

    # Build pipeline based on strategy
    if strategy == "acroform_only":
        steps = [
            ("AcroForm Extraction", check_acroform),
        ]
    elif strategy == "vision_only":
        steps = [
            ("Vision Field Extraction", lambda b: extract_fields_vision(b, "hybrid")),
        ]
    elif strategy == "vision_low_res":
        steps = [
            ("Vision Field Extraction (Low-Res)", lambda b: extract_fields_vision(b, "vision_low_res")),
        ]
    else:  # auto (full pipeline)
        steps = [
            ("AcroForm Extraction", check_acroform),
            ("Visual Structure Check", check_visual_structure),
            ("LLM Classification", classify_with_llm),
            ("Vision Field Extraction", lambda b: extract_fields_vision(b, "hybrid")),
        ]

    # Execute pipeline
    current_template: dict[str, Any] | None = None

    for step_name, step_fn in steps:
        logger.info(f"Pipeline: Executing step '{step_name}'")

        result_or_coro = step_fn(pdf_bytes)

        # If it's a coroutine, await it
        if inspect.iscoroutine(result_or_coro) or asyncio.isfuture(result_or_coro):
            result = await result_or_coro
        else:
            result = result_or_coro

        logger.info(f"Pipeline: Step '{step_name}' completed - success={result.success}, should_continue={result.should_continue}")

        if result.template is not None:
            current_template = result.template

            # Special case: If AcroForm extraction succeeded, we try to enrich it
            if step_name == "AcroForm Extraction":
                try:
                    logger.info("Attempting to enrich AcroForm fields...")
                    from app.services.analysis.strategies import AcroFormEnricher
                    from app.services.pdf_render import render_pdf_pages
                    from app.models.template_schema import DraftTemplate

                    enricher = AcroFormEnricher()
                    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=False)
                    template_obj = DraftTemplate.model_validate(current_template)

                    # Run enrichment (it's async)
                    enriched_template = await enricher.enrich(template_obj, pages)
                    current_template = enriched_template.model_dump()

                    if DEBUG:
                        logger.debug(f"Enrichment complete: {json.dumps(current_template, default=str)}")

                    logger.info("AcroForm enrichment successful")
                    # After successful enrichment, we are DONE for AcroForm
                    return current_template
                except Exception as e:
                    logger.error(f"Failed to enrich AcroForm: {e}", exc_info=True)
                    if DEBUG:
                        logger.debug(f"Enrichment error: {type(e).__name__}: {str(e)}")
                    # Return non-enriched version if enrichment fails
                    return current_template

            # For other steps (like Vision), we return immediately
            logger.info(f"Returning template from step '{step_name}'")
            if DEBUG:
                logger.debug(f"Final template: {json.dumps(current_template, default=str)}")
            return current_template

        if not result.should_continue:
            # Step said stop (but no template)
            # Return empty template
            logger.info(f"Pipeline stopped at step '{step_name}': {result.reason}")
            final_template = {
                "version": "v1",
                "name": "empty",
                "fields": [],
                "description": f"Pipeline stopped at: {step_name} - {result.reason}"
            }
            if DEBUG:
                logger.debug(f"Final template (stopped): {json.dumps(final_template, default=str)}")
            return final_template

    # Should never reach here, but fallback
    logger.warning("Pipeline completed without result")
    final_template = {
        "version": "v1",
        "name": "empty",
        "fields": [],
        "description": "Pipeline completed without result"
    }
    if DEBUG:
        logger.debug(f"Final template (no result): {json.dumps(final_template, default=str)}")
    return final_template


# ============================================================================
# Helper Functions
# ============================================================================

def _acroform_to_template(reader: Any) -> dict[str, Any]:
    """Convert AcroForm fields to template format by scanning annotations."""
    from app.models.template_schema import FieldDefinition, Placement, FontPolicy, DraftTemplate
    
    def get_field_name(obj):
        """Recursively find the field name."""
        if '/T' in obj:
            return obj['/T']
        if '/Parent' in obj:
            return get_field_name(obj['/Parent'].get_object())
        return None

    def get_font_policy(obj):
        """Extract font info from /DA (Default Appearance) string."""
        import re
        da = obj.get('/DA')
        if not da and '/Parent' in obj:
            parent = obj['/Parent'].get_object()
            da = parent.get('/DA')
        
        if da and isinstance(da, str):
            # Typical DA: "/Helv 10 Tf 0 g"
            # Extract font name and size
            font_match = re.search(r'/(\w+)\s+(\d+\.?\d*)\s+Tf', da)
            if font_match:
                font_name = font_match.group(1)
                font_size = float(font_match.group(2))
                return {
                    "size": font_size,
                    "family": font_name,
                    "min_size": 6
                }
        return {"size": 10, "min_size": 6}

    # Map for field_name -> (page_index, rect, font_policy)
    field_placements = {}
    
    # Scan all pages for widget annotations
    for i, page in enumerate(reader.pages):
        if '/Annots' in page:
            mb = page.mediabox
            page_height = float(mb.height)
            
            for annot_ref in page['/Annots']:
                try:
                    annot = annot_ref.get_object()
                    if annot.get('/Subtype') == '/Widget':
                        name = get_field_name(annot)
                        rect = annot.get('/Rect')
                        if name and rect:
                            # If we already have this field, we stick to the first one
                            if name not in field_placements:
                                # PDF coordinates: [x_left, y_bottom, x_right, y_top]
                                x1, y1, x2, y2 = [float(v) for v in rect]
                                
                                # Convert to Top-Left coordinate system
                                app_x = x1
                                app_y = page_height - y2
                                width = x2 - x1
                                height = y2 - y1
                                
                                font_info = get_font_policy(annot)
                                
                                # Capture extra data
                                ft = annot.get('/FT')
                                value = annot.get('/V', '')
                                field_type_name = {
                                    '/Tx': 'Text',
                                    '/Btn': 'Checkbox/Radio',
                                    '/Ch': 'Choice/Dropdown',
                                    '/Sig': 'Signature'
                                }.get(ft, 'Unknown')
                                
                                field_placements[name] = {
                                    "page_index": i,
                                    "x": app_x,
                                    "y": app_y,
                                    "width": width,
                                    "height": height,
                                    "font": font_info,
                                    "tech_notes": f"Type: {field_type_name}, Default: {value}" if value else f"Type: {field_type_name}"
                                }
                except Exception:
                    continue

    if not field_placements:
        return None

    template_fields = []
    for name, pos in field_placements.items():
        font_info = pos.get("font", {})
        field_def = FieldDefinition(
            id=name,
            key=name,
            label=name,
            type="string", # Default
            required=False,
            notes=pos.get("tech_notes"), # Initial technical notes
            placement=Placement(
                page_index=pos["page_index"],
                x=float(pos["x"]),
                y=float(pos["y"]),
                max_width=float(pos["width"]),
                height=float(pos["height"]),
                align="left",
                font_policy=FontPolicy(
                    size=float(font_info.get("size", 10)),
                    family=font_info.get("family"),
                    min_size=float(font_info.get("min_size", 6))
                )
            )
        )
        template_fields.append(field_def)
    
    template = DraftTemplate(
        version="v1",
        name="acroform-import",
        fields=template_fields
    )
    
    return template.model_dump()
