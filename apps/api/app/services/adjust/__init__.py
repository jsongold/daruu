"""Adjust service for bbox and render parameter corrections.

This is a deterministic Service (no Agent/LLM) that:
- Corrects field bboxes based on overflow/overlap issues
- Generates patches for bbox and rendering parameter changes
- Maintains deterministic behavior (same input -> same output)

Service vs Agent:
- This is a Service (deterministic, no LLM reasoning)
- Uses pure computational rules for adjustments
"""

from app.services.adjust.service import AdjustService

__all__ = ["AdjustService"]
