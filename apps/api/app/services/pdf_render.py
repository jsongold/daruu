from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pypdf import PdfReader


@dataclass(frozen=True)
class RenderedPage:
    index: int
    width: float
    height: float
    png_base64: str
    text_blocks: list[dict[str, Any]] | None
    visual_anchors: list[dict[str, Any]] | None = None


def render_pdf_pages(
    pdf_bytes: bytes, *, dpi: int = 150, include_text_blocks: bool = True
) -> list[RenderedPage]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        return _render_with_pypdf(pdf_bytes)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[RenderedPage] = []
    for page_index in range(doc.page_count):
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
