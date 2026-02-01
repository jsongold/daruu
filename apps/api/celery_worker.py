#!/usr/bin/env python3
"""Celery worker entrypoint.

This module provides the entry point for starting Celery workers.

Usage:
    # Start a worker with default settings
    celery -A celery_worker worker --loglevel=info

    # Start with specific queues
    celery -A celery_worker worker -Q daru_jobs,daru_ingest --loglevel=info

    # Start with concurrency setting
    celery -A celery_worker worker --concurrency=4 --loglevel=info

    # Start with flower monitoring (requires flower package)
    celery -A celery_worker flower --port=5555

Environment Variables:
    CELERY_BROKER_URL: Redis broker URL (default: redis://localhost:6379/0)
    CELERY_RESULT_BACKEND: Redis result backend URL (default: redis://localhost:6379/1)
    CELERY_TASK_SOFT_TIME_LIMIT: Soft time limit in seconds (default: 300)
    CELERY_TASK_TIME_LIMIT: Hard time limit in seconds (default: 600)
    CELERY_WORKER_CONCURRENCY: Number of worker processes (default: 4)
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

# Import the Celery app
from app.infrastructure.celery import celery_app

# This allows the module to be used as the Celery app module
app = celery_app

if __name__ == "__main__":
    # Allow running directly: python celery_worker.py worker --loglevel=info
    celery_app.start()
