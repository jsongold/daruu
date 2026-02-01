"""Celery async task processing infrastructure.

This module provides Celery integration for asynchronous task processing:

- celery_app: The Celery application instance
- Tasks: process_job_task, ingest_document_task
- CeleryTaskQueue: Implementation of TaskQueue port

Usage:
    from app.infrastructure.celery import celery_app, get_task_queue

    # Enqueue a job processing task
    task_queue = get_task_queue()
    task_id = await task_queue.enqueue("process_job", job_id)

Worker startup:
    celery -A app.infrastructure.celery worker --loglevel=info
"""

from app.infrastructure.celery.app import celery_app, get_celery_app
from app.infrastructure.celery.config import CeleryConfig, get_celery_config
from app.infrastructure.celery.task_queue import CeleryTaskQueue, get_task_queue
from app.infrastructure.celery.tasks import (
    ingest_document_task,
    process_job_task,
)

__all__ = [
    # Celery app
    "celery_app",
    "get_celery_app",
    # Configuration
    "CeleryConfig",
    "get_celery_config",
    # Task Queue implementation
    "CeleryTaskQueue",
    "get_task_queue",
    # Tasks
    "process_job_task",
    "ingest_document_task",
]
