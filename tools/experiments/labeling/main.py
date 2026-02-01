#!/usr/bin/env python3
"""Label linking test and tuning script.

This script allows testing and comparing different prompts for the
FieldLabellingAgent that links text labels to input boxes in PDF forms.

Usage (from repo root):
    python tools/experiments/labeling/main.py --pdf /path/to/test.pdf
    python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --prompt v2
    python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --compare default v2
    python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --output results.json
    python tools/experiments/labeling/main.py --pdf /path/to/test.pdf --dry-run --verbose
    python tools/experiments/labeling/main.py --list-prompts

The script will:
1. Load a PDF and extract AcroForm fields (boxes) and text blocks (labels)
2. Format the data for the LLM with spatial context
3. Call the LLM (or show what would be sent with --dry-run)
4. Display linkage results with confidence scores and rationales
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Set up paths for imports
_SCRIPT_DIR = Path(__file__).resolve().parent
_LABELING_DIR = _SCRIPT_DIR
_EXPERIMENTS_DIR = _SCRIPT_DIR.parent
_TOOLS_DIR = _EXPERIMENTS_DIR.parent
_REPO_ROOT = _TOOLS_DIR.parent
_API_DIR = _REPO_ROOT / "apps" / "api"

# Add apps/api to path for app module imports
if _API_DIR.exists() and str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

# Add tools dir to path for experiments module imports
if _TOOLS_DIR.exists() and str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


@dataclass
class LinkageResult:
    """Result of a single label-to-box linkage."""

    label_id: str
    box_id: str
    field_name: str
    field_type: str
    confidence: float
    rationale: str
    label_text: str = ""
    label_bbox: list[float] = field(default_factory=list)
    box_bbox: list[float] = field(default_factory=list)


@dataclass
class PageResult:
    """Results for a single page."""

    page: int
    linkages: list[LinkageResult]
    unlinked_boxes: list[str]
    label_count: int
    box_count: int
    processing_time_ms: float = 0.0
    llm_tokens_used: int = 0


@dataclass
class TestResult:
    """Complete test results."""

    pdf_path: str
    prompt_version: str
    pages: list[PageResult]
    total_linkages: int
    total_unlinked: int
    average_confidence: float
    success: bool
    error: str | None = None


def load_pdf_data(pdf_path: Path, page_filter: int | None = None) -> tuple[list, list, list]:
    """Load PDF and extract AcroForm fields and text blocks.

    Args:
        pdf_path: Path to the PDF file
        page_filter: If set, only process this page number (1-indexed)

    Returns:
        Tuple of (acroform_fields, text_blocks, page_dimensions)
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF (fitz) is required. Install with: pip install pymupdf")
        sys.exit(1)

    doc = fitz.open(str(pdf_path))
    acroform_fields = []
    text_blocks = []
    page_dimensions = []
    block_counter = 0

    for page_num in range(len(doc)):
        page_number = page_num + 1  # 1-indexed

        if page_filter is not None and page_number != page_filter:
            continue

        page = doc[page_num]
        rect = page.rect

        page_dimensions.append({
            "page": page_number,
            "width": rect.width,
            "height": rect.height,
        })

        # Extract AcroForm widgets as box candidates
        for widget in page.widgets():
            if widget is None:
                continue

            wrect = widget.rect
            acroform_fields.append({
                "id": f"box_{page_number}_{len(acroform_fields)}",
                "field_name": widget.field_name or "",
                "field_type": _get_widget_type(widget.field_type),
                "page": page_number,
                "bbox": [wrect.x0, wrect.y0, wrect.width, wrect.height],
                "value": widget.field_value or "",
            })

        # Extract text blocks as label candidates
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in blocks.get("blocks", []):
            if block.get("type") != 0:  # text only
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text or len(text) < 1:
                        continue

                    bbox = span.get("bbox", [0, 0, 0, 0])
                    x, y = bbox[0], bbox[1]
                    width = bbox[2] - bbox[0]
                    height = bbox[3] - bbox[1]

                    if width < 2 or height < 2:
                        continue

                    block_counter += 1
                    text_blocks.append({
                        "id": f"label_{page_number}_{block_counter}",
                        "text": text,
                        "page": page_number,
                        "bbox": [x, y, width, height],
                        "font_name": span.get("font"),
                        "font_size": span.get("size"),
                    })

    doc.close()
    return acroform_fields, text_blocks, page_dimensions


