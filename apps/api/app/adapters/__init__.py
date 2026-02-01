"""Adapters layer - DTOs and controllers.

This layer handles the translation between external representations
(HTTP requests/responses, external service formats) and internal
domain/application representations.

Components:
- DTOs: Data Transfer Objects for API requests/responses
"""

from app.adapters.dto import (
    AnalyzeRequestDTO,
    AnalyzeResponseDTO,
    ExtractRequestDTO,
    ExtractResponseDTO,
    FillRequestDTO,
    FillResponseDTO,
    ReviewRequestDTO,
    ReviewResponseDTO,
)

__all__ = [
    "AnalyzeRequestDTO",
    "AnalyzeResponseDTO",
    "ExtractRequestDTO",
    "ExtractResponseDTO",
    "FillRequestDTO",
    "FillResponseDTO",
    "ReviewRequestDTO",
    "ReviewResponseDTO",
]
