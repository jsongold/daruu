from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any
from datetime import datetime

import httpx
from pydantic import ValidationError

from app.models.template_schema import DraftTemplate
from app.services.analysis.strategy import AnalysisStrategy
from app.services.pdf_render import RenderedPage

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o"
DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_RETRIES = 2
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

def _write_debug_file(filename: str, data: Any) -> None:
    """Write debug data to /tmp directory."""
    if not DEBUG:
        return
    try:
        filepath = f"/tmp/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(f"DEBUG: Wrote {filename}")
    except Exception as e:
        logger.error(f"Failed to write debug file {filename}: {e}")


class BaseAnalysisStrategy:
    """Base class for shared LLM interaction logic."""

    def _get_api_config(self) -> tuple[str, str, str]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required to analyze templates")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        return api_key, base_url, model

    def _call_openai(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        prompt: str,
        pages: list[RenderedPage] | None,
        detail: str = "high",
    ) -> str:
        timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        timeout = httpx.Timeout(timeout_seconds)
        headers = {"Authorization": f"Bearer {api_key}"}
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if pages:
            for page in pages:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{page.png_base64[:100]}..." if DEBUG else f"data:image/png;base64,{page.png_base64}",
                            "detail": detail,
                        },
                    }
                )

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You return JSON only. Do not include markdown or extra text.",
                },
                {"role": "user", "content": content},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "max_tokens": 4096,
        }

        if DEBUG:
            _write_debug_file("llm_request_payload.json", {
                "model": model,
                "detail": detail,
                "images_count": len(pages) if pages else 0,
                "prompt_length": len(prompt),
                "prompt": prompt,
                "pages_info": [
                    {
                        "index": p.index,
                        "width": p.width,
                        "height": p.height
                    }
                    for p in (pages or [])
                ]
            })

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                started_at = time.monotonic()
                logger.info(
                    "LLM request start: attempt=%s model=%s detail=%s images=%s",
                    attempt,
                    model,
                    detail,
                    len(pages) if pages else 0,
                )
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{base_url}/chat/completions", json=payload, headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                duration = time.monotonic() - started_at
                logger.info(
                    "LLM request success: attempt=%s status=%s duration=%.2fs",
                    attempt,
                    response.status_code,
                    duration,
                )
                response_content = data["choices"][0]["message"]["content"]

                if DEBUG:
                    _write_debug_file(f"llm_response_{attempt}.json", {
                        "attempt": attempt,
                        "status": response.status_code,
                        "duration": duration,
                        "response_length": len(response_content),
                        "response": response_content
                    })

                return response_content
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                logger.warning("LLM request failed on attempt %s: %s", attempt, exc)
                if DEBUG:
                    _write_debug_file(f"llm_error_attempt_{attempt}.json", {
                        "attempt": attempt,
                        "error": str(exc),
                        "type": type(exc).__name__
                    })

        raise RuntimeError("LLM request failed after retries") from last_error

    def _validate_with_repair(
        self,
        *,
        response_text: str,
        schema_json: dict[str, Any],
        base_url: str,
        api_key: str,
        model: str,
    ) -> DraftTemplate:
        current_text = response_text
        last_error: str | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                payload = json.loads(current_text)
                return DraftTemplate.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                logger.warning(
                    "LLM output validation failed (attempt %s/%s): %s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    last_error,
                )
                if attempt >= MAX_RETRIES:
                    break
                
                # Repair prompt
                repair_prompt = (
                    "Fix the following JSON so it strictly matches the schema.\n"
                    "Return JSON ONLY (no markdown, no commentary).\n"
                    f"Schema JSON:\n{json.dumps(schema_json, ensure_ascii=True)}\n"
                    f"Validation error:\n{last_error}\n"
                    f"Invalid JSON:\n{current_text}\n"
                    "Repaired JSON:"
                )
                
                current_text = self._call_openai(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    prompt=repair_prompt,
                    pages=None,  # No images for repair
                )

        raise RuntimeError(f"LLM output failed schema validation: {last_error}")


