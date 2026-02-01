"""Data Transfer Objects for API endpoints.

DTOs define the external API contract and handle validation of
incoming requests. They are separate from domain entities to allow
the API contract to evolve independently of the domain model.
"""

from app.adapters.dto.analyze import AnalyzeRequestDTO, AnalyzeResponseDTO
from app.adapters.dto.extract import ExtractRequestDTO, ExtractResponseDTO
from app.adapters.dto.fill import FillRequestDTO, FillResponseDTO
from app.adapters.dto.review import ReviewRequestDTO, ReviewResponseDTO

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
