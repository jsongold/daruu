#!/usr/bin/env python3
"""
Example: Using the functional pipeline for PDF analysis
"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.analysis.pipeline import analyze_pdf


def main():
    if len(sys.argv) < 2:
        print("Usage: python example_pipeline.py <path_to_pdf> [strategy]")
        print("\nStrategies:")
        print("  auto           - Full pipeline (AcroForm → Visual → LLM → Vision)")
        print("  acroform_only  - Only try AcroForm extraction")
        print("  vision_only    - Skip AcroForm, go straight to vision")
        print("  vision_low_res - Use low-res vision strategy")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else "auto"
    
    print(f"Analyzing: {pdf_path}")
    print(f"Strategy: {strategy}\n")
    print("=" * 80)
    
    # Read PDF
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Run pipeline
    template = analyze_pdf(pdf_bytes, strategy=strategy)
    
    # Display results
    print(f"\nTemplate: {template['name']}")
    print(f"Fields: {len(template['fields'])}")
    
    if template.get('description'):
        print(f"Description: {template['description']}")
    
    print("\n" + "=" * 80)
    
    # Show first few fields
    if template['fields']:
        print("\nFirst 5 fields:")
        for i, field in enumerate(template['fields'][:5], 1):
            print(f"  {i}. {field['id']} - {field['label']} (page {field['placement']['page_index']})")
        
        if len(template['fields']) > 5:
            print(f"  ... and {len(template['fields']) - 5} more")


if __name__ == "__main__":
    main()