class AcroFormEnricher(BaseAnalysisStrategy):
    """
    Enriches existing AcroForm fields with semantic labels using Vision LLM.
    Optimized for large forms with chunking support and concurrent processing.
    """

    async def enrich(self, template: DraftTemplate, pages: list[RenderedPage]) -> DraftTemplate:
        from app.services.analysis.prompts import build_enrichment_prompt

        api_key, base_url, model = self._get_api_config()

        # Set up concurrent processing with semaphore
        semaphore = asyncio.Semaphore(OPENAI_MAX_CONCURRENT_REQUESTS)
        chunk_tasks = []

        logger.info(f"AcroFormEnricher: Starting concurrent enrichment with max {OPENAI_MAX_CONCURRENT_REQUESTS} concurrent requests")

        # We enrich page by page, collecting tasks for concurrent processing
        for page in pages:
            # Filter fields on this page
            page_fields = [f for f in template.fields if f.placement.page_index == page.index]
            if not page_fields:
                continue

            # For large forms (>50 fields), process in chunks to avoid token limits
            CHUNK_SIZE = 50
            if len(page_fields) > CHUNK_SIZE:
                logger.info(f"Page {page.index} has {len(page_fields)} fields, processing in chunks of {CHUNK_SIZE}")

                for chunk_idx in range(0, len(page_fields), CHUNK_SIZE):
                    chunk = page_fields[chunk_idx:chunk_idx + CHUNK_SIZE]
                    chunk_tasks.append(
                        self._enrich_chunk(chunk, page, api_key, base_url, model, semaphore)
                    )
            else:
                # Process all fields at once for smaller forms
                chunk_tasks.append(
                    self._enrich_chunk(page_fields, page, api_key, base_url, model, semaphore)
                )

        # Execute all chunk enrichment tasks concurrently
        if chunk_tasks:
            await asyncio.gather(*chunk_tasks, return_exceptions=True)

        return template

    async def _enrich_chunk(
        self,
        fields: list,
        page: RenderedPage,
        api_key: str,
        base_url: str,
        model: str,
        semaphore: asyncio.Semaphore,
    ):
        """Enrich a chunk of fields concurrently."""
        from app.services.analysis.prompts import build_enrichment_prompt

        async with semaphore:
            try:
                # Prepare simplified data for LLM
                known_fields = []
                for f in fields:
                    known_fields.append({
                        "id": f.id,
                        "x": round(f.placement.x, 1),
                        "y": round(f.placement.y, 1),
                        "width": round(f.placement.max_width, 1),
                        "height": round(f.placement.height or 20, 1)
                    })

                if DEBUG:
                    # Write input data to debug file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_file = f"/tmp/acroform_enrichment_input_page{page.index}_{timestamp}.json"
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "page_index": page.index,
                            "page_size": {"width": page.width, "height": page.height},
                            "field_count": len(fields),
                            "fields": known_fields
                        }, f, ensure_ascii=False, indent=2)
                    logger.info(f"DEBUG: Wrote input data to {debug_file}")

                prompt = build_enrichment_prompt(
                    page.index, page.width, page.height, json.dumps(known_fields, ensure_ascii=False)
                )

                response_text = await self._call_openai(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    pages=[page],
                    detail="high"
                )

                logger.info(f"Enrichment Response (Page {page.index}, {len(fields)} fields): {len(response_text)} chars")

                if DEBUG:
                    # Write raw LLM response to debug file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_file = f"/tmp/acroform_enrichment_response_page{page.index}_{timestamp}.json"
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    logger.info(f"DEBUG: Wrote LLM response to {debug_file}")

                # Parse enrichment result with error recovery
                try:
                    enriched_items = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse error: {e}. Attempting repair...")
                    # Try to repair by completing the JSON array
                    response_text = response_text.strip()
                    if not response_text.endswith(']'):
                        # Find last complete object
                        last_brace = response_text.rfind('}')
                        if last_brace > 0:
                            response_text = response_text[:last_brace+1] + ']'
                            enriched_items = json.loads(response_text)
                            logger.info(f"Repaired JSON, recovered {len(enriched_items)} items")
                        else:
                            raise
                    else:
                        raise

                if isinstance(enriched_items, dict):
                    # Handle case where LLM wraps it in {"fields": [...]}
                    enriched_items = enriched_items.get("fields", []) or enriched_items.get("items", [])

                # Create a map for quick lookup
                enrichment_map = {item["id"]: item for item in enriched_items if "id" in item}

                # Apply enrichment
                for f in fields:
                    if f.id in enrichment_map:
                        item = enrichment_map[f.id]
                        if item.get("label"):
                            f.label = item["label"]
                        if item.get("section"):
                            f.section = item["section"]
                        if item.get("notes"):
                            f.notes = item["notes"]

                if DEBUG:
                    # Write final enriched fields to debug file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_file = f"/tmp/acroform_enrichment_final_page{page.index}_{timestamp}.json"
                    enriched_fields = []
                    for f in fields:
                        enriched_fields.append({
                            "id": f.id,
                            "label": f.label,
                            "section": f.section,
                            "notes": f.notes,
                            "placement": {
                                "x": f.placement.x,
                                "y": f.placement.y,
                                "width": f.placement.max_width,
                                "height": f.placement.height
                            }
                        })
                    with open(debug_file, 'w', encoding='utf-8') as file:
                        json.dump(enriched_fields, file, ensure_ascii=False, indent=2)
                    logger.info(f"DEBUG: Wrote final enriched data to {debug_file}")

            except Exception as e:
                logger.error(f"Failed to enrich chunk on page {page.index}: {e}")
                # Continue best effort



