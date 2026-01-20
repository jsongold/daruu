import logging
import os
import json
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analyze import router as analyze_router
from app.routes.documents import router as documents_router
from app.routes.generate import router as generate_router
from app.routes.templates import router as templates_router

app = FastAPI(title="Daru PDF API")

log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# Configure logging with more detailed format when DEBUG is enabled
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
if DEBUG:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
else:
    logging.basicConfig(level=log_level)

logger = logging.getLogger(__name__)

if DEBUG:
    logger.info("DEBUG mode enabled - detailed output will be generated")


allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
allow_origins = (
    [origin.strip() for origin in allow_origins_env.split(",") if origin.strip()]
    if allow_origins_env
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)
app.include_router(generate_router)
app.include_router(templates_router)
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
