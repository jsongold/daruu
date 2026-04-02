"""Extract visual structure from PDF forms using PyMuPDF (fitz).

Two entry points:
  - extract_lines_fitz():  raw vector lines for UI visualisation
  - build_segments_fitz(): grid-cell Segments for LLM context
"""

from __future__ import annotations

import statistics
from uuid import uuid4

import fitz

from app.models import BBox, FormField, Segment, TextBlock


# ---------------------------------------------------------------------------
# Shared: extract all vector lines from a page
# ---------------------------------------------------------------------------

def _collect_lines(
    page: fitz.Page,
    page_w: float,
    page_h: float,
) -> tuple[list[tuple[float, float, float, float]], list[tuple[float, float, float, float]]]:
    """Return (h_lines, v_lines) as lists of (x0, y0, x1, y1) in normalised coords.

    h_lines: nearly horizontal segments (dy < 2pt)
    v_lines: nearly vertical segments (dx < 2pt)
    """
    drawings = page.get_drawings()
    h_lines: list[tuple[float, float, float, float]] = []
    v_lines: list[tuple[float, float, float, float]] = []

    for d in drawings:
        for item in d.get("items", []):
            kind = item[0]
            if kind == "l":
                p1, p2 = item[1], item[2]
                dx = abs(p1.x - p2.x)
                dy = abs(p1.y - p2.y)
                nx0, ny0 = p1.x / page_w, p1.y / page_h
                nx1, ny1 = p2.x / page_w, p2.y / page_h
                if dy < 2.0 and dx > 5.0:
                    h_lines.append((min(nx0, nx1), min(ny0, ny1), max(nx0, nx1), max(ny0, ny1)))
                if dx < 2.0 and dy > 5.0:
                    v_lines.append((min(nx0, nx1), min(ny0, ny1), max(nx0, nx1), max(ny0, ny1)))
            elif kind == "re":
                rect = item[1]
                rw, rh = rect.width, rect.height
                nx0 = rect.x0 / page_w
                ny0 = rect.y0 / page_h
                nx1 = rect.x1 / page_w
                ny1 = rect.y1 / page_h
                if rh < 3.0 and rw > 5.0:
                    h_lines.append((min(nx0, nx1), min(ny0, ny1), max(nx0, nx1), max(ny0, ny1)))
                if rw < 3.0 and rh > 5.0:
                    v_lines.append((min(nx0, nx1), min(ny0, ny1), max(nx0, nx1), max(ny0, ny1)))

    return h_lines, v_lines


# ---------------------------------------------------------------------------
# 1. Raw lines for UI visualisation
# ---------------------------------------------------------------------------

def extract_lines_fitz(
    pdf_path: str,
) -> list[Segment]:
    """Return every vector line drawn on the PDF as a thin Segment (no filtering)."""
    doc = fitz.open(pdf_path)
    segments: list[Segment] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_w = page.rect.width or 1.0
        page_h = page.rect.height or 1.0

        h_lines, v_lines = _collect_lines(page, page_w, page_h)

        for x0, y0, x1, y1 in h_lines + v_lines:
            w = max(x1 - x0, 0.001)
            h = max(y1 - y0, 0.001)
            segments.append(Segment(
                id=str(uuid4()), title=None,
                bbox=BBox(x=x0, y=y0, width=w, height=h),
                page=page_num,
            ))

    doc.close()
    return segments


# ---------------------------------------------------------------------------
# 2. Grid-cell segments for LLM context
# ---------------------------------------------------------------------------

def _merge_close(values: list[float], threshold: float = 0.008) -> list[float]:
    """Merge values within threshold distance."""
    if not values:
        return []
    values = sorted(values)
    merged = [values[0]]
    for v in values[1:]:
        if v - merged[-1] > threshold:
            merged.append(v)
        else:
            merged[-1] = (merged[-1] + v) / 2.0
    return merged


