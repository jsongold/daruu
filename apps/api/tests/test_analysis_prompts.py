
import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.analysis.prompts import build_vision_prompt
from app.services.analysis.strategies import VisionLowResStrategy
from app.services.pdf_render import RenderedPage
from app.models.template_schema import DraftTemplate

def test_build_vision_prompt():
    prompt = build_vision_prompt(page_index=0, width=595.0, height=842.0)
    assert "MUST extract fields ONLY from what is visible" in prompt
    assert "IMPORTANT RULES (anti-hallucination)" in prompt
    assert "page_index: 0" in prompt
    assert "Coordinate Rules" not in prompt # old prompt text logic was replaced
    assert "COORDINATE SYSTEM" in prompt
    assert "OUTPUT FORMAT" in prompt
    assert "Return JSON ONLY" in prompt

def test_vision_strategy_parsing():
    import asyncio
    asyncio.run(_test_vision_strategy_parsing_async())

async def _test_vision_strategy_parsing_async():
    # Mock data
    mock_json_response = [
        {
            "id": "full_name",
            "label": "Full Name",
            "page_index": 0,
            "x": 100,
            "y": 200,
            "w": 300,
            "h": 50,
            "kind": "text",
            "section": "Personal Info"
        },
        {
            "id": "agree_terms",
            "label": "I agree",
            "page_index": 0,
            "x": 100,
            "y": 300,
            "w": 20,
            "h": 20,
            "kind": "checkbox",
            "section": "Terms"
        }
    ]
    
    start_page = RenderedPage(index=0, width=1000, height=1000, png_base64="fake", text_blocks=[])
    
    strategy = VisionLowResStrategy()
    
    # Mock _call_openai to return our JSON list string
    with patch.object(strategy, "_call_openai", return_value=json.dumps(mock_json_response)):
        # We also need to mock _get_api_config to avoid env var error
        with patch.object(strategy, "_get_api_config", return_value=("fake_key", "fake_url", "fake_model")):
            result = await strategy.analyze([start_page], {})
            
            assert isinstance(result, DraftTemplate)
            assert len(result.fields) == 2
            
            f1 = result.fields[0]
            assert f1.id == "full_name"
            assert f1.type == "string"
            assert f1.placement.x == 100.0
            
            f2 = result.fields[1]
            assert f2.id == "agree_terms"
            assert f2.type == "string"  # Schema only supports string
            assert f2.placement.max_width == 20.0