class DocumentClassifier(BaseAnalysisStrategy):
    """
    Classifies if a document page is a form/application or just text.
    Uses a pipeline approach: Visual Heuristics -> LLM Verification.
    """
    
    def classify(self, page: RenderedPage) -> bool:
        """
        Determines if the document is a 'Form/Application'.
        
        Pipeline:
        1. Check visual anchor density.
           - If low (< threshold): Not a form (return False).
           - If high: Proceed to LLM check.
        2. LLM check: Ask if it looks like a form to be filled out.
        """
        # Threshold for visual anchors (lines/rects).
        MIN_FORM_ANCHORS = 15  # Specific threshold to trigger LLM check
        
        anchor_count = len(page.visual_anchors or [])
        has_visual_structure = anchor_count >= MIN_FORM_ANCHORS
        
        if not has_visual_structure:
            logger.info(
                "Classification Pipeline: REJECTED by Visual Heuristic (Anchors: %d < %d)", 
                anchor_count, MIN_FORM_ANCHORS
            )
            return False
            
        logger.info(
            "Classification Pipeline: PASSED Visual Heuristic (Anchors: %d >= %d). proceeding to LLM...", 
            anchor_count, MIN_FORM_ANCHORS
        )
        
        # Step 2: LLM Verification
        return self._llm_classify(page)

    def _llm_classify(self, page: RenderedPage) -> bool:
        api_key, base_url, model = self._get_api_config()

        prompt = (
            "Analyze this image of a document page.\n"
            "Determine if this is a 'Form' or 'Application' intended for user input "
            "(e.g. tax form, medical history, bank application, survey).\n"
            "Return JSON only:\n"
            "{\"is_form\": boolean, \"reason\": \"string\"}"
        )

        try:
            response_text = self._call_openai(
                base_url=base_url,
                api_key=api_key,
                model=model,
                prompt=prompt,
                pages=[page],
                detail="low"  # Low detail is enough for classification
            )
            data = json.loads(response_text)
            is_form = bool(data.get("is_form", False))
            reason = data.get("reason", "No reason provided")

            logger.info("Classification Pipeline: LLM Result=%s Reason='%s'", is_form, reason)

            if DEBUG:
                _write_debug_file("llm_classification_result.json", {
                    "page_index": page.index,
                    "is_form": is_form,
                    "reason": reason,
                    "llm_response": data
                })

            return is_form

        except Exception as e:
            logger.warning("Classification Pipeline: LLM check failed: %s. Defaulting to True based on visual anchors.", e)
            if DEBUG:
                _write_debug_file("llm_classification_error.json", {
                    "page_index": page.index,
                    "error": str(e),
                    "type": type(e).__name__
                })
            return True  # Fallback to True if visual anchors were present but LLM failed