def _find_title_in_cell(
    page: fitz.Page,
    page_w: float,
    page_h: float,
    x0: float, y0: float, x1: float, y1: float,
) -> str | None:
    """Find a title for a cell: first meaningful text line near the top.

    Strategy: return the first text line whose centre falls inside the
    cell's upper 40% (or first 6% of page height, whichever is smaller).
    Skip very short strings (<=1 char) that are likely decorative.
    """
    data = page.get_text("dict")
    search_y = y0 + min(0.06, (y1 - y0) * 0.4)

    best: tuple[float, str] | None = None  # (y_pos, text)

    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            first = spans[0]
            sy = first["bbox"][1] / page_h
            sx = first["bbox"][0] / page_w
            if sy < y0 - 0.005 or sy > search_y:
                continue
            if sx < x0 - 0.01 or sx > x1 + 0.01:
                continue
            text = " ".join(s.get("text", "") for s in spans).strip()
            if len(text) <= 1:
                continue
            if best is None or sy < best[0]:
                best = (sy, text)

    if best and 1 < len(best[1]) < 60:
        return best[1]
    return None


def build_segments_fitz(
    pdf_path: str,
    fields: list[FormField] | None = None,
    text_blocks: list[TextBlock] | None = None,
    h_min_ratio: float = 0.70,
    v_min_ratio: float = 0.45,
) -> list[Segment]:
    """Build grid-cell segments from filtered horizontal + vertical rules.

    Args:
        h_min_ratio: minimum width (fraction of page) for horizontal lines
        v_min_ratio: minimum height (fraction of page) for vertical lines
    """
    doc = fitz.open(pdf_path)
    segments: list[Segment] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_w = page.rect.width or 1.0
        page_h = page.rect.height or 1.0

        h_lines, v_lines = _collect_lines(page, page_w, page_h)

        # Filter by length
        h_ys = [((y0 + y1) / 2.0) for x0, y0, x1, y1 in h_lines if (x1 - x0) >= h_min_ratio]
        v_xs = [((x0 + x1) / 2.0) for x0, y0, x1, y1 in v_lines if (y1 - y0) >= v_min_ratio]

        h_ys = _merge_close(h_ys)
        v_xs = _merge_close(v_xs)

        # Remove edge-hugging splits
        h_ys = [y for y in h_ys if 0.02 < y < 0.98]
        v_xs = [x for x in v_xs if 0.02 < x < 0.98]

        if not h_ys and not v_xs:
            segments.append(Segment(
                id=str(uuid4()), title=None,
                bbox=BBox(x=0.0, y=0.0, width=1.0, height=1.0),
                page=page_num,
            ))
            continue

        y_bounds = [0.0] + h_ys + [1.0]
        x_bounds = [0.0] + v_xs + [1.0]

        for yi in range(len(y_bounds) - 1):
            for xi in range(len(x_bounds) - 1):
                cx0 = x_bounds[xi]
                cx1 = x_bounds[xi + 1]
                cy0 = y_bounds[yi]
                cy1 = y_bounds[yi + 1]

                if (cx1 - cx0) < 0.03 or (cy1 - cy0) < 0.015:
                    continue

                title = _find_title_in_cell(page, page_w, page_h, cx0, cy0, cx1, cy1)

                fids: list[str] = []
                tids: list[str] = []

                if fields:
                    for f in fields:
                        if f.page != page_num or f.bbox is None:
                            continue
                        fcx = f.bbox.x + f.bbox.width / 2.0
                        fcy = f.bbox.y + f.bbox.height / 2.0
                        if cx0 <= fcx <= cx1 and cy0 <= fcy <= cy1:
                            fids.append(f.id)

                if text_blocks:
                    for tb in text_blocks:
                        if tb.page != page_num:
                            continue
                        tcx = tb.bbox.x + tb.bbox.width / 2.0
                        tcy = tb.bbox.y + tb.bbox.height / 2.0
                        if cx0 <= tcx <= cx1 and cy0 <= tcy <= cy1:
                            tids.append(tb.id)

                segments.append(Segment(
                    id=str(uuid4()),
                    title=title,
                    bbox=BBox(x=cx0, y=cy0, width=cx1 - cx0, height=cy1 - cy0),
                    page=page_num,
                    field_ids=fids,
                    text_block_ids=tids,
                ))

    doc.close()
    return segments


# Backward compat alias
extract_segments_fitz = build_segments_fitz
