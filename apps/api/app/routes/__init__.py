"""API route handlers."""

from app.routes.adjust import router as adjust_router
from app.routes.analyze import router as analyze_router
from app.routes.auth import router as auth_router
from app.routes.conversations import router as conversations_router
from app.routes.data_sources import router as data_sources_router
from app.routes.documents import router as documents_router
from app.routes.edits import router as edits_router
from app.routes.extract import router as extract_router
from app.routes.extract_service import router as extract_service_router
from app.routes.fill import router as fill_router
from app.routes.fill_service import router as fill_service_router
from app.routes.health import router as health_router
from app.routes.ingest import router as ingest_router
from app.routes.jobs import router as jobs_router
from app.routes.mapping import router as mapping_router
from app.routes.review import router as review_router
from app.routes.review_service import router as review_service_router
from app.routes.structure_labelling import router as structure_labelling_router
from app.routes.templates import router as templates_router
from app.routes.prompt_attempts import router as prompt_attempts_router
from app.routes.autofill_pipeline import router as autofill_pipeline_router
from app.routes.corrections import router as corrections_router
from app.routes.rules import router as rules_router
from app.routes.annotations import router as annotations_router
from app.routes.vision_autofill import router as vision_autofill_router

__all__ = [
    "annotations_router",
    "autofill_pipeline_router",
    "corrections_router",
    "rules_router",
    "adjust_router",
    "analyze_router",
    "auth_router",
    "conversations_router",
    "data_sources_router",
    "documents_router",
    "edits_router",
    "extract_router",
    "extract_service_router",
    "fill_router",
    "fill_service_router",
    "health_router",
    "ingest_router",
    "jobs_router",
    "mapping_router",
    "review_router",
    "review_service_router",
    "structure_labelling_router",
    "prompt_attempts_router",
    "templates_router",
    "vision_autofill_router",
]
