#!/usr/bin/env python3
"""
Test utility to inspect PyMuPDF extraction results from pdf_render.py

Usage:
    python test_pymupdf_extraction.py <path_to_pdf>
    
This will show:
- Page dimensions
- Number of visual anchors (lines/rectangles)
- Number of text blocks
- Sample visual anchors
- Sample text blocks
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add the app module to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdf_render import render_pdf_pages


def test_extraction(pdf_path: str) -> None:
    """Test PyMuPDF extraction on a PDF file."""
    print(f"Testing PyMuPDF extraction on: {pdf_path}\n")
    print("=" * 80)
    
    # Read PDF
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Extract pages
    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=True)
    
    print(f"\n📄 Total Pages: {len(pages)}\n")
    
    for page in pages:
        print(f"\n{'=' * 80}")
        print(f"PAGE {page.index + 1}")
        print(f"{'=' * 80}")
        print(f"  Dimensions: {page.width:.1f} x {page.height:.1f} points")
        print(f"  Visual Anchors: {len(page.visual_anchors or [])}")
        print(f"  Text Blocks: {len(page.text_blocks or [])}")
        
        # Show sample visual anchors
        if page.visual_anchors:
            print(f"\n  📐 Visual Anchors (Lines/Rectangles):")
            for i, anchor in enumerate(page.visual_anchors[:5], 1):
                width = anchor["x1"] - anchor["x0"]
                height = anchor["y1"] - anchor["y0"]
                print(f"    {i}. Type={anchor['type']:<8} "
                      f"Pos=({anchor['x0']:.1f}, {anchor['y0']:.1f}) "
                      f"Size={width:.1f}x{height:.1f}")
            if len(page.visual_anchors) > 5:
                print(f"    ... and {len(page.visual_anchors) - 5} more")
        
        # Show sample text blocks
        if page.text_blocks:
            print(f"\n  📝 Text Blocks:")
            for i, block in enumerate(page.text_blocks[:5], 1):
                text_preview = block["text"][:60].replace("\n", " ")
                if len(block["text"]) > 60:
                    text_preview += "..."
                print(f"    {i}. Pos=({block['x0']:.1f}, {block['y0']:.1f}) "
                      f"Text=\"{text_preview}\"")
            if len(page.text_blocks) > 5:
                print(f"    ... and {len(page.text_blocks) - 5} more")
    
    print(f"\n{'=' * 80}")
    print("\n✅ Extraction complete!\n")
    
    # Summary
    total_anchors = sum(len(p.visual_anchors or []) for p in pages)
    total_blocks = sum(len(p.text_blocks or []) for p in pages)
    
    print("📊 Summary:")
    print(f"  Total Visual Anchors: {total_anchors}")
    print(f"  Total Text Blocks: {total_blocks}")
    print(f"  Average Anchors/Page: {total_anchors / len(pages):.1f}")
    print(f"  Average Text Blocks/Page: {total_blocks / len(pages):.1f}")
    
    # Classification hint
    print(f"\n💡 Classification Hint:")
    print(f"  DocumentClassifier threshold: 15 visual anchors")
    if pages:
        first_page_anchors = len(pages[0].visual_anchors or [])
        if first_page_anchors >= 15:
            print(f"  ✓ First page has {first_page_anchors} anchors → Would trigger LLM classification")
        else:
            print(f"  ✗ First page has {first_page_anchors} anchors → Would be rejected as non-form")


def dump_json(pdf_path: str) -> None:
    """Dump extraction results as JSON."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    pages = render_pdf_pages(pdf_bytes, dpi=150, include_text_blocks=True)
    
    output = []
    for page in pages:
        output.append({
            "index": page.index,
            "width": page.width,
            "height": page.height,
            "visual_anchors": page.visual_anchors,
            "text_blocks": page.text_blocks,
            "png_base64_length": len(page.png_base64) if page.png_base64 else 0
        })
    
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_pymupdf_extraction.py <path_to_pdf>")
        print("  python test_pymupdf_extraction.py <path_to_pdf> --json")
        print("\nExample:")
        print("  python test_pymupdf_extraction.py assets/templates/sample-template.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    if "--json" in sys.argv:
        dump_json(pdf_path)
    else:
        test_extraction(pdf_path)
