"""PromptStore — file-system cache for generated form-specific prompts.

Stores prompts as JSON files keyed by a hash of the form's field structure.
Supports exact-match lookup for cache hits.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models.form_context import FormFieldSpec
from app.services.prompt_generator.models import PromptCacheEntry

logger = logging.getLogger(__name__)


class PromptStore:
    """File-system store for generated form-specific prompts."""

    def __init__(self, storage_dir: str = ".prompt_cache") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def compute_form_hash(self, fields: tuple[FormFieldSpec, ...]) -> str:
        """Compute a deterministic hash of the form's field structure.

        Hash is based on field count, sorted field_ids, and field types.
        Same form structure always produces the same hash.
        """
        field_ids = sorted(f.field_id for f in fields)
        field_types = sorted(f.field_type for f in fields)
        content = f"{len(fields)}:{','.join(field_ids)}:{','.join(field_types)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def store(
        self,
        form_hash: str,
        prompt: str,
        form_title: str | None = None,
        field_count: int = 0,
    ) -> None:
        """Save a generated prompt to the file system."""
        entry = PromptCacheEntry(
            form_hash=form_hash,
            specialized_prompt=prompt,
            field_count=field_count,
            created_at=datetime.now(timezone.utc).isoformat(),
            form_title=form_title,
        )
        path = self._storage_dir / f"{form_hash}.json"
        path.write_text(
            json.dumps(
                {
                    "form_hash": entry.form_hash,
                    "specialized_prompt": entry.specialized_prompt,
                    "field_count": entry.field_count,
                    "created_at": entry.created_at,
                    "form_title": entry.form_title,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info(f"[prompt_store] cached prompt: hash={form_hash}, fields={field_count}")

    def find_similar(self, form_hash: str, top_k: int = 2) -> list[str] | None:
        """Look up cached prompts by exact hash match.

        Returns the cached prompt text as a single-element list on hit,
        or None on miss.

        Args:
            form_hash: Hash to look up.
            top_k: Unused in exact-match mode (reserved for future
                embedding-based search).

        Returns:
            List containing the cached prompt, or None if not found.
        """
        path = self._storage_dir / f"{form_hash}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            prompt = data.get("specialized_prompt", "")
            if prompt:
                logger.info(f"[prompt_store] cache hit: hash={form_hash}")
                return [prompt]
        except Exception as e:
            logger.warning(f"[prompt_store] failed to read cache: {e}")

        return None
