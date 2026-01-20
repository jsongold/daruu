from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.models.template_schema import FieldDefinition, TemplateSchema

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
TEMPLATE_DEFAULT_PATH = ASSETS_DIR / "templates" / "sample-template.pdf"
FONT_DEFAULT_PATH = ASSETS_DIR / "fonts" / "ipaexg.ttf"


def _load_template_pdf() -> PdfReader:
    template_url = os.getenv("TEMPLATE_PDF_URL")
    if template_url:
        with urlopen(template_url) as response:
            data = response.read()
        return PdfReader(BytesIO(data))

    template_path = Path(os.getenv("TEMPLATE_PDF_PATH", str(TEMPLATE_DEFAULT_PATH)))
    if not template_path.exists():
        raise FileNotFoundError(f"Template PDF not found: {template_path}")
    return PdfReader(str(template_path))


def _register_font() -> str:
    font_path = Path(os.getenv("JAPANESE_FONT_PATH", str(FONT_DEFAULT_PATH)))
    if font_path.exists():
        font_name = "JapaneseFont"
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
        return font_name
    return "Helvetica"


def _ellipsize_text(text: str, *, font_name: str, font_size: float, max_width: float) -> str:
    ellipsis = "..."
    if pdfmetrics.stringWidth(ellipsis, font_name, font_size) > max_width:
        return ""

    trimmed = text
    while trimmed:
        if pdfmetrics.stringWidth(trimmed + ellipsis, font_name, font_size) <= max_width:
            return trimmed + ellipsis
        trimmed = trimmed[:-1]
    return ellipsis


def _fit_text_to_width(
    text: str, *, font_name: str, font_size: float, min_size: float, max_width: float
) -> tuple[str, float]:
    current_size = font_size
    while current_size > min_size:
        width = pdfmetrics.stringWidth(text, font_name, current_size)
        if width <= max_width:
            return text, current_size
        current_size = max(min_size, current_size - 0.5)

    width = pdfmetrics.stringWidth(text, font_name, min_size)
    if width <= max_width:
        return text, min_size
    return _ellipsize_text(text, font_name=font_name, font_size=min_size, max_width=max_width), min_size


def _draw_field(
    overlay_canvas: canvas.Canvas,
    *,
    field: FieldDefinition,
    value: str,
    font_name: str,
) -> None:
    placement = field.placement
    # ReportLab uses bottom-origin. 
    # If placement.y is top-origin (distance from top of page to TOP of field),
    # then the baseline for drawing should be roughly height - placement.y - field_height.
    # However, if we want to draw at the baseline that corresponds to the AcroForm's bottom edge:
    # PDF y1 = page_height - top_edge_y - field_height
    
    field_height = placement.height or 12 # Default height if not specified
    draw_y = (overlay_canvas._pagesize[1] - placement.y) - field_height
    
    text, font_size = _fit_text_to_width(
        value,
        font_name=font_name,
        font_size=placement.font_policy.size,
        min_size=placement.font_policy.min_size,
        max_width=placement.max_width,
    )
    overlay_canvas.setFont(font_name, font_size)
    if placement.align == "center":
        overlay_canvas.drawCentredString(placement.x + placement.max_width / 2, draw_y, text)
    elif placement.align == "right":
        overlay_canvas.drawRightString(placement.x + placement.max_width, draw_y, text)
    else:
        overlay_canvas.drawString(placement.x, draw_y, text)


def generate_pdf(*, schema: TemplateSchema, data: dict[str, str]) -> bytes:
    template = _load_template_pdf()
    font_name = _register_font()

    writer = PdfWriter()
    for page_index, page in enumerate(template.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay_stream = BytesIO()
        overlay_canvas = canvas.Canvas(overlay_stream, pagesize=(width, height))

        for field in schema.fields:
            if field.placement.page_index != page_index:
                continue
            value = data.get(field.key, "")
            _draw_field(overlay_canvas, field=field, value=str(value), font_name=font_name)

        overlay_canvas.save()
        overlay_stream.seek(0)
        overlay_pdf = PdfReader(overlay_stream)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    output_stream = BytesIO()
    writer.write(output_stream)
    return output_stream.getvalue()
