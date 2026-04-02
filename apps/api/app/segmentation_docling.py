"""Extract visual segments/sections from PDF forms using docling (>=2.0.0).

Uses docling's DocumentConverter for layout analysis to identify section
headings and compute enclosing bounding boxes for each segment.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from docling.document_converter import DocumentConverter

from app.models import BBox, FormField, Segment, TextBlock

logger = logging.getLogger(__name__)


def _normalize_bbox(
    bbox_obj: object,
    page_width: float,
    page_height: float,
) -> BBox:
    """Convert a docling BoundingBox to a normalized 0-1 BBox."""
    l = bbox_obj.l / page_width if page_width > 0 else 0.0
    t = bbox_obj.t / page_height if page_height > 0 else 0.0
    r = bbox_obj.r / page_width if page_width > 0 else 0.0
    b = bbox_obj.b / page_height if page_height > 0 else 0.0
    return BBox(
        x=min(l, r),
        y=min(t, b),
        width=abs(r - l),
        height=abs(b - t),
    )


def _vertical_center(bbox: BBox) -> float:
    return bbox.y + bbox.height / 2.0


def _merge_bboxes(bboxes: list[BBox]) -> BBox:
    """Compute the enclosing bounding box for a list of BBox objects."""
    if not bboxes:
        return BBox(x=0.0, y=0.0, width=1.0, height=1.0)
    min_x = min(b.x for b in bboxes)
    min_y = min(b.y for b in bboxes)
    max_x = max(b.x + b.width for b in bboxes)
    max_y = max(b.y + b.height for b in bboxes)
    return BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)


def _get_page_dimensions(
    result: object,
) -> dict[int, tuple[float, float]]:
    """Extract page dimensions (width, height) from the conversion result.

    Tries multiple docling API surfaces to find page size info.
    Returns a dict mapping 1-based page number to (width, height).
    """
    dims: dict[int, tuple[float, float]] = {}

    # docling 2.x: result.pages is a list or dict of page objects
    pages = getattr(result, "pages", None)
    if pages:
        items = pages.values() if isinstance(pages, dict) else pages
        for pg in items:
            pno = getattr(pg, "page_no", None)
            size = getattr(pg, "size", None)
            if pno is not None and size is not None:
                dims[pno] = (
                    getattr(size, "width", 612.0),
                    getattr(size, "height", 792.0),
                )
    return dims


_HEADING_LABELS = frozenset({
    "section_header",
    "title",
    "page_header",
    "heading",
})


def extract_segments_docling(
    pdf_path: str,
    fields: list[FormField] | None = None,
    text_blocks: list[TextBlock] | None = None,
) -> list[Segment]:
    """Extract segments from a PDF using docling's layout analysis.

    Each heading detected by docling starts a new segment. Content elements
    between headings are grouped into the preceding segment. If no headings
    are found, one segment per page is returned as a fallback.

    Args:
        pdf_path: Path to the PDF file.
        fields: Optional form fields to assign to segments by y-overlap.
        text_blocks: Optional text blocks to assign to segments.

    Returns:
        A list of Segment objects with bounding boxes and assigned IDs.
    """
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    doc = result.document

    page_dims = _get_page_dimensions(result)
    default_dim = (612.0, 792.0)

    # Collect structured elements with provenance
    raw_segments: list[dict] = []
    current: dict | None = None

    for item, _level in doc.iterate_items():
        prov_list = getattr(item, "prov", None)
        if not prov_list:
            continue
        prov = prov_list[0]
        page_no = getattr(prov, "page_no", 1)
        bbox_raw = getattr(prov, "bbox", None)
        if bbox_raw is None:
            continue

        pw, ph = page_dims.get(page_no, default_dim)
        norm_bbox = _normalize_bbox(bbox_raw, pw, ph)
        label = getattr(item, "label", "")

        is_heading = label.lower().replace("-", "_") in _HEADING_LABELS
        item_text = getattr(item, "text", "") or ""

        if is_heading:
            current = {
                "title": item_text.strip() or None,
                "page": page_no,
                "bboxes": [norm_bbox],
            }
            raw_segments.append(current)
        else:
            if current is None or current["page"] != page_no:
                current = {
                    "title": None,
                    "page": page_no,
                    "bboxes": [],
                }
                raw_segments.append(current)
            current["bboxes"].append(norm_bbox)

    # Fallback: if no segments found, create one per page
    if not raw_segments:
        all_pages = set(page_dims.keys()) or {1}
        for pno in sorted(all_pages):
            raw_segments.append({
                "title": None,
                "page": pno,
                "bboxes": [BBox(x=0.0, y=0.0, width=1.0, height=1.0)],
            })

    # Build Segment objects
    segments: list[Segment] = []
    for seg_data in raw_segments:
        enclosing = _merge_bboxes(seg_data["bboxes"])
        seg = Segment(
            id=str(uuid4()),
            title=seg_data["title"],
            bbox=enclosing,
            page=seg_data["page"],
        )
        segments.append(seg)

    # Assign fields and text blocks to segments by vertical overlap
    segments = _assign_items_to_segments(segments, fields, text_blocks)
    return segments


def _assign_items_to_segments(
    segments: list[Segment],
    fields: list[FormField] | None,
    text_blocks: list[TextBlock] | None,
) -> list[Segment]:
    """Assign fields and text blocks to segments by page and y-range overlap."""
    if not fields and not text_blocks:
        return segments

    updated: list[Segment] = []
    for seg in segments:
        y_min = seg.bbox.y
        y_max = seg.bbox.y + seg.bbox.height

        field_ids: list[str] = []
        if fields:
            for f in fields:
                if f.page != seg.page or f.bbox is None:
                    continue
                vc = _vertical_center(f.bbox)
                if y_min <= vc <= y_max:
                    field_ids.append(f.id)

        tb_ids: list[str] = []
        if text_blocks:
            for tb in text_blocks:
                if tb.page != seg.page:
                    continue
                vc = _vertical_center(tb.bbox)
                if y_min <= vc <= y_max:
                    tb_ids.append(tb.id)

        updated.append(Segment(
            id=seg.id,
            title=seg.title,
            bbox=seg.bbox,
            page=seg.page,
            field_ids=field_ids,
            text_block_ids=tb_ids,
        ))
    return updated
