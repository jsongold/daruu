#!/usr/bin/env python3
"""
Check if a PDF has AcroForm fields using pypdf.

AcroForm is the PDF standard for interactive forms with fillable fields.
If present, we can extract field definitions directly without vision analysis.

Usage:
    python check_acroform.py <path_to_pdf>
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from pypdf import PdfReader


def check_acroform(pdf_path: str) -> None:
    """Check if PDF has AcroForm fields and display details."""
    print(f"Checking AcroForm in: {pdf_path}\n")
    print("=" * 80)
    
    reader = PdfReader(pdf_path)
    
    # Try to get form fields
    try:
        form_fields = reader.get_form_text_fields()
    except Exception as e:
        print(f"\n❌ Error reading form fields: {e}")
        print("\nThis PDF may not contain AcroForm fields or has a different structure.")
        return
    
    # Check if AcroForm exists
    if form_fields is None:
        print("\n❌ No AcroForm found in this PDF")
        print("\nThis PDF does not contain interactive form fields.")
        print("You'll need to use vision-based analysis (LLM) to extract fields.")
        return
    
    if not form_fields:
        print("\n⚠️  AcroForm exists but no fillable text fields found")
        print("\nTrying to get all fields including checkboxes/radio buttons...")
        
        # Try to get all fields (requires newer pypdf)
        try:
            all_fields = reader.get_fields()
            if all_fields:
                print(f"\n✅ Found {len(all_fields)} total form fields\n")
                display_all_fields(all_fields)
            else:
                print("\n❌ No form fields found")
        except AttributeError:
            print("\n⚠️  pypdf version doesn't support get_fields()")
            print("   Install newer pypdf: pip install --upgrade pypdf")
        return
    
    # Display form field details
    print(f"\n✅ Found {len(form_fields)} fillable text fields\n")
    print("=" * 80)
    
    for field_name, field_value in form_fields.items():
        print(f"\nField: {field_name}")
        print(f"  Default Value: {field_value if field_value else '(empty)'}")
    
    print("\n" + "=" * 80)
    
    # Try to get more detailed field information
    try:
        all_fields = reader.get_fields()
        if all_fields:
            print(f"\n📋 Detailed Field Information ({len(all_fields)} total fields):\n")
            display_all_fields(all_fields)
    except AttributeError:
        print("\n💡 For more details, upgrade pypdf: pip install --upgrade pypdf")


def display_all_fields(fields: dict) -> None:
    """Display detailed information about all form fields."""
    for i, (field_name, field_obj) in enumerate(fields.items(), 1):
        print(f"\n{i}. Field Name: {field_name}")
        
        # Get field type
        field_type = "Unknown"
        if hasattr(field_obj, '/FT'):
            ft = field_obj.get('/FT', '')
            type_map = {
                '/Tx': 'Text',
                '/Btn': 'Button/Checkbox/Radio',
                '/Ch': 'Choice (Dropdown/List)',
                '/Sig': 'Signature'
            }
            field_type = type_map.get(ft, str(ft))
        
        print(f"   Type: {field_type}")
        
        # Get field value
        if hasattr(field_obj, '/V'):
            value = field_obj.get('/V', '')
            print(f"   Value: {value if value else '(empty)'}")
        
        # Get field flags (required, readonly, etc.)
        if hasattr(field_obj, '/Ff'):
            flags = field_obj.get('/Ff', 0)
            flag_meanings = []
            if flags & (1 << 0):
                flag_meanings.append("ReadOnly")
            if flags & (1 << 1):
                flag_meanings.append("Required")
            if flags & (1 << 2):
                flag_meanings.append("NoExport")
            if flag_meanings:
                print(f"   Flags: {', '.join(flag_meanings)}")
        
        # Get field position (if available)
        if hasattr(field_obj, '/Rect'):
            rect = field_obj.get('/Rect', [])
            if rect:
                print(f"   Position: x={rect[0]:.1f}, y={rect[1]:.1f}, "
                      f"width={rect[2]-rect[0]:.1f}, height={rect[3]-rect[1]:.1f}")
        
        # Get page number
        if hasattr(field_obj, '/P'):
            page_ref = field_obj.get('/P')
            print(f"   Page: {page_ref}")


def export_acroform_json(pdf_path: str) -> None:
    """Export AcroForm fields as JSON."""
    reader = PdfReader(pdf_path)
    
    try:
        all_fields = reader.get_fields()
        if not all_fields:
            print("{}")
            return
        
        output = []
        for field_name, field_obj in all_fields.items():
            field_data = {
                "name": field_name,
                "type": str(field_obj.get('/FT', 'Unknown')),
                "value": str(field_obj.get('/V', '')),
            }
            
            # Add position if available
            rect = field_obj.get('/Rect')
            if rect:
                field_data["position"] = {
                    "x": float(rect[0]),
                    "y": float(rect[1]),
                    "width": float(rect[2] - rect[0]),
                    "height": float(rect[3] - rect[1])
                }
            
            output.append(field_data)
        
        print(json.dumps(output, indent=2, ensure_ascii=False))
        
    except AttributeError:
        # Fallback to text fields only
        form_fields = reader.get_form_text_fields()
        if form_fields:
            output = [{"name": k, "value": v} for k, v in form_fields.items()]
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print("{}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python check_acroform.py <path_to_pdf>")
        print("  python check_acroform.py <path_to_pdf> --json")
        print("\nExample:")
        print("  python check_acroform.py /path/to/form.pdf")
        print("  python check_acroform.py /path/to/form.pdf --json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    if "--json" in sys.argv:
        export_acroform_json(pdf_path)
    else:
        check_acroform(pdf_path)