class HybridStrategy(BaseAnalysisStrategy, AnalysisStrategy):
    """
    Standard strategy: High-res images + text blocks (if available).
    Analyzes all pages in one context window.
    """

    def __init__(self) -> None:
        self.classifier = DocumentClassifier()

    def _classify_document(self, page: RenderedPage) -> bool:
        return self.classifier.classify(page)

    async def analyze(
        self, pages: list[RenderedPage], schema_json: dict[str, Any]
    ) -> DraftTemplate:
        from app.models.template_schema import FieldDefinition

        if DEBUG:
            _write_debug_file("hybrid_strategy_start.json", {
                "strategy": "HybridStrategy",
                "num_pages": len(pages),
                "pages_info": [
                    {
                        "index": p.index,
                        "width": p.width,
                        "height": p.height,
                        "text_blocks_count": len(p.text_blocks) if p.text_blocks else 0,
                        "visual_anchors_count": len(p.visual_anchors) if p.visual_anchors else 0
                    }
                    for p in pages
                ]
            })

        logger.info(f"HybridStrategy: Starting analysis of {len(pages)} pages")

        if not pages:
            return DraftTemplate(version="v1", name="empty", fields=[])

        # Step 0: Classify if it's a form (Check first page)
        if not self._classify_document(pages[0]):
            logger.info("Document classified as textual/non-form. Skipping extraction.")
            if DEBUG:
                _write_debug_file("hybrid_strategy_rejected.json", {
                    "reason": "Document classified as non-form"
                })
            return DraftTemplate(
                version="v1",
                name="non-form-document",
                fields=[],
                description="Document detected as non-form content."
            )

        api_key, base_url, model = self._get_api_config()
        all_fields: list[FieldDefinition] = []

        for page in pages:
            logger.info(f"HybridStrategy: Processing page {page.index}")

            # Build prompt including text block metadata for THIS page only
            page_summary = {
                "page_index": page.index,
                "width": page.width,
                "height": page.height,
                "text_blocks": page.text_blocks or [],
                "visual_anchors": page.visual_anchors or [],  # Include extracted anchors
            }

            prompt = (
                "You are a form field extraction engine.\n"
                "Extract all writable input fields from the given form image.\n\n"
                "Rules:\n"
                "- Output JSON array only.\n"
                "- Use exact printed labels (original language).\n"
                "- Do not invent any fields.\n"
                "- Coordinates must match real boxes or lines.\n"
                "- Each checkbox, date box, and digit box is one field.\n"
                "- Expand tables row by row.\n"
                "- Do not wrap the output in any object.\n"
                "- Do not include explanations.\n\n"
                "Process:\n"
                "1. First pass: scan the entire image and detect all input areas.\n"
                "2. Second pass: enumerate every detected field and assign exact pixel coordinates.\n\n"
                "Output Format:\n"
                '[{"label": "string", "x": number, "y": number, "width": number, "height": number, "type": "string"}]\n'
                f"Page metadata (points):\n{json.dumps([page_summary], ensure_ascii=True)}\n"
            )

            try:
                response_text = self._call_openai(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    pages=[page],
                    detail="high",
                )
                logger.info("LLM Response (Page %s): %d chars", page.index, len(response_text))

                if DEBUG:
                    _write_debug_file(f"hybrid_page_{page.index}_extraction.json", {
                        "page_index": page.index,
                        "page_size": {"width": page.width, "height": page.height},
                        "llm_response": response_text
                    })

                # Parse simplified JSON
                items = json.loads(response_text)
                if isinstance(items, dict):
                    items = items.get("fields", []) or items.get("items", [])

                if DEBUG:
                    _write_debug_file(f"hybrid_page_{page.index}_parsed_items.json", {
                        "page_index": page.index,
                        "items_count": len(items),
                        "items": items
                    })

                for item in items:
                    from app.models.template_schema import Placement, FontPolicy

                    # Map flat item to FieldDefinition
                    label = item.get("label", "Field")
                    field_id = f"field_{len(all_fields) + 1}"

                    field_def = FieldDefinition(
                        id=field_id,
                        key=field_id,
                        label=label,
                        type="string",  # Default to string
                        required=False,
                        placement=Placement(
                            page_index=page.index,
                            x=float(item.get("x", 0)),
                            y=float(item.get("y", 0)),
                            max_width=float(item.get("width", 100)),
                            align="left",
                            font_policy=FontPolicy(size=12, min_size=8)
                        )
                    )
                    all_fields.append(field_def)

                logger.info(f"HybridStrategy: Extracted {len(items)} fields from page {page.index}")

            except Exception as e:
                logger.error("Failed to analyze page %s: %s", page.index, e, exc_info=True)
                if DEBUG:
                    _write_debug_file(f"hybrid_page_{page.index}_error.json", {
                        "page_index": page.index,
                        "error": str(e),
                        "type": type(e).__name__
                    })
                # Continue best effort

        logger.info(f"HybridStrategy: Extracted {len(all_fields)} fields total before snapping")

        # Post-process: Snap fields to visual anchors if available
        self._snap_fields_to_anchors(all_fields, pages)

        if DEBUG:
            _write_debug_file("hybrid_strategy_final_fields.json", {
                "total_fields": len(all_fields),
                "fields": [
                    {
                        "id": f.id,
                        "label": f.label,
                        "placement": {
                            "page_index": f.placement.page_index,
                            "x": f.placement.x,
                            "y": f.placement.y,
                            "max_width": f.placement.max_width,
                            "height": f.placement.height
                        }
                    }
                    for f in all_fields
                ]
            })

        # Merge fields into a final template
        template = DraftTemplate(
            version="v1",
            name="imported-hybrid-template",
            fields=all_fields
        )

        logger.info(f"HybridStrategy: Analysis complete - {len(all_fields)} fields")
        return template

    def _snap_fields_to_anchors(
        self, fields: list[FieldDefinition], pages: list[RenderedPage]
    ) -> None:
        """
        Adjust field coordinates to match the nearest visual anchor (line/rect).
        This overrides LLM hallucinations with precise vector coordinates.
        """
        SNAP_THRESHOLD = 20.0  # pixels
        snap_results = []

        for page in pages:
            if not page.visual_anchors:
                logger.info("Page %s: No visual anchors found for snapping.", page.index)
                continue

            logger.info("Page %s: Found %d visual anchors. Attempting snap...", page.index, len(page.visual_anchors))

            page_fields = [f for f in fields if f.placement.page_index == page.index]

            for field in page_fields:
                fx, fy = field.placement.x, field.placement.y
                best_anchor = None
                best_dist = float("inf")

                for anchor in page.visual_anchors:
                    ax0, ay0 = anchor["x0"], anchor["y0"]
                    # Calculate distance from field top-left to anchor top-left
                    # Weighted y-distance more because lines matter vertically
                    dist = ((fx - ax0) ** 2) + ((fy - ay0) ** 2 * 4)

                    if dist < best_dist:
                        best_dist = dist
                        best_anchor = anchor

                # If close enough, SNAP!
                if best_anchor and best_dist < (SNAP_THRESHOLD ** 2):
                    old_x, old_y = field.placement.x, field.placement.y

                    # Update coordinates
                    field.placement.x = best_anchor["x0"]
                    field.placement.y = best_anchor["y0"]

                    # Also update width if it seems related
                    anchor_width = best_anchor["x1"] - best_anchor["x0"]
                    if anchor_width > 10:
                        field.placement.max_width = anchor_width

                    snap_distance = best_dist ** 0.5
                    logger.info(
                        "Snapped field '%s': (%.1f, %.1f) -> (%.1f, %.1f) [dist=%.1f]",
                        field.label, old_x, old_y, field.placement.x, field.placement.y, snap_distance
                    )

                    snap_results.append({
                        "field_id": field.id,
                        "field_label": field.label,
                        "old_position": {"x": old_x, "y": old_y},
                        "new_position": {"x": field.placement.x, "y": field.placement.y},
                        "snap_distance": snap_distance
                    })

        if DEBUG and snap_results:
            _write_debug_file("hybrid_strategy_snap_results.json", {
                "total_snapped": len(snap_results),
                "snaps": snap_results
            })


