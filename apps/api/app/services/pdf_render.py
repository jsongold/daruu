from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pypdf import PdfReader

from app.services.cache import get_cached_render, set_cached_render

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderedPage:
    index: int
    width: float
    height: float
    png_base64: str
    text_blocks: list[dict[str, Any]] | None
    visual_anchors: list[dict[str, Any]] | None = None


def render_pdf_pages(
    pdf_bytes: bytes,
    *,
    dpi: int = 150,
    include_text_blocks: bool = True,
    page_indices: list[int] | None = None,
) -> list[RenderedPage]:
    """Render PDF pages with automatic caching."""
    # Check cache first
    cached = get_cached_render(pdf_bytes, page_indices, dpi, include_text_blocks)
    if cached is not None:
        logger.info("Cache HIT: %d pages (dpi=%d)", len(cached), dpi)
        return cached

    logger.info(
        "Cache MISS: Rendering %s pages (dpi=%d)",
        "all" if page_indices is None else str(len(page_indices)),
        dpi,
    )

    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        result = _render_with_pypdf(pdf_bytes)
        set_cached_render(pdf_bytes, page_indices, dpi, include_text_blocks, result)
        return result

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Determine which pages to render
    if page_indices is None:
        pages_to_render = range(doc.page_count)
    else:
        pages_to_render = page_indices

    pages: list[RenderedPage] = []
    for page_index in pages_to_render:
        page = doc.load_page(page_index)
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        png_bytes = pixmap.tobytes("png")
        png_base64 = base64.b64encode(png_bytes).decode("ascii")
        rect = page.rect
        
        # Extract visual anchors (lines/rects)
        visual_anchors = []
        try:
            paths = page.get_drawings()
            for p in paths:
                r = p["rect"]
                # Filter out tiny specks or full page borders
                if r.width < 5 or r.height < 5: 
                    # keep horizontal lines (underlines)
                    if r.width > 20 and r.height < 5:
                        pass
                    elif r.height > 20 and r.width < 5:
                        pass
                    else:
                        continue
                        
                visual_anchors.append({
                    "x0": float(r.x0),
                    "y0": float(r.y0),
                    "x1": float(r.x1),
                    "y1": float(r.y1),
                    "type": "rect" if p["type"] != "s" else "stroke" 
                })
        except Exception:
            pass

        text_blocks = None
        if include_text_blocks:
            blocks = page.get_text("blocks") or []
            text_blocks = []
            for block in blocks:
                x0, y0, x1, y1, text, *_ = block
                cleaned = (text or "").strip()
                if not cleaned:
                    continue
                text_blocks.append(
                    {
                        "x0": float(x0),
                        "y0": float(y0),
                        "x1": float(x1),
                        "y1": float(y1),
                        "text": cleaned,
                    }
                )

        pages.append(
            RenderedPage(
                index=page_index,
                width=float(rect.width),
                height=float(rect.height),
                png_base64=png_base64,
                text_blocks=text_blocks,
                visual_anchors=visual_anchors,
            )
        )

    # Cache before returning
    set_cached_render(pdf_bytes, page_indices, dpi, include_text_blocks, pages)
    return pages


def _render_with_pypdf(pdf_bytes: bytes) -> list[RenderedPage]:
    placeholder_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
        "ASsJTYQAAAAASUVORK5CYII="
    )
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[RenderedPage] = []
    for page_index, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        pages.append(
            RenderedPage(
                index=page_index,
                width=width,
                height=height,
                png_base64=placeholder_png,
                text_blocks=None,
            )
        )
    return pages
