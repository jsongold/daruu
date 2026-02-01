"""Redis Job Store for distributed job state management.

This module provides a Redis-based implementation for:
- Job state persistence with TTL support
- Distributed locking for concurrent job processing
- Job querying by status and other criteria

Uses redis-py with async support (redis.asyncio).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import uuid4

from app.config import RedisConfig, get_redis_config
from app.models import (
    Activity,
    ActivityAction,
    Document,
    Evidence,
    Extraction,
    FieldModel,
    Issue,
    JobContext,
    JobMode,
    JobStatus,
    Mapping,
)

logger = logging.getLogger(__name__)

# Default TTL for jobs (24 hours)
DEFAULT_JOB_TTL_SECONDS = 86400

# Default lock timeout (30 seconds)
DEFAULT_LOCK_TIMEOUT_SECONDS = 30


class RedisConnectionError(Exception):
    """Raised when Redis connection fails."""

    pass


class RedisLockError(Exception):
    """Raised when lock acquisition fails."""

    pass


class RedisSerializationError(Exception):
    """Raised when serialization/deserialization fails."""

    pass


def _serialize_job(job: JobContext) -> str:
    """Serialize a JobContext to JSON string."""
    try:
        return job.model_dump_json()
    except Exception as e:
        raise RedisSerializationError(f"Failed to serialize job: {e}") from e


def _deserialize_job(data: str | bytes) -> JobContext:
    """Deserialize a JSON string to JobContext."""
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return JobContext.model_validate_json(data)
    except Exception as e:
        raise RedisSerializationError(f"Failed to deserialize job: {e}") from e


class RedisJobStore:
    """Redis-based job store for distributed locking and state.

    Key structure:
    - {prefix}job:{job_id} - Job data as JSON
    - {prefix}lock:{job_id} - Lock key
    - {prefix}status:{status} - Set of job IDs with that status
    - {prefix}all - Set of all job IDs
    """

    def __init__(
        self,
        redis_url: str | None = None,
        key_prefix: str | None = None,
        lock_timeout: int | None = None,
        job_ttl: int | None = None,
        config: RedisConfig | None = None,
    ) -> None:
        cfg = config if config is not None else get_redis_config()
        self._redis_url = redis_url if redis_url is not None else cfg.url
        self._key_prefix = key_prefix if key_prefix is not None else f"{cfg.prefix}job:"
        self._lock_timeout = lock_timeout if lock_timeout is not None else cfg.lock_timeout
        self._job_ttl = job_ttl if job_ttl is not None else DEFAULT_JOB_TTL_SECONDS
        self._redis: Any = None
        self._connected = False

    def _job_key(self, job_id: str) -> str:
        return f"{self._key_prefix}{job_id}"

    def _lock_key(self, job_id: str) -> str:
        return f"{self._key_prefix}lock:{job_id}"

    def _status_key(self, status: JobStatus) -> str:
        return f"{self._key_prefix}status:{status.value}"

    def _all_jobs_key(self) -> str:
        return f"{self._key_prefix}all"

    async def connect(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """Connect to Redis with retry logic."""
        try:
            import redis.asyncio as redis
        except ImportError as e:
            raise RedisConnectionError(
                "redis package not installed. Install with: pip install redis"
            ) from e

        import asyncio

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                self._redis = redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=False,
                )
                await self._redis.ping()
                self._connected = True
                logger.info(f"Connected to Redis at {self._redis_url}")
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        raise RedisConnectionError(
            f"Failed to connect to Redis after {max_retries} attempts: {last_error}"
        )

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._connected = False
            logger.info("Redis connection closed")

    def _ensure_connected(self) -> None:
        if not self._connected or self._redis is None:
            raise RedisConnectionError("Not connected to Redis. Call connect() first.")

    async def create(
        self,
        mode: JobMode,
        target_document: Document,
        source_document: Document | None = None,
    ) -> JobContext:
        """Create a new job in Redis."""
        self._ensure_connected()

        job_id = str(uuid4())
        now = datetime.now(timezone.utc)

        initial_activity = Activity(
            id=str(uuid4()),
            timestamp=now,
            action=ActivityAction.JOB_CREATED,
            details={"mode": mode.value},
        )

        job = JobContext(
            id=job_id,
            mode=mode,
            status=JobStatus.CREATED,
            source_document=source_document,
            target_document=target_document,
            fields=[],
            mappings=[],
            extractions=[],
            evidence=[],
            issues=[],
            activities=[initial_activity],
            created_at=now,
            updated_at=now,
            progress=0.0,
            current_step="initialized",
            next_actions=["run"],
        )

        job_data = _serialize_job(job)
        job_key = self._job_key(job_id)

        async with self._redis.pipeline() as pipe:
            pipe.set(job_key, job_data, ex=self._job_ttl)
            pipe.sadd(self._all_jobs_key(), job_id)
            pipe.sadd(self._status_key(job.status), job_id)
            await pipe.execute()

        logger.info(f"Created job {job_id} with mode {mode.value}")
        return job

    async def get(self, job_id: str) -> JobContext | None:
        """Get a job by ID from Redis."""
        self._ensure_connected()

        job_data = await self._redis.get(self._job_key(job_id))
        if job_data is None:
            return None

        return _deserialize_job(job_data)

    async def update(self, job_id: str, **updates: Any) -> JobContext | None:
        """Update a job with new values (immutable pattern)."""
        self._ensure_connected()

        job = await self.get(job_id)
        if job is None:
            return None

        old_status = job.status

        updated_data = job.model_dump()
        updated_data.update(updates)
        updated_data["updated_at"] = datetime.now(timezone.utc)

        new_job = JobContext(**updated_data)
        job_data = _serialize_job(new_job)

        async with self._redis.pipeline() as pipe:
            pipe.set(self._job_key(job_id), job_data, ex=self._job_ttl)

            if "status" in updates and updates["status"] != old_status:
                new_status = updates["status"]
                if isinstance(new_status, JobStatus):
                    pipe.srem(self._status_key(old_status), job_id)
                    pipe.sadd(self._status_key(new_status), job_id)

            await pipe.execute()

        return new_job

    async def add_activity(self, job_id: str, activity: Activity) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_activities = [*job.activities, activity]
        return await self.update(job_id, activities=new_activities)

    async def add_field(self, job_id: str, field: FieldModel) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_fields = [*job.fields, field]
        return await self.update(job_id, fields=new_fields)

    async def update_field(
        self, job_id: str, field_id: str, **updates: Any
    ) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None

        new_fields = []
        found = False
        for f in job.fields:
            if f.id == field_id:
                field_data = f.model_dump()
                field_data.update(updates)
                new_fields.append(FieldModel(**field_data))
                found = True
            else:
                new_fields.append(f)

        if not found:
            return None

        return await self.update(job_id, fields=new_fields)

    async def add_mapping(self, job_id: str, mapping: Mapping) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_mappings = [*job.mappings, mapping]
        return await self.update(job_id, mappings=new_mappings)

    async def add_extraction(
        self, job_id: str, extraction: Extraction
    ) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_extractions = [*job.extractions, extraction]
        return await self.update(job_id, extractions=new_extractions)

    async def add_evidence(self, job_id: str, evidence: Evidence) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_evidence = [*job.evidence, evidence]
        return await self.update(job_id, evidence=new_evidence)

    async def add_issue(self, job_id: str, issue: Issue) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_issues = [*job.issues, issue]
        return await self.update(job_id, issues=new_issues)

    async def clear_issues(self, job_id: str) -> JobContext | None:
        return await self.update(job_id, issues=[])

    async def remove_issue(self, job_id: str, issue_id: str) -> JobContext | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_issues = [i for i in job.issues if i.id != issue_id]
        return await self.update(job_id, issues=new_issues)

    async def list_all(self) -> list[JobContext]:
        self._ensure_connected()
        job_ids = await self._redis.smembers(self._all_jobs_key())
        jobs = []
        for job_id_bytes in job_ids:
            job_id = job_id_bytes.decode("utf-8") if isinstance(job_id_bytes, bytes) else job_id_bytes
            job = await self.get(job_id)
            if job is not None:
                jobs.append(job)
        return jobs

    async def list_by_status(self, status: JobStatus) -> list[JobContext]:
        self._ensure_connected()
        job_ids = await self._redis.smembers(self._status_key(status))
        jobs = []
        for job_id_bytes in job_ids:
            job_id = job_id_bytes.decode("utf-8") if isinstance(job_id_bytes, bytes) else job_id_bytes
            job = await self.get(job_id)
            if job is not None and job.status == status:
                jobs.append(job)
        return jobs

    async def delete(self, job_id: str) -> bool:
        self._ensure_connected()
        job = await self.get(job_id)
        if job is None:
            return False

        async with self._redis.pipeline() as pipe:
            pipe.delete(self._job_key(job_id))
            pipe.srem(self._all_jobs_key(), job_id)
            pipe.srem(self._status_key(job.status), job_id)
            pipe.delete(self._lock_key(job_id))
            await pipe.execute()

        logger.info(f"Deleted job {job_id}")
        return True

    # Distributed Locking

    async def acquire_lock(self, job_id: str, timeout: int | None = None) -> bool:
        self._ensure_connected()
        lock_timeout = timeout if timeout is not None else self._lock_timeout
        lock_key = self._lock_key(job_id)

        acquired = await self._redis.set(
            lock_key, "1", nx=True, ex=lock_timeout
        )

        if acquired:
            logger.debug(f"Acquired lock for job {job_id}")
        else:
            logger.debug(f"Failed to acquire lock for job {job_id}")

        return bool(acquired)

    async def release_lock(self, job_id: str) -> None:
        self._ensure_connected()
        lock_key = self._lock_key(job_id)
        await self._redis.delete(lock_key)
        logger.debug(f"Released lock for job {job_id}")

    async def extend_lock(self, job_id: str, timeout: int | None = None) -> bool:
        self._ensure_connected()
        lock_timeout = timeout if timeout is not None else self._lock_timeout
        lock_key = self._lock_key(job_id)
        extended = await self._redis.expire(lock_key, lock_timeout)
        return bool(extended)

    async def is_locked(self, job_id: str) -> bool:
        self._ensure_connected()
        lock_key = self._lock_key(job_id)
        return bool(await self._redis.exists(lock_key))

    @asynccontextmanager
    async def lock(
        self,
        job_id: str,
        timeout: int | None = None,
        blocking: bool = True,
        blocking_timeout: float = 10.0,
    ) -> AsyncIterator[bool]:
        import asyncio

        acquired = False
        try:
            if blocking:
                start_time = asyncio.get_event_loop().time()
                while True:
                    acquired = await self.acquire_lock(job_id, timeout)
                    if acquired:
                        break
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= blocking_timeout:
                        raise RedisLockError(
                            f"Failed to acquire lock for job {job_id} after {blocking_timeout}s"
                        )
                    await asyncio.sleep(0.1)
            else:
                acquired = await self.acquire_lock(job_id, timeout)

            yield acquired
        finally:
            if acquired:
                await self.release_lock(job_id)

    # Utility Methods

    async def refresh_ttl(self, job_id: str, ttl: int | None = None) -> bool:
        self._ensure_connected()
        job_ttl = ttl if ttl is not None else self._job_ttl
        job_key = self._job_key(job_id)
        refreshed = await self._redis.expire(job_key, job_ttl)
        return bool(refreshed)

    async def get_ttl(self, job_id: str) -> int | None:
        self._ensure_connected()
        job_key = self._job_key(job_id)
        ttl = await self._redis.ttl(job_key)
        if ttl < 0:
            return None
        return ttl

    async def cleanup_expired_references(self) -> int:
        self._ensure_connected()
        removed = 0
        job_ids = await self._redis.smembers(self._all_jobs_key())

        for job_id_bytes in job_ids:
            job_id = job_id_bytes.decode("utf-8") if isinstance(job_id_bytes, bytes) else job_id_bytes
            exists = await self._redis.exists(self._job_key(job_id))
            if not exists:
                async with self._redis.pipeline() as pipe:
                    pipe.srem(self._all_jobs_key(), job_id)
                    for status in JobStatus:
                        pipe.srem(self._status_key(status), job_id)
                    await pipe.execute()
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} expired job references")

        return removed