def _get_widget_type(field_type: int) -> str:
    """Convert PyMuPDF widget type to string."""
    type_map = {
        0: "unknown",
        1: "button",
        2: "checkbox",
        3: "combobox",
        4: "listbox",
        5: "radio",
        6: "signature",
        7: "text",
    }
    return type_map.get(field_type, "unknown")


def prepare_llm_input(
    page: int,
    boxes: list[dict],
    labels: list[dict],
    prompt_version: str = "default",
) -> tuple[str, str]:
    """Prepare the LLM input messages.

    Args:
        page: Page number
        boxes: Box candidates for this page
        labels: Label candidates for this page
        prompt_version: Which prompt set to use

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from experiments.labeling.prompts import get_prompt_set

    prompt_set = get_prompt_set(prompt_version)

    # Format boxes with nearby labels
    formatted_boxes = []
    for box in boxes:
        nearby = _find_nearby_labels(box, labels)
        formatted_boxes.append({
            "id": box["id"],
            "type": box.get("field_type", "text"),
            "position": {
                "x": box["bbox"][0],
                "y": box["bbox"][1],
                "width": box["bbox"][2],
                "height": box["bbox"][3],
            },
            "nearby_labels": nearby[:5],
        })

    # Format labels with nearby boxes
    formatted_labels = []
    for label in labels:
        nearby = _find_nearby_boxes(label, boxes)
        formatted_labels.append({
            "id": label["id"],
            "text": label["text"],
            "position": {
                "x": label["bbox"][0],
                "y": label["bbox"][1],
                "width": label["bbox"][2],
                "height": label["bbox"][3],
            },
            "font_name": label.get("font_name"),
            "font_size": label.get("font_size"),
            "nearby_boxes": nearby[:5],
        })

    # Detect language
    language = _detect_language(labels)
    reading_direction = "left-to-right, top-to-bottom"
    if language == "ja":
        reading_direction = "Japanese: typically left-to-right, may have vertical sections"

    # Format spatial clusters
    clusters = _compute_clusters(labels, boxes)

    user_prompt = prompt_set.user_prompt_template.format(
        page=page,
        doc_type="form",
        language=language,
        reading_direction=reading_direction,
        labels_json=json.dumps(formatted_labels, indent=2, ensure_ascii=False),
        boxes_json=json.dumps(formatted_boxes, indent=2, ensure_ascii=False),
        spatial_clusters=json.dumps(clusters, indent=2, ensure_ascii=False),
    )

    return prompt_set.system_prompt, user_prompt


def _find_nearby_labels(box: dict, labels: list[dict], max_distance: float = 200.0) -> list[dict]:
    """Find labels near a box."""
    box_bbox = box["bbox"]
    box_cx = box_bbox[0] + box_bbox[2] / 2
    box_cy = box_bbox[1] + box_bbox[3] / 2

    nearby = []
    for label in labels:
        label_bbox = label["bbox"]
        label_cx = label_bbox[0] + label_bbox[2] / 2
        label_cy = label_bbox[1] + label_bbox[3] / 2

        dist = ((box_cx - label_cx) ** 2 + (box_cy - label_cy) ** 2) ** 0.5
        if dist <= max_distance:
            direction = _compute_direction(box_cx, box_cy, label_cx, label_cy)
            nearby.append({
                "label_id": label["id"],
                "label_text": label["text"][:50],
                "direction": direction,
                "distance_px": round(dist, 1),
            })

    nearby.sort(key=lambda x: x["distance_px"])
    return nearby


def _find_nearby_boxes(label: dict, boxes: list[dict], max_distance: float = 200.0) -> list[dict]:
    """Find boxes near a label."""
    label_bbox = label["bbox"]
    label_cx = label_bbox[0] + label_bbox[2] / 2
    label_cy = label_bbox[1] + label_bbox[3] / 2

    nearby = []
    for box in boxes:
        box_bbox = box["bbox"]
        box_cx = box_bbox[0] + box_bbox[2] / 2
        box_cy = box_bbox[1] + box_bbox[3] / 2

        dist = ((label_cx - box_cx) ** 2 + (label_cy - box_cy) ** 2) ** 0.5
        if dist <= max_distance:
            direction = _compute_direction(label_cx, label_cy, box_cx, box_cy)
            nearby.append({
                "box_id": box["id"],
                "direction": direction,
                "distance_px": round(dist, 1),
            })

    nearby.sort(key=lambda x: x["distance_px"])
    return nearby


def _compute_direction(from_x: float, from_y: float, to_x: float, to_y: float) -> str:
    """Compute direction from one point to another."""
    dx = to_x - from_x
    dy = to_y - from_y

    horizontal = ""
    vertical = ""

    if dx < -20:
        horizontal = "left"
    elif dx > 20:
        horizontal = "right"

    if dy < -20:
        vertical = "above"
    elif dy > 20:
        vertical = "below"

    if vertical and horizontal:
        return f"{vertical}-{horizontal}"
    elif vertical:
        return vertical
    elif horizontal:
        return horizontal
    return "overlapping"


def _detect_language(labels: list[dict]) -> str:
    """Detect primary language from labels."""
    japanese_count = 0
    total_count = len(labels)

    for label in labels:
        text = label.get("text", "")
        for char in text:
            code = ord(char)
            if (0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF) or (0x4E00 <= code <= 0x9FFF):
                japanese_count += 1
                break

    if total_count == 0:
        return "unknown"
    if japanese_count / total_count > 0.3:
        return "ja"
    return "en"


def _compute_clusters(labels: list[dict], boxes: list[dict]) -> list[dict]:
    """Compute spatial clusters of nearby elements."""
    all_elements = []
    for label in labels:
        all_elements.append({
            "type": "label",
            "id": label["id"],
            "y": label["bbox"][1],
            "height": label["bbox"][3],
        })
    for box in boxes:
        all_elements.append({
            "type": "box",
            "id": box["id"],
            "y": box["bbox"][1],
            "height": box["bbox"][3],
        })

    if not all_elements:
        return []

    all_elements.sort(key=lambda e: e["y"])

    clusters = []
    current_cluster: list[dict] = []
    cluster_y_end = 0.0

    for elem in all_elements:
        if current_cluster and elem["y"] > cluster_y_end + 50:
            if len(current_cluster) > 1:
                clusters.append({
                    "y_range": f"{current_cluster[0]['y']:.0f}-{cluster_y_end:.0f}",
                    "labels": [e["id"] for e in current_cluster if e["type"] == "label"],
                    "boxes": [e["id"] for e in current_cluster if e["type"] == "box"],
                })
            current_cluster = []

        current_cluster.append(elem)
        cluster_y_end = max(cluster_y_end, elem["y"] + elem["height"])

    if len(current_cluster) > 1:
        clusters.append({
            "y_range": f"{current_cluster[0]['y']:.0f}-{cluster_y_end:.0f}",
            "labels": [e["id"] for e in current_cluster if e["type"] == "label"],
            "boxes": [e["id"] for e in current_cluster if e["type"] == "box"],
        })

    return clusters


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Call the LLM with the given prompts.

    Args:
        system_prompt: System message
        user_prompt: User message
        model: Model to use
        temperature: Sampling temperature

    Returns:
        Parsed response with linkages
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel, Field as PydanticField
    from app.config import get_settings

    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")

    class FieldLinkage(BaseModel):
        label_id: str = PydanticField(..., description="ID of the label")
        box_id: str = PydanticField(..., description="ID of the box")
        field_name: str = PydanticField(..., description="Human-readable field name")
        field_type: str = PydanticField(..., description="Field type")
        confidence: float = PydanticField(..., ge=0.0, le=1.0)
        rationale: str = PydanticField(..., description="Reasoning")

    class LinkageResponse(BaseModel):
        linkages: list[FieldLinkage] = PydanticField(default_factory=list)
        unlinked_boxes: list[str] = PydanticField(default_factory=list)

    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=120,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    structured_llm = llm.with_structured_output(LinkageResponse)
    response = await structured_llm.ainvoke(messages)

    return {
        "linkages": [l.model_dump() for l in response.linkages],
        "unlinked_boxes": response.unlinked_boxes,
    }


async def run_labeling_test(
    pdf_path: Path,
    prompt_version: str = "default",
    page_filter: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> TestResult:
    """Run the label linking test on a PDF.

    Args:
        pdf_path: Path to the PDF file
        prompt_version: Prompt version to use
        page_filter: Only process this page if set
        dry_run: If True, show prompts without calling LLM
        verbose: Show detailed output

    Returns:
        TestResult with all results
    """
    import time

    print(f"\n{'='*60}")
    print(f"Testing label linking on: {pdf_path.name}")
    print(f"Prompt version: {prompt_version}")
    if page_filter:
        print(f"Page filter: {page_filter}")
    print(f"{'='*60}\n")

    # Load PDF data
    acroform_fields, text_blocks, page_dimensions = load_pdf_data(pdf_path, page_filter)

    print(f"Loaded {len(acroform_fields)} AcroForm fields (boxes)")
    print(f"Loaded {len(text_blocks)} text blocks (potential labels)")
    print(f"Pages: {len(page_dimensions)}")

    if not acroform_fields:
        print("\nWARNING: No AcroForm fields found. This PDF may not have form fields.")
        return TestResult(
            pdf_path=str(pdf_path),
            prompt_version=prompt_version,
            pages=[],
            total_linkages=0,
            total_unlinked=0,
            average_confidence=0.0,
            success=False,
            error="No AcroForm fields found",
        )

    # Group by page
    boxes_by_page: dict[int, list[dict]] = {}
    labels_by_page: dict[int, list[dict]] = {}

    for box in acroform_fields:
        page = box["page"]
        if page not in boxes_by_page:
            boxes_by_page[page] = []
        boxes_by_page[page].append(box)

    for label in text_blocks:
        page = label["page"]
        if page not in labels_by_page:
            labels_by_page[page] = []
        labels_by_page[page].append(label)

    page_results: list[PageResult] = []
    all_boxes = set()
    all_labels = set()

    for page in sorted(boxes_by_page.keys()):
        boxes = boxes_by_page.get(page, [])
        labels = labels_by_page.get(page, [])

        print(f"\n--- Page {page} ---")
        print(f"  Boxes: {len(boxes)}, Labels: {len(labels)}")

        for box in boxes:
            all_boxes.add(box["id"])
        for label in labels:
            all_labels.add(label["id"])

        system_prompt, user_prompt = prepare_llm_input(page, boxes, labels, prompt_version)

        if verbose or dry_run:
            print(f"\n[SYSTEM PROMPT] ({len(system_prompt)} chars)")
            if dry_run:
                print(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt)
            print(f"\n[USER PROMPT] ({len(user_prompt)} chars)")
            if dry_run:
                print(user_prompt[:1000] + "..." if len(user_prompt) > 1000 else user_prompt)

        if dry_run:
            page_results.append(PageResult(
                page=page,
                linkages=[],
                unlinked_boxes=[b["id"] for b in boxes],
                label_count=len(labels),
                box_count=len(boxes),
            ))
            continue

        # Call LLM
        start_time = time.time()
        try:
            response = await call_llm(system_prompt, user_prompt)
            elapsed_ms = (time.time() - start_time) * 1000

            linkages = []
            for link in response.get("linkages", []):
                # Find original label and box for additional info
                label_info = next((l for l in labels if l["id"] == link["label_id"]), {})
                box_info = next((b for b in boxes if b["id"] == link["box_id"]), {})

                linkages.append(LinkageResult(
                    label_id=link["label_id"],
                    box_id=link["box_id"],
                    field_name=link["field_name"],
                    field_type=link["field_type"],
                    confidence=link["confidence"],
                    rationale=link["rationale"],
                    label_text=label_info.get("text", ""),
                    label_bbox=label_info.get("bbox", []),
                    box_bbox=box_info.get("bbox", []),
                ))

            page_results.append(PageResult(
                page=page,
                linkages=linkages,
                unlinked_boxes=response.get("unlinked_boxes", []),
                label_count=len(labels),
                box_count=len(boxes),
                processing_time_ms=elapsed_ms,
            ))

            print(f"  Linked: {len(linkages)}, Unlinked: {len(response.get('unlinked_boxes', []))}")
            print(f"  Time: {elapsed_ms:.0f}ms")

        except Exception as e:
            print(f"  ERROR: {e}")
            page_results.append(PageResult(
                page=page,
                linkages=[],
                unlinked_boxes=[b["id"] for b in boxes],
                label_count=len(labels),
                box_count=len(boxes),
            ))

    # Compute summary
    total_linkages = sum(len(pr.linkages) for pr in page_results)
    total_unlinked = sum(len(pr.unlinked_boxes) for pr in page_results)

    all_confidences = [l.confidence for pr in page_results for l in pr.linkages]
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return TestResult(
        pdf_path=str(pdf_path),
        prompt_version=prompt_version,
        pages=page_results,
        total_linkages=total_linkages,
        total_unlinked=total_unlinked,
        average_confidence=avg_confidence,
        success=True,
    )


def print_results(result: TestResult, verbose: bool = False) -> None:
    """Pretty print the test results."""
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"PDF: {result.pdf_path}")
    print(f"Prompt: {result.prompt_version}")
    print(f"Total Linkages: {result.total_linkages}")
    print(f"Total Unlinked: {result.total_unlinked}")
    print(f"Average Confidence: {result.average_confidence:.2%}")

    if result.error:
        print(f"Error: {result.error}")
        return

    for page_result in result.pages:
        print(f"\n--- Page {page_result.page} ---")
        print(f"Boxes: {page_result.box_count}, Labels: {page_result.label_count}")
        print(f"Linked: {len(page_result.linkages)}, Unlinked: {len(page_result.unlinked_boxes)}")

        if page_result.linkages:
            print("\nLinkages:")
            for link in page_result.linkages:
                conf_bar = "#" * int(link.confidence * 10) + "-" * (10 - int(link.confidence * 10))
                print(f"  [{conf_bar}] {link.confidence:.0%}")
                print(f"    Label: {link.label_id} -> Box: {link.box_id}")
                print(f"    Name: {link.field_name} ({link.field_type})")
                print(f"    Label text: \"{link.label_text[:50]}{'...' if len(link.label_text) > 50 else ''}\"")
                if verbose:
                    print(f"    Rationale: {link.rationale}")

        if page_result.unlinked_boxes:
            print(f"\nUnlinked boxes: {', '.join(page_result.unlinked_boxes)}")


async def compare_prompts(
    pdf_path: Path,
    prompt_a: str,
    prompt_b: str,
    page_filter: int | None = None,
) -> None:
    """Compare two prompt versions on the same PDF."""
    print(f"\n{'='*60}")
    print(f"COMPARING PROMPTS: {prompt_a} vs {prompt_b}")
    print(f"{'='*60}")

    result_a = await run_labeling_test(pdf_path, prompt_a, page_filter)
    result_b = await run_labeling_test(pdf_path, prompt_b, page_filter)

    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}")

    print(f"\n{'Metric':<25} {prompt_a:<15} {prompt_b:<15} {'Diff':<10}")
    print("-" * 65)

    diff_linkages = result_b.total_linkages - result_a.total_linkages
    diff_unlinked = result_b.total_unlinked - result_a.total_unlinked
    diff_conf = result_b.average_confidence - result_a.average_confidence

    print(f"{'Total Linkages':<25} {result_a.total_linkages:<15} {result_b.total_linkages:<15} {diff_linkages:+}")
    print(f"{'Total Unlinked':<25} {result_a.total_unlinked:<15} {result_b.total_unlinked:<15} {diff_unlinked:+}")
    print(f"{'Avg Confidence':<25} {result_a.average_confidence:.2%:<15} {result_b.average_confidence:.2%:<15} {diff_conf:+.2%}")

    # Compare individual linkages
    for pa, pb in zip(result_a.pages, result_b.pages):
        if pa.page != pb.page:
            continue

        links_a = {l.box_id: l for l in pa.linkages}
        links_b = {l.box_id: l for l in pb.linkages}

        common_boxes = set(links_a.keys()) & set(links_b.keys())
        only_a = set(links_a.keys()) - set(links_b.keys())
        only_b = set(links_b.keys()) - set(links_a.keys())

        if only_a or only_b or common_boxes:
            print(f"\nPage {pa.page}:")
            if only_a:
                print(f"  Only in {prompt_a}: {only_a}")
            if only_b:
                print(f"  Only in {prompt_b}: {only_b}")

            # Check for different linkages on same box
            for box_id in common_boxes:
                la = links_a[box_id]
                lb = links_b[box_id]
                if la.label_id != lb.label_id:
                    print(f"  Different label for {box_id}:")
                    print(f"    {prompt_a}: {la.label_id} ({la.label_text[:30]})")
                    print(f"    {prompt_b}: {lb.label_id} ({lb.label_text[:30]})")


def save_results(result: TestResult, output_path: Path) -> None:
    """Save results to JSON file."""
    data = {
        "pdf_path": result.pdf_path,
        "prompt_version": result.prompt_version,
        "total_linkages": result.total_linkages,
        "total_unlinked": result.total_unlinked,
        "average_confidence": result.average_confidence,
        "success": result.success,
        "error": result.error,
        "pages": [
            {
                "page": pr.page,
                "label_count": pr.label_count,
                "box_count": pr.box_count,
                "processing_time_ms": pr.processing_time_ms,
                "linkages": [
                    {
                        "label_id": l.label_id,
                        "box_id": l.box_id,
                        "field_name": l.field_name,
                        "field_type": l.field_type,
                        "confidence": l.confidence,
                        "rationale": l.rationale,
                        "label_text": l.label_text,
                        "label_bbox": l.label_bbox,
                        "box_bbox": l.box_bbox,
                    }
                    for l in pr.linkages
                ],
                "unlinked_boxes": pr.unlinked_boxes,
            }
            for pr in result.pages
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test and tune label linking prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.experiments.labeling.main --pdf form.pdf
  python -m tools.experiments.labeling.main --pdf form.pdf --prompt v2
  python -m tools.experiments.labeling.main --pdf form.pdf --compare default v2
  python -m tools.experiments.labeling.main --pdf form.pdf --page 1 --verbose
  python -m tools.experiments.labeling.main --pdf form.pdf --dry-run
  python -m tools.experiments.labeling.main --pdf form.pdf --output results.json
        """,
    )

    parser.add_argument(
        "--pdf",
        type=Path,
        help="Path to PDF file to test",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="Specific page to process (default: all)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="default",
        help="Prompt version to use (default, v2)",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("PROMPT_A", "PROMPT_B"),
        help="Compare two prompt versions",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path for JSON results",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed LLM responses",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompts without calling LLM",
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="List available prompt versions",
    )

    args = parser.parse_args()

    if args.list_prompts:
        from experiments.labeling.prompts import get_available_prompts, get_prompt_set
        print("Available prompt versions:")
        for name in get_available_prompts():
            ps = get_prompt_set(name)
            print(f"  {name}: {ps.description}")
        return 0

    if not args.pdf:
        # Look for a default test PDF
        default_pdf = _REPO_ROOT / "apps" / "tests" / "assets" / "2025bun_01_input.pdf"
        if default_pdf.exists():
            args.pdf = default_pdf
            print(f"Using default test PDF: {args.pdf}")
        else:
            parser.error("--pdf is required (or place a test PDF at apps/tests/assets/2025bun_01_input.pdf)")

    if not args.pdf.exists():
        print(f"ERROR: PDF file not found: {args.pdf}")
        return 1

    if args.compare:
        asyncio.run(compare_prompts(args.pdf, args.compare[0], args.compare[1], args.page))
        return 0

    result = asyncio.run(run_labeling_test(
        args.pdf,
        args.prompt,
        args.page,
        args.dry_run,
        args.verbose,
    ))

    print_results(result, args.verbose)

    if args.output and not args.dry_run:
        save_results(result, args.output)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
