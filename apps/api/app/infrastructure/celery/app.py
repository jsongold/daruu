"""Celery application factory.

Creates and configures the Celery application instance.
This module should be imported by the worker entrypoint.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

from celery import Celery

from app.infrastructure.celery.config import get_celery_config

if TYPE_CHECKING:
    pass


def create_celery_app() -> Celery:
    """Create and configure a Celery application instance.

    The app is configured with:
    - Redis broker and result backend
    - Task time limits and retry settings
    - Task routing for different queues
    - Serialization settings (JSON)

    Returns:
        Configured Celery application.
    """
    config = get_celery_config()

    # Create Celery app
    app = Celery(
        "daru_pdf",
        broker=config.broker_url,
        backend=config.result_backend,
    )

    # Apply configuration
    app.conf.update(config.to_celery_config())

    # Auto-discover tasks from the tasks module
    app.autodiscover_tasks(["app.infrastructure.celery"])

    return app


@lru_cache
def get_celery_app() -> Celery:
    """Get the cached Celery application instance.

    Returns:
        Singleton Celery application.
    """
    return create_celery_app()


# Module-level celery app instance for worker startup
celery_app = get_celery_app()


def clear_celery_app_cache() -> None:
    """Clear the cached Celery app.

    Useful for testing when a fresh app is needed.
    """
    get_celery_app.cache_clear()
    global celery_app
    celery_app = get_celery_app()