class VisionLowResStrategy(BaseAnalysisStrategy, AnalysisStrategy):
    """
    Vision-only strategy: Low-res images, processes pages concurrently.
    Uses a specialized prompt for form field detection.
    """

    async def _process_single_page_lowres(
        self,
        page: RenderedPage,
        api_key: str,
        base_url: str,
        model: str,
        semaphore: asyncio.Semaphore,
    ) -> tuple[int, list[Any] | None, Exception | None]:
        """
        Process a single page concurrently (low-res variant).

        Returns:
            (page_index, extracted_items, error) - If error is not None, items should be ignored
        """
        from app.services.analysis.prompts import build_vision_prompt

        async with semaphore:
            try:
                logger.info(f"VisionLowResStrategy: Processing page {page.index}")

                prompt = build_vision_prompt(page.index, page.width, page.height)

                response_text = await self._call_openai(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    pages=[page],
                    detail="low",
                )
                logger.info("LLM Response (Page %s): %d chars", page.index, len(response_text))

                if DEBUG:
                    _write_debug_file(f"vision_lowres_page_{page.index}_response.json", {
                        "page_index": page.index,
                        "page_size": {"width": page.width, "height": page.height},
                        "response_length": len(response_text),
                        "response": response_text
                    })

                # Expecting a JSON array of dicts
                extracted_data = json.loads(response_text)
                if isinstance(extracted_data, dict) and "fields" in extracted_data:
                    # Handle case where LLM wraps it in {"fields": [...]}
                    extracted_data = extracted_data["fields"]

                if not isinstance(extracted_data, list):
                    logger.warning("LLM returned non-list for page %s: %s", page.index, type(extracted_data))
                    if DEBUG:
                        _write_debug_file(f"vision_lowres_page_{page.index}_error.json", {
                            "page_index": page.index,
                            "error": f"Expected list, got {type(extracted_data).__name__}",
                            "data_type": type(extracted_data).__name__
                        })
                    return (page.index, None, ValueError(f"Expected list, got {type(extracted_data).__name__}"))

                if DEBUG:
                    _write_debug_file(f"vision_lowres_page_{page.index}_parsed.json", {
                        "page_index": page.index,
                        "items_count": len(extracted_data),
                        "items": extracted_data
                    })

                logger.info(f"VisionLowResStrategy: Extracted {len(extracted_data)} fields from page {page.index}")
                return (page.index, extracted_data, None)

            except Exception as e:
                logger.error("Failed to parse/validate page %s: %s", page.index, e, exc_info=True)
                if DEBUG:
                    _write_debug_file(f"vision_lowres_page_{page.index}_parse_error.json", {
                        "page_index": page.index,
                        "error": str(e),
                        "type": type(e).__name__
                    })
                return (page.index, None, e)

    async def analyze(
        self, pages: list[RenderedPage], schema_json: dict[str, Any]
    ) -> DraftTemplate:
        from app.models.template_schema import FieldDefinition, Placement, FontPolicy

        logger.info(f"VisionLowResStrategy: Starting analysis of {len(pages)} pages")

        if DEBUG:
            _write_debug_file("vision_lowres_strategy_start.json", {
                "strategy": "VisionLowResStrategy",
                "num_pages": len(pages),
                "pages_info": [
                    {
                        "index": p.index,
                        "width": p.width,
                        "height": p.height
                    }
                    for p in pages
                ]
            })

        api_key, base_url, model = self._get_api_config()

        all_fields: list[FieldDefinition] = []

        # Set up concurrent processing with semaphore
        semaphore = asyncio.Semaphore(OPENAI_MAX_CONCURRENT_REQUESTS)

        logger.info(f"VisionLowResStrategy: Starting concurrent processing of {len(pages)} pages with max {OPENAI_MAX_CONCURRENT_REQUESTS} concurrent requests")

        # Create tasks for concurrent processing
        tasks = [
            self._process_single_page_lowres(page, api_key, base_url, model, semaphore)
            for page in pages
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results in order (preserving page order)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                continue

            page_index, extracted_data, error = result
            if error or extracted_data is None:
                logger.warning(f"Page {page_index} had no items extracted")
                continue

            for item in extracted_data:
                # Map LLM output to FieldDefinition
                # LLM output: id, label, page_index, x, y, w, h, kind, section

                kind_map = {
                    "text": "string",
                    "number": "string",
                    "date": "string",
                    "checkbox": "string",  # Schema only supports string currently
                    "radio": "string",
                    "signature": "string",
                    "stamp": "string"
                }

                field_type = kind_map.get(item.get("kind"), "string")

                # Convert to FieldDefinition
                field_def = FieldDefinition(
                    id=item.get("id"),
                    key=item.get("id"),
                    label=item.get("label"),
                    type=field_type,
                    required=False,  # Default to optional as prompt doesn't strictly detect requiredness yet
                    placement=Placement(
                        page_index=item.get("page_index", page_index),
                        x=float(item.get("x", 0)),
                        y=float(item.get("y", 0)),
                        max_width=float(item.get("w", 100)),
                        align="left",
                        font_policy=FontPolicy(size=10, min_size=6),
                    )
                )
                all_fields.append(field_def)

        if DEBUG:
            _write_debug_file("vision_lowres_strategy_final.json", {
                "total_fields": len(all_fields),
                "fields": [
                    {
                        "id": f.id,
                        "label": f.label,
                        "placement": {
                            "page_index": f.placement.page_index,
                            "x": f.placement.x,
                            "y": f.placement.y,
                            "max_width": f.placement.max_width
                        }
                    }
                    for f in all_fields
                ]
            })

        logger.info(f"VisionLowResStrategy: Analysis complete - {len(all_fields)} fields")
        return DraftTemplate(
            version="v1",
            name="imported-vision-template",
            fields=all_fields
        )
