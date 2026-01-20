from __future__ import annotations

import logging
from typing import Literal

from app.models.template_schema import DraftTemplate
from app.services.analysis import HybridStrategy, VisionLowResStrategy
from app.services.pdf_render import RenderedPage

logger = logging.getLogger(__name__)

StrategyType = Literal["auto", "hybrid", "vision_low_res", "acroform_only", "vision_only"]


async def analyze_template(
    pages: list[RenderedPage], 
    strategy_type: StrategyType = "hybrid"
) -> DraftTemplate:
    """
    Analyze the rendered PDF pages using the specified strategy.
    """
    logger.info("Analyzing template with strategy: %s", strategy_type)
    
    # Simple Factory
    strategies = {
        "hybrid": HybridStrategy(),
        "vision_low_res": VisionLowResStrategy(),
    }
    
    strategy = strategies.get(strategy_type)
    if not strategy:
        # Fallback or strict error
        logger.warning("Unknown strategy '%s', falling back to hybrid", strategy_type)
        strategy = strategies["hybrid"]

    schema = DraftTemplate.model_json_schema()
    
    # Execute strategy
    return await strategy.analyze(pages, schema)

# Wait, `asyncio.run` inside an async loop (route) will fail.
# It's better to make `analyze_template` async and await it in the route.
