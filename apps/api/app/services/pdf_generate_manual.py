from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
from urllib.request import urlopen

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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


def generate_pdf(*, name: str, address: str) -> bytes:
    template = _load_template_pdf()
    page = template.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)

    # PDF coordinate system: points, origin at bottom-left.
    overlay_stream = BytesIO()
    overlay_canvas = canvas.Canvas(overlay_stream, pagesize=(width, height))
    font_name = _register_font()
    overlay_canvas.setFont(font_name, 12)

    # Manual placement coordinates (points).
    overlay_canvas.drawString(72, height - 120, name)
    overlay_canvas.drawString(72, height - 150, address)
    overlay_canvas.save()

    overlay_stream.seek(0)
    overlay_pdf = PdfReader(overlay_stream)
    page.merge_page(overlay_pdf.pages[0])

    writer = PdfWriter()
    writer.add_page(page)
    output_stream = BytesIO()
    writer.write(output_stream)
    return output_stream.getvalue()
