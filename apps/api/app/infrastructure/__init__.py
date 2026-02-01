"""Infrastructure layer implementations.

This module contains concrete implementations of repository interfaces
and other infrastructure concerns (database, file storage, external APIs).

Following Clean Architecture:
- Interfaces (Ports) are defined in `app.application.ports`
- Implementations (Adapters) are in `app.infrastructure.*`
- Services depend on interfaces, not implementations

Infrastructure packages:
- celery: Celery async task queue adapter
- supabase: Supabase client, auth, and storage adapters
- langchain: LangChain LLM gateway adapter
- repositories: In-memory and other repository implementations
- observability: Tracing, metrics, and logging
"""

# Note: Imports are lazy to avoid requiring optional dependencies
# Use direct imports when needed:
#   from app.infrastructure.celery import get_task_queue
#   from app.infrastructure.supabase import SupabaseStorageAdapter
#   from app.infrastructure.langchain import LangChainLLMGateway
