"""Lightweight stopwatch for structured profiling.

Collects named lap durations (milliseconds) and optionally auto-logs
them as a structured ``extra`` dict on context-manager exit.

Usage — auto-log mode (builder.py style)::

    with StopWatch("FormContextBuilder.build", logger) as sw:
        with sw.lap("list_sources"):
            data = repo.list(...)
        with sw.lap("enrich"):
            enriched = enrich(data)
        sw.set(document_id=doc_id, fields_count=10)
    # logger.info("FormContextBuilder.build", extra={
    #     "total_ms": 57, "list_sources_ms": 12, "enrich_ms": 45,
    #     "document_id": doc_id, "fields_count": 10,
    # })

Usage — manual mode (service.py style)::

    sw = StopWatch()
    with sw.lap("context_build"):
        ctx = await build(...)
    duration = sw.laps["context_build"]  # int ms
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Generator


class StopWatch:
    """Instance-scoped stopwatch with named laps and optional auto-logging."""

    __slots__ = ("_label", "_logger", "_start", "_laps", "_extras")

    def __init__(
        self,
        label: str = "",
        logger: logging.Logger | None = None,
    ) -> None:
        self._label = label
        self._logger = logger
        self._start = perf_counter()
        self._laps: dict[str, int] = {}
        self._extras: dict[str, Any] = {}

    # -- lap timing ----------------------------------------------------------

    @contextmanager
    def lap(self, name: str) -> Generator[None, None, None]:
        """Time a named code block in milliseconds."""
        t = perf_counter()
        yield
        self._laps[name] = int((perf_counter() - t) * 1000)

    # -- extra attributes ----------------------------------------------------

    def set(self, **kwargs: Any) -> None:
        """Attach arbitrary key-values included in the auto-log output."""
        self._extras.update(kwargs)

    # -- read-only access ----------------------------------------------------

    @property
    def total_ms(self) -> int:
        """Wall-clock milliseconds since construction."""
        return int((perf_counter() - self._start) * 1000)

    @property
    def laps(self) -> dict[str, int]:
        """Snapshot of ``{lap_name: duration_ms}``."""
        return dict(self._laps)

    # -- context manager (auto-log on exit) ----------------------------------

    def __enter__(self) -> StopWatch:
        return self

    def __exit__(self, *exc: object) -> None:
        if self._logger is not None:
            self._logger.info(
                self._label,
                extra={
                    "total_ms": self.total_ms,
                    **{f"{k}_ms": v for k, v in self._laps.items()},
                    **self._extras,
                },
            )
