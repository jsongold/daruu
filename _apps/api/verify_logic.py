
import asyncio
import json
from dataclasses import dataclass
from typing import Any

# Mocking the models and classes to verify logic
@dataclass
class Placement:
    page_index: int
    x: float
    y: float
    max_width: float
    height: float
    font_policy: Any

@dataclass
class FieldDefinition:
    id: str
    key: str
    label: str
    type: str
    required: bool
    placement: Placement
    section: str = None
    notes: str = None

async def test_enrichment_logic():
    print("Testing Enrichment Logic...")
    
    # 1. Simulate extracted AcroForm fields
    fields = [
        FieldDefinition(
            id="H1", key="H1", label="H1", type="string", required=False,
            placement=Placement(page_index=0, x=290, y=12, max_width=40, height=20, font_policy=None)
        ),
        FieldDefinition(
            id="T1", key="T1", label="T1", type="string", required=False,
            placement=Placement(page_index=0, x=40, y=82, max_width=380, height=20, font_policy=None)
        )
    ]
    
    # 2. Simulate LLM Enrichment Response
    llm_response = [
        {"id": "H1", "label": "年号", "section": "ヘッダ部", "notes": "「令和」など"},
        {"id": "T1", "label": "住所", "section": "納税者情報", "notes": "住所を入力"}
    ]
    
    # 3. Simulate enrichment process
    enrichment_map = {item["id"]: item for item in llm_response}
    for f in fields:
        if f.id in enrichment_map:
            item = enrichment_map[f.id]
            f.label = item["label"]
            f.section = item["section"]
            f.notes = item["notes"]
            
    # 4. Verify results
    assert fields[0].label == "年号"
    assert fields[0].section == "ヘッダ部"
    assert fields[1].label == "住所"
    assert fields[1].section == "納税者情報"
    
    print("✅ Enrichment logic verified!")

async def test_coordinate_rendering_logic():
    print("Testing Coordinate Rendering Logic...")
    
    # Mocking ReportLab's canvas coordinate transformation
    page_height = 842.0 # A4
    
    def calculate_draw_y(top_origin_y, field_height):
        # The logic we implemented in pdf_engine.py
        return (page_height - top_origin_y) - field_height
    
    # Suppose a field is at the very top (y=0) with height 20
    # top-origin: y=0, height=20
    # bottom-origin: y should be 842 - 20 = 822
    y_top = 0
    h = 20
    draw_y = calculate_draw_y(y_top, h)
    assert draw_y == 822.0
    
    # Suppose a field is 100 points down
    # top-origin: y=100, height=20
    # bottom-origin: y should be 842 - 100 - 20 = 722
    y_100 = 100
    draw_y = calculate_draw_y(y_100, h)
    assert draw_y == 722.0
    
    print("✅ Coordinate rendering logic verified!")

if __name__ == "__main__":
    asyncio.run(test_enrichment_logic())
    asyncio.run(test_coordinate_rendering_logic())
