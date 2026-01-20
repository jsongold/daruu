#!/usr/bin/env python3
"""
Visual debugger for PyMuPDF extraction results.

This script creates a visual representation of extracted visual anchors
by drawing them on the PDF page image.

Usage:
    python visualize_extraction.py <path_to_pdf> [output_image.png]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdf_render import render_pdf_pages


def visualize_extraction(pdf_path: str, output_path: str | None = None) -> None:
    """Create a visual representation of extraction results."""
    try:
        from PIL import Image, ImageDraw
        import base64
        import io
    except ImportError:
        print("Error: This script requires Pillow. Install with: pip install Pillow")
        sys.exit(1)
    
    print(f"Visualizing extraction from: {pdf_path}\n")
    
    # Read and extract
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=True)
    
    if not pages:
        print("No pages found!")
        return
    
    # Process first page for visualization
    page = pages[0]
    
    # Decode base64 PNG
    img_bytes = base64.b64decode(page.png_base64)
    img = Image.open(io.BytesIO(img_bytes))
    
    # Create drawing context
    draw = ImageDraw.Draw(img)
    
    # Scale factor from points to pixels (at 150 DPI)
    scale = 150 / 72  # DPI / points_per_inch
    
    # Draw visual anchors in red
    if page.visual_anchors:
        print(f"Drawing {len(page.visual_anchors)} visual anchors in RED...")
        for anchor in page.visual_anchors:
            x0 = anchor["x0"] * scale
            y0 = anchor["y0"] * scale
            x1 = anchor["x1"] * scale
            y1 = anchor["y1"] * scale
            
            # Draw rectangle
            draw.rectangle([x0, y0, x1, y1], outline="red", width=2)
    else:
        print("No visual anchors found.")
    
    # Draw text blocks in blue
    if page.text_blocks:
        print(f"Drawing {len(page.text_blocks)} text blocks in BLUE...")
        for block in page.text_blocks:
            x0 = block["x0"] * scale
            y0 = block["y0"] * scale
            x1 = block["x1"] * scale
            y1 = block["y1"] * scale
            
            # Draw rectangle
            draw.rectangle([x0, y0, x1, y1], outline="blue", width=1)
    else:
        print("No text blocks found.")
    
    # Save output
    if output_path is None:
        output_path = f"extraction_debug_page_{page.index}.png"
    
    img.save(output_path)
    print(f"\n✅ Saved visualization to: {output_path}")
    print(f"\nLegend:")
    print(f"  🔴 RED boxes = Visual Anchors (lines/rectangles)")
    print(f"  🔵 BLUE boxes = Text Blocks")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python visualize_extraction.py <path_to_pdf> [output_image.png]")
        print("\nExample:")
        print("  python visualize_extraction.py assets/templates/sample-template.pdf debug.png")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    visualize_extraction(pdf_path, output_path)
